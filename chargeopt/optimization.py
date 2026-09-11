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

from chargeopt.helpers import init_grid_pricing, init_routes, time_to_quarter

warnings.simplefilter(action='ignore', category=FutureWarning)

# HiGHS is open source and slower than Gurobi on a model this size, so the
# solve is bounded and any incumbent found by then is used. The full ten-bus
# fleet lands around 110-125s but varies with machine load - one run in five
# reached 180s with nothing - so the ceiling carries real headroom.
TIME_LIMIT_SECONDS = 300
MIP_GAP = 0.03

# The binding difficulty here is finding any feasible schedule, not closing the
# gap, so HiGHS is pushed well past its default heuristic effort of 0.05.
# The original capped charger transitions at 2 across the entire run, which over
# D=3 days forces one contiguous charging window for the whole horizon rather
# than one per night. That reading left a 4-bus, 3-route case at mixed starting
# SOC without any feasible solution after 600s; per-day it proves optimal in
# about 16.
#
# 'horizon' is workable when buses start at or near a full pack: a bus that
# starts full needs no pre-route top-up, so one window after its route is
# enough, and the whole ten-bus fleet then solves to optimality in about two
# minutes. Start a bus low enough that it must charge before its route as well
# as after, and one window can no longer cover both.
CHANGE_CAP_SCOPE = 'day'

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

# When some block cannot be covered by any selected bus, drop it and solve for
# the rest rather than returning nothing. The dropped blocks are named in the
# status so the schedule is never quietly partial.
DROP_UNCOVERABLE_BLOCKS = True

# Statuses that mean a schedule was written. Callers test with is_solved rather
# than comparing strings, so the wording can carry caveats - a dropped block, a
# remaining gap - without the results view falling through to nothing.
SOLVED_PREFIXES = ('Optimal solution found', 'Stopped at')


def is_solved(status):
    return bool(status) and str(status).startswith(SOLVED_PREFIXES)


def is_partial(status):
    """Solved, but with something the operator needs to know about."""
    return is_solved(status) and ('dropped' in str(status) or str(status).startswith('Stopped'))

HIGHS_OPTIONS = {
    'mip_heuristic_effort': 0.5,
    'mip_detect_symmetry': True,
    'presolve': 'on',
}


def _can_cover(start_kwh, route_kwh, eB_min, eB_max):
    """Whether a bus holding start_kwh could take a route needing route_kwh.

    A horizon-wide transition cap gives each bus a single charging window. If
    the end-of-horizon target needs charge the bus does not already have, that
    window is spent restoring it after the route, so the bus has to leave on
    what it is holding. Under an end target of the reserve floor nothing has to
    be restored - eB never drops below it anyway - which frees the window for a
    pre-route top-up and leaves only the pack size binding, as with per-day
    windows.
    """
    window_spent_on_end_target = (
        CHANGE_CAP_SCOPE == 'horizon' and END_SOC_MODE in ('start', 'fraction')
    )
    if window_spent_on_end_target:
        return start_kwh >= eB_min + route_kwh
    return eB_max >= eB_min + route_kwh


def _max_matching(capable):
    """Largest set of blocks assignable to distinct buses.

    Each bus takes at most one route per day, so coverage is a bipartite
    matching rather than a per-block test: a block only counts as coverable if
    a bus is free for it once the other blocks are served too.
    """
    match_bus = {}
    match_route = {}

    def assign(route, seen):
        for bus in capable[route]:
            if bus in seen:
                continue
            seen.add(bus)
            if bus not in match_bus or assign(match_bus[bus], seen):
                match_bus[bus] = route
                match_route[route] = bus
                return True
        return False

    for route in sorted(capable, key=lambda r: len(capable[r])):
        assign(route, set())
    return match_route


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


