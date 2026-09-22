"""Block energy from the MAPIE consumption model, per bus.

The scheduler used a flat 2.5 kWh/mile for every bus on every block, while
the portal already shipped a trained model with conformal prediction
intervals. Two things change by using it.

Consumption is per *(coach, block)*, not per block: the model is fitted with
the coach as a feature and separates the fleet by a few percent on identical
mileage. The energy term stays linear - it is still a constant multiplying
the assignment binary - so this costs the solver nothing.

And the interval is what makes the plan robust rather than merely tuned. The
upper end of a (1 - alpha) conformal band is the consumption level the
schedule is built to survive; planning against the point prediction means
roughly half of all days break it.
"""

import numpy as np

FLAT_KWH_PER_MILE = 2.5


def block_energy(coaches, mileages, eB_max, mode='interval', alpha=0.1):
    """Energy each bus would need for each block.

    Returns ({(bus, block): kWh}, note) where note describes what was used, so
    a caller can say so rather than silently planning on a fallback.
    """
    miles = [float(m) for m in np.asarray(mileages).ravel()]
    flat = {(b, r): miles[r] * FLAT_KWH_PER_MILE
            for b in range(len(coaches)) for r in range(len(miles))}

    if mode == 'fixed':
        return flat, f"{FLAT_KWH_PER_MILE} kWh/mile, flat"

    try:
        from components.consumption_model import predict_batch

        pairs = [(coaches[b], miles[r])
                 for b in range(len(coaches)) for r in range(len(miles))]
        frame = predict_batch(pairs, alpha=alpha)
        column = 'pred' if mode == 'point' else 'high'
        # Predictions are a percentage of pack capacity.
        values = (frame[column].to_numpy() / 100.0) * eB_max
        if not np.all(np.isfinite(values)):
            raise ValueError('model returned a non-finite prediction')

        energy = {}
        k = 0
        for b in range(len(coaches)):
            for r in range(len(miles)):
                energy[(b, r)] = float(values[k])
                k += 1
    except Exception as exc:
        return flat, (f"{FLAT_KWH_PER_MILE} kWh/mile - the consumption model "
                      f"could not be scored ({type(exc).__name__})")

    if mode == 'point':
        return energy, "consumption model, point prediction"
    return energy, (f"consumption model, upper {1 - alpha:.0%} interval "
                    f"(about the {1 - alpha / 2:.0%} consumption level)")
