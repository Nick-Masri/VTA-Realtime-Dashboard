import os
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import streamlit as st
import yaml
from pyomo.contrib.appsi.base import TerminationCondition
from pyomo.contrib.appsi.solvers import Highs

from chargeopt.baseline import charge_on_arrival
from chargeopt.consumption import block_energy
from chargeopt.helpers import init_grid_pricing, init_routes, time_to_quarter

warnings.simplefilter(action='ignore', category=FutureWarning)

# HiGHS is open source and slower than Gurobi on a model this size, so the
# solve is bounded and any incumbent found by then is used. The full ten-bus
# fleet lands around 110-125s but varies with machine load - one run in five
# reached 180s with nothing - so the ceiling carries real headroom.
TIME_LIMIT_SECONDS = 300
# Share of each window's budget given to deciding coverage before cost.
COVERAGE_SHARE = 0.45
MIP_GAP = 0.03

# The plan is built as rolling 24-hour windows starting from now, one solved
# after another with each bus's charge carried into the next. A window holds a
# block and the night that recharges for it, so the overnight top-up is never
# split across a boundary the way a midnight-to-midnight day would split it.
WINDOW = 96
DAYS = 3
# A monthly demand charge is set by a single peak, so a plan meant to repeat
# daily carries a thirtieth of it per day.
DAYS_PER_MONTH = 30

# Where block energy comes from.
#   'interval' - upper end of a (1 - CONSUMPTION_ALPHA) conformal band from the
#                MAPIE model, per bus. The default: the plan then survives any
#                day whose consumption lands below about its 95th percentile.
#   'point'    - the model's point prediction, which roughly half of days beat
#   'fixed'    - the flat 2.5 kWh/mile the scheduler used before
CONSUMPTION_MODE = 'interval'
CONSUMPTION_ALPHA = 0.1
# Windows are anchored to the operating day rather than to the moment the plan
# is built. Anchored to "now", a block starting more than a few hours out has
# its return fall past the window's end and gets dropped; anchored to the small
# hours, a pull-out and the night that recharges for it sit in the same window.
DAY_START = 12  # 03:00

# Charging stretches allowed per bus per operating day. One is what the
# original model allowed across a whole calendar day, but a block and the
# charging either side of it now sit inside a single window, and a bus needing
# a top-up before pull-out as well as a recharge after pull-in needs two.
CHARGE_WINDOWS_PER_DAY = 2

# The binding difficulty here is finding any feasible schedule, not closing the
# gap, so HiGHS is pushed well past its default heuristic effort of 0.05.

# What each bus must have left at the end of the horizon.
#   'start'    - at least what it began with. Repeatable: the plan can be run
#                again tomorrow from the same state. This is the original.
#   'reserve'  - only the 20% floor. Cheapest and easiest to solve, but the
#                fleet ends flatter than it started, so the schedule is a
#                one-off rather than a steady state.
#   'fraction' - a fixed readiness target, END_SOC_FRACTION of the pack. Not
#                strictly a relaxation: it is looser than 'start' for a bus
#                that began above the target and tighter for one below it.
END_SOC_MODE = 'start'
END_SOC_FRACTION = 0.8

# Statuses that mean a schedule was written. Callers test with is_solved rather
# than comparing strings, so the wording can carry caveats - a dropped block, a
# remaining gap - without the results view falling through to nothing.
SOLVED_PREFIXES = ('Optimal solution found', 'Stopped at', 'Schedule found')


def is_solved(status):
    return bool(status) and str(status).startswith(SOLVED_PREFIXES)


def is_partial(status):
    """Solved, but with something the operator needs to know about."""
    text = str(status)
    return is_solved(status) and (
        'unserved' in text
        or 'no bus available' in text
        or 'beyond range' in text
        or text.startswith('Stopped')
        or text.startswith('Schedule found')
    )

HIGHS_OPTIONS = {
    'mip_heuristic_effort': 0.5,
    'mip_detect_symmetry': True,
    'presolve': 'on',
}


def _end_target(soc, eB_max, eB_min):
    if END_SOC_MODE == 'reserve':
        return eB_min
    if END_SOC_MODE == 'fraction':
        return eB_max * END_SOC_FRACTION
    return eB_max * soc


def _soc_fraction(raw):
    """Accept a '85%' string or a plain number."""
    if isinstance(raw, str):
        raw = raw.strip().rstrip('%')
    return float(raw) / 100