class ChargeOpt:
    def __init__(self, buses, routes, chargers):
        self.buses = buses
        self.routes = routes
        self.chargers = chargers
        self.startTime = datetime.now()

    def solve(self):
        startTimeNum = time_to_quarter(self.startTime.strftime('%I:%M %p'))

        B = len(self.buses)
        if B == 0:
            return "No buses selected", startTimeNum

        routes = self.routes
        R = len(routes)
        if R == 0:
            return "No blocks selected", startTimeNum

        #####################################
        # Config
        #####################################
        config_path = os.path.join(os.getcwd(), "chargeopt/config.yml")
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        current_datetime = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
        filename = f'chargeopt_{current_datetime}'

        eB_max = config["ebMaxKwh"]
        eB_min = int(eB_max * .2)
        eB_range = eB_max - eB_min

        numChargers = len(self.chargers)
        pCB_ub = config["chargerPower"]
        gridKWH = config['gridMaxPower']

        D = 3
        dt = 0.25
        T = D * 96
        optimized_time = [t for t in range(startTimeNum, T)]

        [departure, arrival, eRoute, report] = init_routes(routes, eB_range, pCB_ub)
        if report != 'All Clear':
            return report, startTimeNum

        block_labels = [str(x) for x in routes['block_id']] if 'block_id' in routes else [
            str(i) for i in range(len(routes))]

        # A bus starting below the 20% floor cannot satisfy eB's lower bound,
        # which otherwise surfaces as a bare "infeasible".
        start_soc = {b: _soc_fraction(self.buses.iloc[b, 1]) for b in range(B)}
        too_low = [
            str(self.buses.iloc[b, 0]) for b in range(B)
            if eB_max * start_soc[b] < eB_min
        ]
        if too_low:
            return (
                f"Below the {eB_min / eB_max:.0%} reserve at start: "
                f"{', '.join(too_low)}"
            ), startTimeNum

        #####################################
        # Coverage screen
        #####################################
        # Every selected block has to be run by some bus, so one block nothing
        # can take makes the whole model infeasible. Screening first turns that
        # into a named block instead of a solver shrug.
        start_kwh = {b: eB_max * start_soc[b] for b in range(B)}
        capable = {
            r: {b for b in range(B)
                if _can_cover(start_kwh[b], eRoute[r], eB_min, eB_max)}
            for r in range(R)
        }
        matched = _max_matching(capable)
        uncoverable = [r for r in range(R) if r not in matched]

        dropped_note = ''
        if uncoverable:
            names = ', '.join(block_labels[r] for r in uncoverable)
            if not DROP_UNCOVERABLE_BLOCKS:
                return (
                    f"No bus can cover block(s) {names} on its starting charge"
                ), startTimeNum

            keep = [r for r in range(R) if r in matched]
            if not keep:
                return (
                    "None of the selected blocks can be covered by these buses"
                ), startTimeNum

            departure = np.asarray(departure)[keep]
            arrival = np.asarray(arrival)[keep]
            eRoute = np.asarray(eRoute)[keep]
            R = len(keep)
            dropped_note = f" - dropped block(s) {names}"

        tDep = np.zeros((R, D), dtype=int)
        tRet = np.zeros((R, D), dtype=int)
        for d in range(D):
            for r in range(R):
                # the time is one less than the matlab time
                tDep[r, d] = int(departure[r] - 1 + d * 96)
                tRet[r, d] = int(arrival[r] - 1 + d * 96)

        tDay = np.zeros((D, 96), dtype=int)
        for d in range(D):
            tDay[d, :] = np.arange(d * 96, (d + 1) * 96)

        gridPowAvail = gridKWH
        gridPowPrice = init_grid_pricing(D)

        #####################################
        # Model
        #####################################
        m = pyo.ConcreteModel()
        m.B = pyo.RangeSet(0, B - 1)
        m.T = pyo.RangeSet(0, T - 1)
        m.D = pyo.RangeSet(0, D - 1)
        m.R = pyo.RangeSet(0, R - 1)
        m.OT = pyo.Set(initialize=optimized_time, ordered=True)

        m.powerCB = pyo.Var(m.B, m.T, bounds=(0, pCB_ub))
        m.gridPowToB = pyo.Var(m.B, m.T, bounds=(0, gridKWH))
        m.eB = pyo.Var(m.B, m.T, bounds=(eB_min, eB_max))

        m.chargerUse = pyo.Var(m.B, m.T, domain=pyo.Binary)
        m.T1 = pyo.Var(m.B, m.T, domain=pyo.Binary)
        m.T2 = pyo.Var(m.B, m.T, domain=pyo.Binary)
        m.change = pyo.Var(m.B, m.T, domain=pyo.Binary)
        m.charging = pyo.Var(m.B, m.D, domain=pyo.Binary)
        m.tracker = pyo.Var(m.B, m.T, domain=pyo.Binary)
        m.tracker_b = pyo.Var(m.B, m.T, domain=pyo.Binary)
        m.assignment = pyo.Var(m.B, m.D, m.R, domain=pyo.Binary)

        #####################################
        # Big-M constants
        #####################################
        # Each is the smallest value that still relaxes its own constraint.
        # A single blanket M weakens the LP relaxation, which matters far more
        # to an open-source branch-and-bound than it did to Gurobi.
        M_fill = eB_range                    # charge needed to fill the pack
        M_power = pCB_ub                     # charger output
        M_low = pCB_ub * dt                  # energy one interval can deliver
        M_high = eB_range - pCB_ub * dt

        #####################################
        # Charging constraints
        #####################################
        m.change_link = pyo.Constraint(
            m.B, m.T, rule=lambda m, b, t: m.change[b, t] == m.T1[b, t] + m.T2[b, t])

        def _init_zero(var):
            return pyo.Constraint(
                m.B, pyo.RangeSet(0, startTimeNum - 1),
                rule=lambda m, b, t: var[b, t] == 0)

        m.T1_init = _init_zero(m.T1)
        m.T2_init = _init_zero(m.T2)

        after_start = pyo.RangeSet(1, T - 1)
        m.use_link_1 = pyo.Constraint(
            m.B, after_start,
            rule=lambda m, b, t: m.T1[b, t] - m.T2[b, t]
            == m.chargerUse[b, t] - m.chargerUse[b, t - 1])
        m.use_link_2 = pyo.Constraint(
            m.B, after_start,
            rule=lambda m, b, t: m.change[b, t]
            <= m.chargerUse[b, t - 1] + m.chargerUse[b, t])
        m.use_link_3 = pyo.Constraint(
            m.B, after_start,
            rule=lambda m, b, t: m.change[b, t]
            <= 2 - m.chargerUse[b, t - 1] - m.chargerUse[b, t])

        if CHANGE_CAP_SCOPE == 'day':
            m.change_cap = pyo.Constraint(
                m.B, m.D, rule=lambda m, b, d:
                sum(m.change[b, int(t)] for t in tDay[d]) <= 2)
        else:
            m.change_cap = pyo.Constraint(
                m.B, rule=lambda m, b: sum(m.change[b, t] for t in m.T) <= 2)
        m.daily_min = pyo.Constraint(
            m.B, m.D, rule=lambda m, b, d:
            sum(m.chargerUse[b, int(t)] for t in tDay[d]) >= 4 * m.charging[b, d])
        m.daily_max = pyo.Constraint(
            m.B, m.D, rule=lambda m, b, d:
            sum(m.chargerUse[b, int(t)] for t in tDay[d]) <= 96 * m.charging[b, d])

        m.power_gate = pyo.Constraint(
            m.B, m.T,
            rule=lambda m, b, t: m.powerCB[b, t] <= pCB_ub * m.chargerUse[b, t])

        # When charging, deliver at least what is needed to fill the pack.
        # Gurobi accepted the original (eB_max - eB) * tracker product; that is
        # bilinear, so it is switched here for the exact linearization a binary
        # multiplier allows - a second big-M that relaxes the row when
        # tracker is 0, which is all the product did.
        m.fill_rule = pyo.Constraint(
            m.B, m.OT,
            rule=lambda m, b, t: m.powerCB[b, t] * dt
            + M_fill * (1 - m.chargerUse[b, t])
            + M_fill * (1 - m.tracker[b, t])
            >= eB_max - m.eB[b, t])
        # ... or run the charger flat out if more than that is needed
        m.full_power_rule = pyo.Constraint(
            m.B, m.OT,
            rule=lambda m, b, t: m.powerCB[b, t] + M_power * (1 - m.chargerUse[b, t])
            >= pCB_ub * m.tracker_b[b, t])

        m.tracker_low = pyo.Constraint(
            m.B, m.OT,
            rule=lambda m, b, t: (eB_max - m.eB[b, t])
            >= (pCB_ub * dt) - M_low * m.tracker[b, t])
        m.tracker_high = pyo.Constraint(
            m.B, m.OT,
            rule=lambda m, b, t: (eB_max - m.eB[b, t])
            <= (pCB_ub * dt) + M_high * m.tracker_b[b, t])
        m.tracker_pick = pyo.Constraint(
            m.B, m.T,
            rule=lambda m, b, t: m.tracker[b, t] + m.tracker_b[b, t] == 1)

        m.charger_count = pyo.Constraint(
            m.T, rule=lambda m, t: sum(m.chargerUse[b, t] for b in m.B) <= numChargers)

        #####################################
        # Power availability
        #####################################
        m.grid_total = pyo.Constraint(
            m.T, rule=lambda m, t: sum(m.gridPowToB[b, t] for b in m.B) <= gridPowAvail)
        m.charger_supply = pyo.Constraint(
            m.B, m.T, rule=lambda m, b, t: m.powerCB[b, t] == m.gridPowToB[b, t])

        #####################################
        # Bus battery operation
        #####################################
        m.battery = pyo.ConstraintList()
        for b in range(B):
            for d in range(D):
                for i in range(96):
                    if d == 0 and i == 0:
                        continue
                    t = int(tDay[d][i])
                    depletion = sum(
                        eRoute[r] * m.assignment[b, d, r]
                        for r in range(R) if t == tRet[r][d]
                    )
                    m.battery.add(
                        m.eB[b, t] == m.eB[b, t - 1] + dt * m.powerCB[b, t - 1] - depletion)

        m.route_requirement = pyo.ConstraintList()
        for b in range(B):
            for d in range(D):
                for i in range(96):
                    t = int(tDay[d][i])
                    requirement = sum(
                        eRoute[r] * m.assignment[b, d, r]
                        for r in range(R) if t == tDep[r][d]
                    )
                    m.route_requirement.add(m.eB[b, t] >= eB_min + requirement)

        m.soc_bounds = pyo.ConstraintList()
        for b in range(B):
            soc = start_soc[b]
            for t in range(startTimeNum):
                m.soc_bounds.add(m.eB[b, t] == eB_max * soc)
            m.soc_bounds.add(m.eB[b, T - 1] >= _end_target(soc, eB_max, eB_min))

        #####################################
        # Route coverage
        #####################################
        m.coverage = pyo.ConstraintList()
        for b in range(B):
            for d in range(D):
                for r in range(R):
                    for t in range(int(tDep[r][d]), int(tRet[r][d]) + 1):
                        m.coverage.add(m.chargerUse[b, t] + m.assignment[b, d, r] <= 1)

        m.route_covered = pyo.Constraint(
            m.R, pyo.RangeSet(1, 1),
            rule=lambda m, r, d: sum(m.assignment[b, d, r] for b in m.B) == 1)
        m.one_route_each = pyo.Constraint(
            m.B, m.D,
            rule=lambda m, b, d: sum(m.assignment[b, d, r] for r in m.R) <= 1)

        m.time_shift = pyo.ConstraintList()
        for b in range(B):
            for t in range(startTimeNum):
                m.time_shift.add(m.powerCB[b, t] == 0)
                m.time_shift.add(m.gridPowToB[b, t] == 0)
                m.time_shift.add(m.chargerUse[b, t] == 0)

        #####################################
        # Objective
        #####################################
        m.obj = pyo.Objective(
            expr=0.25 * sum(
                gridPowPrice[t] * sum(m.gridPowToB[b, t] for b in range(B))
                for t in range(T)
            ),
            sense=pyo.minimize,
        )

        #####################################
        # Solve
        #####################################
        solver = Highs()
        solver.config.time_limit = TIME_LIMIT_SECONDS
        solver.config.mip_gap = MIP_GAP
        solver.config.load_solution = False
        solver.config.stream_solver = False
        for option, value in HIGHS_OPTIONS.items():
            solver.highs_options[option] = value

        began = time.time()
        result = solver.solve(m)
        sol_time = time.time() - began

        terminal = result.termination_condition
        has_solution = result.best_feasible_objective is not None

        if terminal == TerminationCondition.infeasible:
            return "Model is infeasible" + dropped_note, startTimeNum
        if not has_solution:
            if terminal == TerminationCondition.maxTimeLimit:
                return (
                    f"No solution found within {TIME_LIMIT_SECONDS}s" + dropped_note
                ), startTimeNum
            return "Model Error" + dropped_note, startTimeNum

        result.solution_loader.load_vars()
        obj_val = float(result.best_feasible_objective)

        #####################################
        # Exporting results
        #####################################
        path = os.path.join(os.getcwd(), "chargeopt", "outputs")
        os.makedirs(path, exist_ok=True)

        def genDF(name, var):
            data = [
                {'time': t, 'bus': b, name: pyo.value(var[b, t])}
                for t in range(T) for b in range(B)
            ]
            df = pd.DataFrame(data)
            return df.set_index(['bus', 'time']) if len(df) > 0 else None

        twodim_df = pd.concat(
            [genDF('powerCB', m.powerCB), genDF('eB', m.eB),
             genDF('chargerUse', m.chargerUse)],
            axis=1, join='inner',
        )
        twodim_df.to_csv(f'{path}/{filename}.csv')

        assignment_df = pd.DataFrame([
            {'day': d, 'bus': b, 'route': r,
             'assignment': pyo.value(m.assignment[b, d, r])}
            for d in range(D) for b in range(B) for r in range(R)
        ]).set_index(['bus', 'day', 'route'])
        assignment_df.to_csv(f'{path}/assignments_{filename}.csv')

        results_file = f'{path}/results.csv'
        results_df = pd.DataFrame(columns=[
            "case_name", "numBuses", "ebMaxKwh", "numChargers", "chargerPower",
            "chargerEff", "routes", "gridMaxPower", "obj_val", "sol_time", "date", "type",
        ])
        try:
            results_df = pd.concat([pd.read_csv(results_file), results_df], ignore_index=True)
        except FileNotFoundError:
            pass

        new_row = pd.DataFrame([{
            "case_name": filename,
            "numBuses": B,
            "ebMaxKwh": eB_max,
            "numChargers": numChargers,
            "chargerPower": pCB_ub,
            "routes": str(routes),
            "gridMaxPower": gridKWH,
            "obj_val": obj_val,
            "sol_time": round(sol_time, 2),
            "date": datetime.now().strftime("%m/%d/%Y"),
        }])
        results_df = pd.concat([results_df, new_row], ignore_index=True)
        results_df.to_csv(results_file, index=False)

        if terminal == TerminationCondition.optimal:
            status = "Optimal solution found"
        else:
            bound = result.best_objective_bound
            gap = abs(obj_val - bound) / max(abs(obj_val), 1e-9) if bound is not None else None
            status = (
                f"Stopped at {TIME_LIMIT_SECONDS}s with a feasible solution"
                + (f" ({gap:.1%} gap)" if gap is not None else "")
            )

        return status + dropped_note, startTimeNum
