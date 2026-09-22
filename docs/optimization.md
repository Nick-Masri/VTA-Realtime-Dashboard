# Charge scheduling: formulation and solve

How `chargeopt/` decides which bus runs which block and when each bus charges.
Written against `chargeopt/optimization.py` (463 lines) and `chargeopt/helpers.py`.

## What it decides

Given a set of buses with current state of charge, a set of daily service blocks
with known mileage and clock times, and a depot with a fixed number of identical
chargers, produce a three-day plan that:

1. covers as many block-days as possible, then
2. among the plans achieving that coverage, minimises the electricity bill —
   time-of-use energy **plus the demand charge on peak grid draw**.

Coverage and cost are ranked, not weighted. That ordering is deliberate and is
enforced by the two-pass solve described below.

Time is discretised into 15-minute quarters (`dt = 0.25` h). A day is 96
quarters; the horizon is `DAYS = 3`.

## Why the solver changed

The model was originally written for Gurobi under a WLS academic licence. That
licence expired and is not renewable, and Gurobi's free tier caps at 2,000
variables against roughly 17,000 binaries at fleet scale, so the Optimization tab
could not run at all.

It now runs on **Pyomo** with the **APPSI HiGHS** backend, which keeps the solver
in-process rather than writing an LP file per solve. HiGHS is open source, and
slower than Gurobi on a model this size, which is why the solve is time-bounded
and returns its best incumbent rather than insisting on proven optimality.

Two changes were forced by the move:

**One constraint was not linear.** (Since removed outright — see *Charging
behaviour* — but it is why the port was not a drop-in.) The original required

```
powerCB*dt + M*(1 - chargerUse) >= (eB_max - eB) * tracker
```

whose right-hand side multiplies a continuous variable by a binary. Gurobi
accepted it; HiGHS is linear only. Because the multiplier is binary the product
has an exact linearization — a second big-M that relaxes the row when `tracker`
is 0, which is all the product was doing. See *Charging behaviour* below.

**Big-M is derived per constraint** rather than a blanket 1000: `352` to fill the
pack (`eB_range`), `49` for charger output (`pCB_ub`), `12.25` for one interval's
energy (`pCB_ub*dt`), `339.75` for the upper tracker bound. The charger-output row
tightens twentyfold, which matters far more to HiGHS than it did to Gurobi.

## Data and parameters

From `chargeopt/config.yml`:

| Symbol | Value | Meaning |
|---|---|---|
| `eB_max` | 440 kWh | usable pack |
| `eB_min` | 88 kWh | 20% reserve floor (`0.2 * eB_max`) |
| `eB_range` | 352 kWh | `eB_max - eB_min` |
| `pCB_ub` | 49 kW | per-charger rated output |
| `gridKWH` | 500 kW | depot grid ceiling |
| `chargerEff` | 0.94 | charger efficiency, applied in the energy balance |
| `demandChargePerKw` | 20.0 | $/kW of monthly peak — **set from the real tariff** |
| `numChargers` | len(chargers) | identical, interchangeable |

**Block energy comes from the MAPIE consumption model**, per bus, via
`chargeopt/consumption.py`. Two consequences:

- Consumption is per *(coach, block)*, not per block. The coach is a model
  feature and the fleet separates by a few percent on identical mileage. The
  energy term stays linear — still a constant multiplying the assignment
  binary — so this costs the solver nothing.
- `CONSUMPTION_MODE` selects what is planned against:

| Mode | Basis | Effect |
|---|---|---|
| `interval` (default) | upper end of a `1 - CONSUMPTION_ALPHA` conformal band (α = 0.1) | plan survives any day below roughly the 95th percentile of consumption |
| `point` | the model's point prediction | roughly half of days exceed it |
| `fixed` | flat 2.5 kWh/mile | the original behaviour |

Measured on a 4-bus, 3-block case: flat $4,414/month, point $4,538, interval
$5,259. Robustness costs about 19% because the plan buys 17% more energy — it
is a real trade, not a free upgrade. Predictions come back as a percentage of
pack capacity and are converted with `eB_max`.

If the model cannot be scored — missing pickle, non-numeric coach id, weather
lookup failure — it falls back to the flat rate and *says so* in the summary
rather than planning silently on a different basis.

Grid price is a hardcoded summer-weekday TOU curve (`helpers.init_grid_pricing`):

| Window | $/kWh |
|---|---|
| 12:00–18:00 (peak) | 0.59002 |
| 08:30–12:00, 18:00–21:30 (partial) | 0.29319 |
| otherwise (off-peak) | 0.22161 |

## Decision variables

Per bus `b`, quarter `i`, block `r`:

