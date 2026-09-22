"""Charge-on-arrival: what the depot costs with no scheduling at all.

The benchmark the literature reports optimized charging against. Every bus
plugs in as soon as it is back on the yard and draws rated power until the
pack is full, regardless of price. Chargers are handed out earliest-return
first and the number in use at once is capped by the charger count and by
what the service can carry.

It is deliberately given the same block assignments the optimizer chose, so
the comparison isolates *when and how fast* each plan charges rather than
mixing in a different set of duties.

One asymmetry is worth stating rather than hiding: this fills every pack to
100%, while the optimized plan charges only as far as its end-of-horizon
target. Uncontrolled charging therefore buys more energy as well as buying it
at worse moments, so both kWh delivered and cost are reported and the two
should be read together.
"""


def charge_on_arrival(soc_at_start, windows, energy, prices, sizes, window_len):
    """Returns cost, peak draw and energy delivered for the unmanaged policy."""
    (B, eB_max, eB_min, eB_range, pCB_ub, gridKWH,
     numChargers, dt, eff, demand_rate) = sizes

    eB = {b: eB_max * soc_at_start[b] for b in range(B)}
    # Rated draw per charger at the meter, and how many the feeder can carry.
    per_charger_draw = pCB_ub / eff
    concurrent = max(1, min(numChargers, int(gridKWH // per_charger_draw)))

    energy_cost = 0.0
    peak_kw = 0.0
    energy_kwh = 0.0

    for w0, frozen, placed, served in windows:
        drops = {}
        busy = {}
        back_at = {b: 0 for b in range(B)}
        for r, (start, end) in placed.items():
            for b in served.get(r, []):
                drops.setdefault(end, []).append((b, float(energy[(b, r)])))
                busy.setdefault(b, set()).update(range(start, end + 1))
                back_at[b] = end

        for i in range(window_len):
            for b, kwh in drops.get(i, []):
                eB[b] -= kwh

            # The stretch already in the past when the plan was built is not
            # available to either policy.
            if i < frozen:
                continue

            waiting = [b for b in range(B)
                       if i not in busy.get(b, ()) and eB[b] < eB_max - 1e-6]
            waiting.sort(key=lambda b: (back_at[b], b))

            draw = 0.0
            for b in waiting[:concurrent]:
                to_pack = min(pCB_ub, (eB_max - eB[b]) / dt)
                eB[b] += to_pack * dt
                draw += to_pack / eff

            energy_cost += dt * prices[w0 + i] * draw
            energy_kwh += dt * draw
            peak_kw = max(peak_kw, draw)

    return {
        'energy_cost': energy_cost,
        'peak_kw': peak_kw,
        'energy_kwh': energy_kwh,
        'cost': energy_cost + demand_rate * peak_kw,
        'end_soc': {b: eB[b] / eB_max for b in range(B)},
    }