def _window_blocks(w0, departure, arrival, frozen):
    """Where each block falls inside the operating day starting at quarter w0.

    Blocks recur daily, so every window holds one occurrence of each. A block
    already under way when the plan is built cannot be crewed now, and one
    whose return lands past the window's end would never have its energy
    deducted; neither is offered.
    """
    placed = {}
    for r in range(len(departure)):
        start = int((departure[r] - 1 - w0) % WINDOW)
        length = int((arrival[r] - departure[r]) % WINDOW)
        if start >= frozen and start + length < WINDOW:
            placed[r] = (start, start + length)
    return placed


def _solve_window(w0, soc_at_start, placed, energy, prices, budget, sizes, frozen=0):
    """One rolling day. Returns the schedule, or None if nothing was found."""
    B, eB_max, eB_min, eB_range, pCB_ub, gridKWH, numChargers, dt, eff, demand_rate = sizes
    runnable = sorted(placed)

    m = pyo.ConcreteModel()
    m.B = pyo.RangeSet(0, B - 1)
    m.I = pyo.RangeSet(0, WINDOW - 1)
    m.R = pyo.Set(initialize=runnable, ordered=True)

    # powerCB is what reaches the pack; gridPowToB is what the meter sees.
    m.powerCB = pyo.Var(m.B, m.I, bounds=(0, pCB_ub))
    m.gridPowToB = pyo.Var(m.B, m.I, bounds=(0, pCB_ub / eff))
    m.eB = pyo.Var(m.B, m.I, bounds=(eB_min, eB_max))
    m.chargerUse = pyo.Var(m.B, m.I, domain=pyo.Binary)
    m.T1 = pyo.Var(m.B, m.I, domain=pyo.Binary)
    m.T2 = pyo.Var(m.B, m.I, domain=pyo.Binary)
    m.change = pyo.Var(m.B, m.I, domain=pyo.Binary)
    m.charging = pyo.Var(m.B, domain=pyo.Binary)
    m.assignment = pyo.Var(m.B, m.R, domain=pyo.Binary)
    m.unserved = pyo.Var(m.R, domain=pyo.Binary)
    # Highest depot draw over the window, priced in the cost pass so the plan
    # flattens its own peak rather than only chasing cheap quarters.
    m.peak = pyo.Var(bounds=(0, gridKWH))

    later = pyo.RangeSet(1, WINDOW - 1)

    m.change_link = pyo.Constraint(m.B, m.I, rule=lambda m, b, i:
                                   m.change[b, i] == m.T1[b, i] + m.T2[b, i])
    m.use_link_1 = pyo.Constraint(m.B, later, rule=lambda m, b, i:
                                  m.T1[b, i] - m.T2[b, i]
                                  == m.chargerUse[b, i] - m.chargerUse[b, i - 1])
    m.use_link_2 = pyo.Constraint(m.B, later, rule=lambda m, b, i:
                                  m.change[b, i] <= m.chargerUse[b, i - 1] + m.chargerUse[b, i])
    m.use_link_3 = pyo.Constraint(m.B, later, rule=lambda m, b, i:
                                  m.change[b, i] <= 2 - m.chargerUse[b, i - 1] - m.chargerUse[b, i])
    m.first_change = pyo.Constraint(m.B, rule=lambda m, b:
                                    m.change[b, 0] == m.chargerUse[b, 0])
    m.change_cap = pyo.Constraint(m.B, rule=lambda m, b:
                                  sum(m.change[b, i] for i in m.I)
                                  <= 2 * CHARGE_WINDOWS_PER_DAY)
    m.daily_min = pyo.Constraint(m.B, rule=lambda m, b:
                                 sum(m.chargerUse[b, i] for i in m.I) >= 4 * m.charging[b])
    m.daily_max = pyo.Constraint(m.B, rule=lambda m, b:
                                 sum(m.chargerUse[b, i] for i in m.I) <= WINDOW * m.charging[b])
    # Power is free between zero and rated whenever the bus is plugged in.
    # It used to be pinned at rated output by a pair of big-M rows selected by
    # a tracker binary - the one non-linear piece of the original Gurobi model.
    # That forbade the only lever that actually shaves a peak, and cost two
    # binaries per bus per quarter to enforce.
    m.power_gate = pyo.Constraint(m.B, m.I, rule=lambda m, b, i:
                                  m.powerCB[b, i] <= pCB_ub * m.chargerUse[b, i])
    m.charger_count = pyo.Constraint(m.I, rule=lambda m, i:
                                     sum(m.chargerUse[b, i] for b in m.B) <= numChargers)
    m.grid_total = pyo.Constraint(m.I, rule=lambda m, i:
                                  sum(m.gridPowToB[b, i] for b in m.B) <= gridKWH)
    # The depot is billed for what it draws; the pack receives eff of it.
    m.charger_supply = pyo.Constraint(m.B, m.I, rule=lambda m, b, i:
                                      m.powerCB[b, i] == eff * m.gridPowToB[b, i])
    m.peak_def = pyo.Constraint(m.I, rule=lambda m, i:
                                sum(m.gridPowToB[b, i] for b in m.B) <= m.peak)

    returns_at = {}
    departs_at = {}
    for r, (start, end) in placed.items():
        returns_at.setdefault(end, []).append(r)
        departs_at.setdefault(start, []).append(r)

    m.battery = pyo.ConstraintList()
    m.route_requirement = pyo.ConstraintList()
    m.opening = pyo.ConstraintList()
    for b in range(B):
        held = eB_max * soc_at_start[b]
        m.opening.add(m.eB[b, 0] == held)
        # The stretch of this window that is already in the past when the plan
        # is built: nothing can be scheduled into it.
        for i in range(frozen):
            m.opening.add(m.eB[b, i] == held)
            m.opening.add(m.powerCB[b, i] == 0)
            m.opening.add(m.gridPowToB[b, i] == 0)
            m.opening.add(m.chargerUse[b, i] == 0)
        m.opening.add(m.eB[b, WINDOW - 1] >= _end_target(soc_at_start[b], eB_max, eB_min))
        for i in range(WINDOW):
            if i > 0:
                drop = sum(energy[(b, r)] * m.assignment[b, r]
                           for r in returns_at.get(i, []))
                m.battery.add(m.eB[b, i] == m.eB[b, i - 1] + dt * m.powerCB[b, i - 1] - drop)
            need = sum(energy[(b, r)] * m.assignment[b, r]
                       for r in departs_at.get(i, []))
            m.route_requirement.add(m.eB[b, i] >= eB_min + need)

    m.coverage = pyo.ConstraintList()
    for b in range(B):
        for r, (start, end) in placed.items():
            for i in range(start, min(end + 1, WINDOW)):
                m.coverage.add(m.chargerUse[b, i] + m.assignment[b, r] <= 1)

    # A window whose blocks have all departed already still has to be solved -
    # the fleet charges through it - but its coverage constraints would reduce
    # to trivial truths, which Pyomo rejects.
    if runnable:
        m.route_covered = pyo.Constraint(m.R, rule=lambda m, r:
                                         sum(m.assignment[b, r] for b in m.B)
                                         + m.unserved[r] == 1)
        m.one_route_each = pyo.Constraint(m.B, rule=lambda m, b:
                                          sum(m.assignment[b, r] for r in m.R) <= 1)
        m.full_coverage = pyo.Constraint(expr=sum(m.unserved[r] for r in runnable) == 0)

    energy_cost = dt * sum(prices[i] * sum(m.gridPowToB[b, i] for b in range(B))
                           for i in range(WINDOW))
    m.coverage_obj = pyo.Objective(
        expr=sum(m.unserved[r] for r in runnable) if runnable else 0,
        sense=pyo.minimize)
    # A monthly demand charge is set by one peak, so a repeating daily plan
    # carries a thirtieth of it per day. At that weight the peak term and the
    # energy term land in the same order of magnitude and genuinely trade off.
    m.cost_obj = pyo.Objective(expr=energy_cost + demand_rate * m.peak,
                               sense=pyo.minimize)
    m.cost_obj.deactivate()

    def run(limit, warmstart=False):
        solver = Highs()
        solver.config.warmstart = warmstart
        solver.config.time_limit = max(limit, 5)
        solver.config.mip_gap = MIP_GAP
        solver.config.load_solution = False
        solver.config.stream_solver = False
        for option, value in HIGHS_OPTIONS.items():
            solver.highs_options[option] = value
        return solver.solve(m)

    def seed_parked():
        m.peak.set_value(0)
        for b in range(B):
            held = eB_max * soc_at_start[b]
            for i in range(WINDOW):
                m.eB[b, i].set_value(held)
                m.powerCB[b, i].set_value(0)
                m.gridPowToB[b, i].set_value(0)
                for var in (m.chargerUse, m.T1, m.T2, m.change):
                    var[b, i].set_value(0)
            m.charging[b].set_value(0)
            for r in runnable:
                m.assignment[b, r].set_value(0)
        for r in runnable:
            m.unserved[r].set_value(1)

    began = time.time()
    result = run(budget * COVERAGE_SHARE)
    if result.best_feasible_objective is None:
        if runnable:
            m.full_coverage.deactivate()
        if END_SOC_MODE in ('start', 'reserve'):
            seed_parked()
        spent = time.time() - began
        result = run(budget * COVERAGE_SHARE - spent + budget * 0.1,
                     warmstart=END_SOC_MODE in ('start', 'reserve'))
        if result.best_feasible_objective is None:
            return None
    result.solution_loader.load_vars()

    if runnable:
        m.coverage_level = pyo.Constraint(
            expr=sum(m.unserved[r] for r in runnable)
            <= sum(round(pyo.value(m.unserved[r])) for r in runnable))
    m.coverage_obj.deactivate()
    m.cost_obj.activate()

    cost_result = run(budget - (time.time() - began), warmstart=True)
    optimal = cost_result.termination_condition == TerminationCondition.optimal
    if cost_result.best_feasible_objective is not None:
        cost_result.solution_loader.load_vars()
    else:
        optimal = False

    rows = []
    for i in range(WINDOW):
        for b in range(B):
            rows.append({'time': w0 + i, 'bus': b,
                         'powerCB': pyo.value(m.powerCB[b, i]),
                         'gridPowToB': pyo.value(m.gridPowToB[b, i]),
                         'eB': pyo.value(m.eB[b, i]),
                         'chargerUse': pyo.value(m.chargerUse[b, i])})

    energy = dt * sum(prices[i] * sum(pyo.value(m.gridPowToB[b, i]) for b in range(B))
                      for i in range(WINDOW))
    peak_kw = pyo.value(m.peak)

    return {
        'rows': rows,
        'end_soc': {b: pyo.value(m.eB[b, WINDOW - 1]) / eB_max for b in range(B)},
        'served': {r: [b for b in range(B) if pyo.value(m.assignment[b, r]) > 0.5]
                   for r in runnable},
        'unserved': [r for r in runnable if pyo.value(m.unserved[r]) > 0.5],
        'energy_cost': energy,
        'peak_kw': peak_kw,
        'energy_kwh': dt * sum(pyo.value(m.gridPowToB[b, i])
                               for b in range(B) for i in range(WINDOW)),
        'cost': energy + demand_rate * peak_kw,
        'optimal': optimal,
    }