| Variable | Domain | Meaning |
|---|---|---|
| `eB[b,i]` | `[eB_min, eB_max]` | energy in the pack |
| `powerCB[b,i]` | `[0, pCB_ub]` | power reaching the pack |
| `gridPowToB[b,i]` | `[0, pCB_ub/eff]` | power drawn at the meter |
| `peak` | `[0, gridKWH]` | highest depot draw over the window |
| `chargerUse[b,i]` | binary | bus is plugged in |
| `assignment[b,r]` | binary | bus `b` runs block `r` |
| `unserved[r]` | binary | block `r` is not run |
| `charging[b]` | binary | bus charges at all this window |
| `T1, T2, change[b,i]` | binary | charging-session transitions |

## Constraints

**Battery dynamics.** Energy carries forward, gains what was charged in the
previous interval, and loses a block's full energy at the quarter the bus
returns:

```
eB[b,i] = eB[b,i-1] + dt*powerCB[b,i-1] - Σ_r eRoute[r]*assignment[b,r]   (r returning at i)
```

**Departure readiness.** A bus must hold the reserve plus the whole block's
energy at the moment it pulls out:

```
eB[b,i] >= eB_min + Σ_r eRoute[r]*assignment[b,r]                         (r departing at i)
```

**Coverage.** Each block is run by exactly one bus or explicitly marked
unserved; a bus runs at most one block per window:

```
Σ_b assignment[b,r] + unserved[r] = 1
Σ_r assignment[b,r] <= 1
Σ_r unserved[r] = 0            (hard, in the first pass only)
```

**A bus cannot charge while out on its block.** For every quarter between a
block's departure and return:

```
chargerUse[b,i] + assignment[b,r] <= 1
```

**Depot capacity and metering.** Simultaneous plug-ins cannot exceed the charger
count, total draw cannot exceed the grid ceiling, and the depot is billed for
what it *draws* while the pack receives `eff` of it:

```
Σ_b chargerUse[b,i] <= numChargers
Σ_b gridPowToB[b,i] <= gridKWH
powerCB[b,i] = eff * gridPowToB[b,i]
Σ_b gridPowToB[b,i] <= peak                  (defines the billed peak)
```

**Charging-session structure.** `change[b,i]` marks a plug-in or unplug event.
Sessions are capped and given a minimum length so the plan is operationally
realistic rather than a scatter of one-quarter top-ups:

```
change[b,i] = T1[b,i] + T2[b,i]
T1[b,i] - T2[b,i] = chargerUse[b,i] - chargerUse[b,i-1]
Σ_i change[b,i] <= 2 * CHARGE_WINDOWS_PER_DAY        (= 4 transitions)
Σ_i chargerUse[b,i] >= 4 * charging[b]               (>= 1 hour if it charges at all)
```

`CHARGE_WINDOWS_PER_DAY = 2` matters more than it looks. With one stretch, a bus
can recharge after pull-in *or* top up before pull-out, but not both — and a bus
starting low needs both to get back to where it began. That single constant took
a ten-bus case from 5 of 16 block-days covered to 16 of 16.

**Charging behaviour.** Power is free between zero and rated whenever the bus is
plugged in — `powerCB[b,i] <= pCB_ub * chargerUse[b,i]` and nothing more.

It was not always. The original model pinned power at rated output through a
`tracker` / `tracker_b` binary pair selecting between "draw full power" and "top
up to exactly full", which is where the non-linear row came from. That was
removed for two reasons. It forbade the only lever that actually shaves a peak —
if every plugged-in bus must draw 49 kW, the sole control is which buses are
plugged in when. And it cost two binaries per bus per quarter: dropping them
takes roughly 1,920 binaries out of a ten-bus window, which took that case from
110–125s to **23s, solved to optimality**.

**Terminal condition.** `END_SOC_MODE` selects what each bus must hold at the end
of the horizon:

| Mode | Target | Note |
|---|---|---|
| `start` (default) | at least its starting SOC | repeatable — the plan can be re-run tomorrow from the same state |
| `reserve` | the 20% floor | cheapest and easiest to solve, but the fleet ends flatter than it started |
| `fraction` | `END_SOC_FRACTION` of the pack | a fixed readiness target; looser than `start` for a bus that began high, tighter for one that began low |

This is the binding constraint on a partly discharged fleet — not the starting
charge itself. A low bus must top up before its route and again after to return
to where it began: two windows, four transitions.

## Objective

```
minimise   dt * Σ_i price[i] * Σ_b gridPowToB[b,i]      (time-of-use energy)
         + (demandChargePerKw / 30) * peak              (demand charge)
```

A monthly demand charge is levied once, on a single peak, so a plan meant to
repeat daily carries a thirtieth of it per day. At that weight the two terms
land in the same order of magnitude and genuinely trade off; at the full monthly
rate the peak term swamps energy by roughly twenty to one.

## Baseline comparison

`chargeopt/baseline.py` simulates **charge-on-arrival** — the benchmark the
literature reports against. Every bus plugs in the moment it is back on the yard
and draws rated power until full, ignoring price; chargers go to the earliest
return first, capped by charger count and by what the feeder carries.

