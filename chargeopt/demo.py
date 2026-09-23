"""Pre-computed scenarios, so a demo opens on results rather than a spinner.

A live solve is bounded at five minutes, which is a long time to hold a room.
These carry their own fixed fleet and their own saved answer: they load
instantly and are identical every time, which the live solver is not - it
stops on a 3% tolerance, so the same question can come back a percent or two
apart. The Submit button stays as proof the solver is real.

The portal's own fleet cannot be cached. It runs on simulated telemetry that
reseeds every minute, so a bundle keyed on it would never be reused.

Bundles are written as CSV and JSON rather than pickles: they are committed,
and a pickle would tie the repo to one pandas version.

Rebuild after changing the model:

    python -m chargeopt.demo
"""

import json
import os

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'demo_cache')
OUTPUTS = os.path.join(os.path.dirname(__file__), 'outputs')


def fleet():
    """The depot every demo scenario is run against."""
    buses = pd.DataFrame({
        'vehicle': ['7501', '7502', '7503', '7504', '9501', '9502'],
        'soc': ['82%', '61%', '94%', '45%', '73%', '88%'],
        'status': ['Idle', 'Idle', 'Charging', 'Idle', 'Idle', 'Charging'],
    })
    blocks = pd.DataFrame({
        'block_id': ['22-04', '23-11', '55-02', '60-07', '522-03'],
        'block_startTime': ['05:45 AM', '06:15 AM', '06:45 AM', '07:30 AM', '09:00 AM'],
        'block_endTime':   ['01:45 PM', '02:30 PM', '03:15 PM', '04:00 PM', '05:30 PM'],
        'Mileage': [96.0, 88.0, 112.0, 104.0, 78.0],
    })
    chargers = pd.DataFrame({
        'stationName': ['Station 1', 'Station 2', 'Station 3', 'Station 4'],
    })
    return buses, blocks, chargers


SCENARIOS = [
    {
        'slug': 'as-built',
        'label': 'The depot as it is',
        'blurb': 'Six buses, five blocks, four 49 kW chargers on the current tariff.',
        'scenario': {},
    },
    {
        'slug': 'two-more-chargers',
        'label': 'Two more chargers',
        'blurb': 'The same duties with six chargers instead of four.',
        'scenario': {'numChargers': 6},
    },
    {
        'slug': 'no-demand-charge',
        'label': 'Chasing cheap hours only',
        'blurb': 'Planned without pricing the peak, then billed for it anyway.',
        'scenario': {'price_demand': False},
    },
]


def _dir(slug):
    return os.path.join(CACHE_DIR, slug)


def load(slug):
    """The saved run, or None if it has not been built."""
    folder = _dir(slug)
    meta_path = os.path.join(folder, 'meta.json')
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path) as handle:
            meta = json.load(handle)
        return {
            'results': meta['results'],
            'startTimeNum': meta['startTimeNum'],
            'summary': meta['summary'],
            'label': meta['label'],
            'blurb': meta['blurb'],
            'built_at': meta.get('built_at', ''),
            'buses': pd.read_csv(os.path.join(folder, 'buses.csv'), dtype=str),
            'blocks': pd.read_csv(os.path.join(folder, 'blocks.csv')),
            'chargers': pd.read_csv(os.path.join(folder, 'chargers.csv'), dtype=str),
            'artifacts': {
                'results_row': meta['results_row'],
                'assignments': pd.read_csv(os.path.join(folder, 'assignments.csv')),
                'schedule': pd.read_csv(os.path.join(folder, 'schedule.csv')),
            },
        }
    except Exception:
        # A half-written or stale bundle must not take the page down with it.
        return None


def available():
    return [s for s in SCENARIOS if os.path.exists(os.path.join(_dir(s['slug']), 'meta.json'))]


def build(spec):
    """Solve one scenario and write its bundle. Returns the status string."""
    from chargeopt.optimization import ChargeOpt, is_solved

    buses, blocks, chargers = fleet()
    opt = ChargeOpt(buses.copy(), blocks.copy(), chargers.copy(),
                    scenario=spec['scenario'])
    status, start_quarter = opt.solve()
    if not is_solved(status) or not opt.summary:
        return status

    results_row = pd.read_csv(os.path.join(OUTPUTS, 'results.csv')).iloc[-1].dropna()
    case = results_row['case_name']

    folder = _dir(spec['slug'])
    os.makedirs(folder, exist_ok=True)
    buses.to_csv(os.path.join(folder, 'buses.csv'), index=False)
    blocks.to_csv(os.path.join(folder, 'blocks.csv'), index=False)
    chargers.to_csv(os.path.join(folder, 'chargers.csv'), index=False)
    pd.read_csv(os.path.join(OUTPUTS, f'assignments_{case}.csv')).to_csv(
        os.path.join(folder, 'assignments.csv'), index=False)
    pd.read_csv(os.path.join(OUTPUTS, f'{case}.csv')).to_csv(
        os.path.join(folder, 'schedule.csv'), index=False)

    with open(os.path.join(folder, 'meta.json'), 'w') as handle:
        json.dump({
            'label': spec['label'],
            'blurb': spec['blurb'],
            'results': status,
            'startTimeNum': int(start_quarter),
            'summary': opt.summary,
            'results_row': {k: (v.item() if hasattr(v, 'item') else v)
                            for k, v in results_row.to_dict().items()},
            'built_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),
        }, handle, indent=2, default=str)
    return status


def build_all():
    for spec in SCENARIOS:
        print(f"building {spec['slug']} ...", flush=True)
        print(f"  {build(spec)}", flush=True)


if __name__ == '__main__':
    build_all()