class ChargeOpt:
    def __init__(self, buses, routes, chargers, scenario=None):
        self.buses = buses
        self.routes = routes
        self.chargers = chargers
        # Per-run overrides of config.yml, so "what if we added two chargers"
        # is a question the tool answers rather than a file edit.
        self.scenario = scenario or {}
        self.startTime = datetime.now()
        # Filled in by solve(); None means no comparison is available, which
        # every early return below leaves in place.
        self.summary = None

    def solve(self):
        startTimeNum = time_to_quarter(self.startTime.strftime('%I:%M %p'))

        B = len(self.buses)
        if B == 0:
            return "No buses selected", startTimeNum

        routes = self.routes
        R = len(routes)
        if R == 0:
            return "No blocks selected", startTimeNum

        config_path = os.path.join(os.getcwd(), "chargeopt/config.yml")
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        filename = f'chargeopt_{datetime.now().strftime("%m-%d-%Y_%H-%M-%S")}'
        def setting(key, default):
            # An explicit zero is a real answer, so None is the only fallback.
            value = self.scenario.get(key)
            return default if value is None else value

        eB_max = setting('ebMaxKwh', config["ebMaxKwh"])
        eB_min = int(eB_max * .2)
        eB_range = eB_max - eB_min
        numChargers = setting('numChargers', len(self.chargers))
        pCB_ub = setting('chargerPower', config["chargerPower"])
        gridKWH = setting('gridMaxPower', config['gridMaxPower'])
        eff = setting('chargerEff', config['chargerEff'])
        demand_month = setting('demandChargePerKw',
                               config.get('demandChargePerKw', 0.0))
        demand_rate = demand_month / DAYS_PER_MONTH
        consumption_mode = setting('consumption_mode', CONSUMPTION_MODE)
        consumption_alpha = setting('consumption_alpha', CONSUMPTION_ALPHA)
        dt = 0.25

        if numChargers < 1:
            return "No chargers selected", startTimeNum

        block_labels = [str(x) for x in routes['block_id']] if 'block_id' in routes else [
            str(i) for i in range(len(routes))]

        mileages = routes['Mileage'].to_numpy()
        [departure, arrival, eRoute, report] = init_routes(routes, eB_range, pCB_ub)

        coaches = [self.buses.iloc[b, 0] for b in range(B)]
        energy, consumption_note = block_energy(
            coaches, mileages, eB_max, consumption_mode, consumption_alpha)

        # A block no bus can run on one charge is impossible for the fleet, not
        # merely awkward: the bus would have to leave holding more than it can
        # store. Screened against the most frugal bus, now that consumption
        # differs between them.
        too_long = [r for r in range(R)
                    if min(energy[(b, r)] for b in range(B)) >= eB_range]
        excluded_note = ''
        # Route indices are reported against the block list the caller handed
        # in, which still holds the excluded ones.
        original_index = list(range(R))
        if too_long:
            names = ', '.join(block_labels[r] for r in too_long)
            keep = [r for r in range(R) if r not in too_long]
            if not keep:
                return (f"Every block needs more than the {eB_range:.0f} kWh a "
                        f"pack can give: {names}"), startTimeNum
            departure = np.asarray(departure)[keep]
            arrival = np.asarray(arrival)[keep]
            energy = {(b, new_r): energy[(b, old_r)]
                      for b in range(B) for new_r, old_r in enumerate(keep)}
            block_labels = [block_labels[r] for r in keep]
            original_index = keep
            R = len(keep)
            excluded_note = f" - beyond range on one charge: {names}"

        soc = {b: _soc_fraction(self.buses.iloc[b, 1]) for b in range(B)}
        too_low = [str(self.buses.iloc[b, 0]) for b in range(B)
                   if eB_max * soc[b] < eB_min]
        if too_low:
            return (f"Below the {eB_min / eB_max:.0%} reserve at start: "
                    f"{', '.join(too_low)}"), startTimeNum

        prices = init_grid_pricing(DAYS + 2, self.scenario.get('tariff'))
        sizes = (B, eB_max, eB_min, eB_range, pCB_ub, gridKWH, numChargers, dt,
                 eff, demand_rate)

        schedule = []
        assignments = []
        missed = {}
        asked = 0
        cost = 0.0
        energy_cost = 0.0
        energy_kwh = 0.0
        peak_kw = 0.0
        all_optimal = True
        # The baseline runs from the same opening charge and the same duties,
        # so it has to be captured before the loop rolls soc forward.
        soc_at_start = dict(soc)
        windows = []
        began = time.time()

        for day in range(DAYS):
            w0 = DAY_START + day * WINDOW
            frozen = max(0, min(startTimeNum - w0, WINDOW))
            placed = _window_blocks(w0, departure, arrival, frozen)
            asked += len(placed)

            left = TIME_LIMIT_SECONDS - (time.time() - began)
            budget = max(left / (DAYS - day), 10)
            out = _solve_window(w0, soc, placed, energy,
                                prices[w0:w0 + WINDOW], budget, sizes, frozen)
            if out is None:
                return (f"No schedule found for day {day + 1} within "
                        f"{TIME_LIMIT_SECONDS}s"), startTimeNum

            schedule.extend(out['rows'])
            cost += out['cost']
            energy_cost += out['energy_cost']
            energy_kwh += out['energy_kwh']
            # The bill is set by the worst quarter, not the sum of the days.
            peak_kw = max(peak_kw, out['peak_kw'])
            all_optimal = all_optimal and out['optimal']
            windows.append((w0, frozen, placed, out['served']))
            soc = out['end_soc']

            # The label a block is filed under is the calendar day it departs
            # in, which is what the results view reconstructs its clock time
            # from.
            for r, (start, _) in placed.items():
                calendar_day = (w0 + start) // WINDOW
                for b in range(B):
                    assignments.append({
                        'day': calendar_day, 'bus': b, 'route': original_index[r],
                        'assignment': 1 if b in out['served'][r] else 0})
            for r in out['unserved']:
                calendar_day = (w0 + placed[r][0]) // WINDOW
                missed.setdefault(calendar_day, []).append(block_labels[r])

        sol_time = time.time() - began
        unfilled_count = sum(len(v) for v in missed.values())

        base = charge_on_arrival(soc_at_start, windows, energy, prices, sizes, WINDOW)
        # Monthly figures assume the planned days repeat. Energy scales with
        # the days; the demand charge is levied once on the highest peak.
        def _monthly(energy_per_day, peak):
            return energy_per_day * DAYS_PER_MONTH + demand_month * peak

        # Uncontrolled charging fills every pack, while the plan charges only
        # to its end-of-horizon target, so the headline gap is partly a
        # difference in energy bought. The rate paid per kWh is the like-for-
        # like number and is what the time-of-use shifting actually earns.
        def _rate(cost_total, kwh):
            return cost_total / kwh if kwh > 0 else 0.0

        optimized_daily = energy_cost / DAYS
        baseline_daily = base['energy_cost'] / DAYS
        self.summary = {
            'demand_charge_per_kw': demand_month,
            'consumption': consumption_note,
            'scenario': {
                'chargers': numChargers,
                'charger_kw': pCB_ub,
                'grid_kw': gridKWH,
                'demand_per_kw': demand_month,
                'basis': consumption_mode,
                'tariff': dict(self.scenario.get('tariff') or {}),
            },
            'covered': asked - unfilled_count,
            'asked': asked,
            'optimized': {
                'energy_cost_day': optimized_daily,
                'peak_kw': peak_kw,
                'energy_kwh': energy_kwh,
                'cost_per_kwh': _rate(energy_cost, energy_kwh),
                'monthly': _monthly(optimized_daily, peak_kw),
            },
            'baseline': {
                'energy_cost_day': baseline_daily,
                'peak_kw': base['peak_kw'],
                'energy_kwh': base['energy_kwh'],
                'cost_per_kwh': _rate(base['energy_cost'], base['energy_kwh']),
                'monthly': _monthly(baseline_daily, base['peak_kw']),
            },
        }
        saved = self.summary['baseline']['monthly'] - self.summary['optimized']['monthly']
        self.summary['monthly_saving'] = saved
        self.summary['monthly_saving_pct'] = (
            100 * saved / self.summary['baseline']['monthly']
            if self.summary['baseline']['monthly'] > 0 else 0.0)

        path = os.path.join(os.getcwd(), "chargeopt", "outputs")
        os.makedirs(path, exist_ok=True)

        pd.DataFrame(schedule).set_index(['bus', 'time']).to_csv(f'{path}/{filename}.csv')
        pd.DataFrame(assignments).set_index(['bus', 'day', 'route']).to_csv(
            f'{path}/assignments_{filename}.csv')

        results_file = f'{path}/results.csv'
        results_df = pd.DataFrame(columns=[
            "case_name", "numBuses", "ebMaxKwh", "numChargers", "chargerPower",
            "chargerEff", "routes", "gridMaxPower", "obj_val", "sol_time", "date", "type",
        ])
        try:
            results_df = pd.concat([pd.read_csv(results_file), results_df], ignore_index=True)
        except FileNotFoundError:
            pass
        results_df = pd.concat([results_df, pd.DataFrame([{
            "case_name": filename, "numBuses": B, "ebMaxKwh": eB_max,
            "numChargers": numChargers, "chargerPower": pCB_ub, "routes": str(routes),
            "gridMaxPower": gridKWH, "obj_val": cost, "sol_time": round(sol_time, 2),
            "date": datetime.now().strftime("%m/%d/%Y"),
        }])], ignore_index=True)
        results_df.to_csv(results_file, index=False)

        if unfilled_count:
            per_day = '; '.join(f"day {d}: {', '.join(missed[d])}" for d in sorted(missed))
            covered = (f" - covered {asked - unfilled_count} of {asked} block-days, "
                       f"no bus for {per_day}")
        else:
            covered = f" - all {asked} block-days covered"

        status = ("Optimal solution found" if all_optimal
                  else f"Stopped at {TIME_LIMIT_SECONDS}s with a feasible solution")
        return status + covered + excluded_note, startTimeNum