It is given **the same block assignments the optimizer chose**, so the
comparison isolates when and how fast each plan charges rather than mixing in
different duties.

One asymmetry is reported rather than hidden: charge-on-arrival fills every pack
to 100%, while the plan charges only to its end-of-horizon target. It therefore
buys more energy *as well as* buying it at worse moments. Both kWh delivered and
the rate paid per kWh are surfaced, and the rate is the like-for-like number —
it is what the time-of-use shifting earns on its own.

## How it is solved

### Rolling horizon, one day at a time

The three-day plan was originally one model over 288 quarters, roughly seventeen
thousand binaries at fleet scale. Requiring service on all three days pushed it
past what HiGHS could find: ten buses against eight blocks covered **1 of 16**
block-days, and raising the coverage budget from 90s to 240s changed nothing.

It is now **three models of 96 quarters**, solved in sequence, each bus's ending
charge carried into the next day as its opening charge.

Windows are anchored to the **operating day** (`DAY_START = 12`, i.e. 03:00), not
to the moment the plan is built. Anchored to "now", a block starting more than a
few hours out has its return fall past the window's end and gets dropped —
covering nothing at all. Anchored to the small hours, a pull-out and the night
that recharges for it sit inside the same window, so an overnight top-up is never
split across a boundary.

Quarters already in the past when the plan is built are **frozen**: charge is
pinned at its held value and no charging can be scheduled into them.

A block is only offered if it can actually be run — one that pulled out before
the plan starts cannot be crewed now, and one returning past the window's end
would never have its energy deducted. Blocks needing more than `eB_range` on one
charge are screened out entirely and reported, since no bus could ever run them.

### Two passes: coverage, then cost

Within each window:

1. **Coverage, hard.** Minimise `Σ unserved` with `Σ unserved = 0` also imposed.
   Budget: `COVERAGE_SHARE = 0.45` of the window's time.
2. **Coverage, soft.** If that found no incumbent, drop the hard equality, seed a
   *do-nothing* schedule (nothing runs, nothing charges, charge holds — feasible
   by inspection) as a warm start, and re-solve.
3. **Freeze coverage.** Add `Σ unserved <= (whatever was achieved)`.
4. **Cost.** Deactivate the coverage objective, activate electricity cost, and
   re-solve warm-started for the remaining budget.

Minimising the unserved count *directly* rather than constraining it was
measurably worse: a ten-bus run left 7 of 8 blocks unserved when minimised, and
served all 8 when constrained. Freezing coverage before the cost pass also means
the reported MIP gap measures **cost**, not a blended coverage term.

The soft-coverage binary is what keeps a bad input from destroying the whole run.
Coverage used to be a hard equality, so one block no bus could take made the
entire model infeasible — the operator got "Model is infeasible", no schedule,
and no indication which block was at fault.

### Time budgeting

`TIME_LIMIT_SECONDS = 300` for the whole three-day solve. Each window gets
`remaining / (days left)`, floored at 10s. `MIP_GAP = 0.03`. HiGHS is pushed well
past its default heuristic effort (`mip_heuristic_effort = 0.5`) because the
binding difficulty here is finding *any* feasible schedule, not closing the gap.

The ceiling is 300s rather than 180s because the ten-bus fleet lands around
110–125s but moves with machine load — one run in five reached 180s with no
incumbent at all.

### What comes back

A status string, parsed by `is_solved()` / `is_partial()` rather than compared
literally, so it can carry caveats without the results view falling through to
nothing. It reports block-days covered out of asked, names the blocks nobody
could run and on which day, and flags any excluded as beyond range. Schedules and
assignments are written to `chargeopt/outputs/`, with a running `results.csv` log
of case size, objective and solve time.

## Known limits

Honest list of what the model does *not* currently capture:

- **One block per bus per window.** `Σ_r assignment[b,r] <= 1` forbids a bus
  running two blocks in a day.
- **The demand charge is a flat $/kW on the horizon peak.** Real tariffs often
  distinguish on-peak from any-time demand and measure over 15-minute intervals
  within a billing month; this prices one peak over a three-day plan.
- **Chargers are identical and interchangeable**, modelled as a count.
- **No CC/CV taper**, temperature effect, or battery degradation; a pack accepts
  rated power at any state of charge.
- **Prices are a hardcoded summer weekday**, not a live tariff, and identical
  across all three days.
- **Consumption uncertainty is handled by a quantile, not a distribution.**
  Planning against an upper conformal bound is a robust point estimate; it is
  not a stochastic program, and it does not price the cost of a block failing.
- **The model is scored once, for today's weather**, and the same energy figure
  is used for all three days of the horizon.
- **The baseline is a simulation, not a second optimization.** It is a fair
  representation of unmanaged charging, not of a competently hand-built
  schedule.
