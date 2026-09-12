"""Simulated live fleet data.

The Supabase project is reachable, but nothing has written to it since
07/15/2024 - the Proterra/Swiftly ingestion that fed it lives outside this
repo and stopped. These builders synthesise a current-looking fleet so the
portal stays a working demo, in the exact shapes `calls.supa_select` returns
after its own post-processing.

Timezone conventions here mirror what the real tables store:
  * `last_transmission` is naive UTC (callers localize it themselves)
  * `created_at` is tz-aware UTC
  * `predictedArrival` is Pacific wall time carrying a UTC offset, which is
    the quirk get_active_blocks strips and re-localizes
"""

import numpy as np
import pandas as pd

PACIFIC = 'US/Pacific'

# Seeded from the last real readings so odometers stay plausible.
_BASE_ODOMETER = {
    '7501': 44848, '7502': 52281, '7503': 31281, '7504': 57978, '7505': 66416,
    '9501': 8771, '9502': 4642, '9503': 5139, '9504': 15322, '9505': 3582,
}
COACHES = sorted(_BASE_ODOMETER)

_ROUTES = ['22', '23', '55', '60', '522']

BATTERY_KWH = 440
# What a 40ft battery bus actually consumes. The history view discards any
# block outside 1-4 kWh/mile as a bad reading, so the simulated drawdown is
# derived from mileage and one of these rather than drawn independently.
EFFICIENCY_RANGE = (1.9, 2.7)

# Proterra fault strings arrive asterisk-prefixed; the UI strips the asterisks.
_FAULTS = ['', '', '', '', '', '*Low Coolant Level', '*HVAC Derate', '*Door Sensor']
_DEPOT_LAT, _DEPOT_LON = 37.41875, -121.93600


def _rng(seed_source):
    return np.random.default_rng(abs(hash(seed_source)) % (2 ** 32))


def _now_pacific():
    return pd.Timestamp.now(tz=PACIFIC)


# Keeps the dashboard odometer and the history series on the same trajectory.
MILES_PER_SERVICE_DAY = 85


def _odometer(coach, at):
    """Drift the baseline forward at roughly a service day's mileage."""
    days = max(0.0, (at - pd.Timestamp('2024-07-15', tz=PACIFIC)).total_seconds() / 86400)
    return int(_BASE_ODOMETER[coach] + days * MILES_PER_SERVICE_DAY)


def in_service():
    """Coaches out on a block right now, rotating by hour."""
    now = _now_pacific()
    rng = _rng(f'service-{now.strftime("%Y-%m-%d-%H")}')
    picked = rng.choice(len(COACHES), size=4, replace=False)
    return {COACHES[int(i)]: _ROUTES[int(rng.integers(0, len(_ROUTES)))] for i in picked}


def mock_soc():
    """Latest reading per coach - mirrors supabase_soc()."""
    now = _now_pacific()
    serving = in_service()
    rng = _rng(f'soc-{now.strftime("%Y-%m-%d-%H-%M")}')
    rows = []

    for coach in COACHES:
        # A few minutes of jitter so readings look like independent telemetry.
        seen = now - pd.Timedelta(minutes=int(rng.integers(1, 9)))
        rows.append({
            'soc': int(rng.integers(35, 92)) if coach in serving else int(rng.integers(45, 99)),
            'vehicle': coach,
            'odometer': f"{_odometer(coach, now):,}",
            'status': 'Driving' if coach in serving else 'Idle',
            'last_transmission': seen.tz_convert('UTC').tz_localize(None),
            'created_at': seen.tz_convert('UTC'),
        })

    return pd.DataFrame(rows)


def mock_soc_history(vehicle=None, days=17):
    """Telemetry time series - mirrors supabase_soc_history()."""
    now = _now_pacific()
    coaches = [str(vehicle)] if vehicle is not None else COACHES
    rows = []

    for coach in coaches:
        if coach not in _BASE_ODOMETER:
            continue
        rng = _rng(f'history-{coach}-{now.strftime("%Y-%m-%d")}')
        efficiency = float(rng.uniform(*EFFICIENCY_RANGE))
        soc = float(rng.integers(80, 100))
        odo = _odometer(coach, now - pd.Timedelta(days=days))

        stamps = pd.date_range(now - pd.Timedelta(days=days), now, freq='30min', tz=PACIFIC)
        for stamp in stamps:
            hour = stamp.hour
            if 6 <= hour < 19:
                # In service. Charge follows the miles at this bus's
                # efficiency, so the reported kWh/mile is a real ratio.
                miles = float(rng.uniform(3.4, 4.6))
                odo += miles
                soc -= miles * efficiency / BATTERY_KWH * 100
            else:
                # Overnight at the yard, recovering the day's drawdown.
                soc += float(rng.uniform(2.0, 3.4))
            soc = float(np.clip(soc, 12, 100))

            rows.append({
                'soc': int(round(soc)),
                'vehicle': coach,
                'odometer': int(odo),
                'fault': str(rng.choice(_FAULTS)),
                'status': 'Driving' if 6 <= hour < 19 else 'Idle',
                'last_transmission': stamp.tz_convert('UTC').tz_localize(None),
                'created_at': stamp.tz_convert('UTC'),
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return None
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(PACIFIC)
    return df.sort_values('created_at', ascending=False).reset_index(drop=True)


def _block_row(coach, route, day, rng, finished):
    start_hour = int(rng.integers(6, 10))
    # The history view measures from block start to roughly an hour before the
    # end and discards anything under 40 miles, so blocks are long enough that
    # every one of them clears that.
    length = int(rng.integers(7, 11))
    start = day.replace(hour=start_hour, minute=int(rng.choice([0, 15, 30, 45])), second=0, microsecond=0)
    end = start + pd.Timedelta(hours=length)
    arrival = end + pd.Timedelta(minutes=int(rng.integers(-8, 20)))

    return {
        'coach': coach,
        'id': route,
        'block_id': f"{route}-{int(rng.integers(1, 40)):02d}",
        'block_startTime': start.strftime('%H:%M:%S'),
        'block_endTime': end.strftime('%H:%M:%S'),
        # Pacific wall time stamped as UTC - the quirk the real rows carry.
        'predictedArrival': arrival.tz_localize(None).tz_localize('UTC').isoformat(),
        'created_at': (
            start.tz_localize(None).tz_localize('UTC').isoformat() if finished
            else _now_pacific().tz_convert('UTC').isoformat()
        ),
    }


def mock_blocks(active=True, days=14):
    """Block assignments - mirrors supabase_blocks()."""
    now = _now_pacific()

    if active:
        serving = in_service()
        if not serving:
            return None
        rng = _rng(f'active-blocks-{now.strftime("%Y-%m-%d-%H")}')
        rows = []
        for coach, route in serving.items():
            end = now + pd.Timedelta(minutes=int(rng.integers(25, 240)))
            start = now - pd.Timedelta(hours=int(rng.integers(2, 6)))
            rows.append({
                'coach': coach,
                'id': route,
                'block_id': f"{route}-{int(rng.integers(1, 40)):02d}",
                'block_startTime': start.strftime('%H:%M:%S'),
                'block_endTime': end.strftime('%H:%M:%S'),
                'predictedArrival': end.tz_localize(None).tz_localize('UTC').isoformat(),
                'created_at': now.tz_convert('UTC').isoformat(),
            })
        return pd.DataFrame(rows)

    rows = []
    # Yesterday backwards: a block running today has not finished, so there is
    # no end-of-block telemetry to measure it against. Telemetry reaches back
    # further than this (see mock_soc_history) so the oldest block still has
    # readings before it started.
    last_day = now.normalize() - pd.Timedelta(days=1)
    for day in pd.date_range(last_day - pd.Timedelta(days=days), last_day, freq='D', tz=PACIFIC):
        rng = _rng(f'blocks-{day.date()}')
        for coach in rng.choice(COACHES, size=int(rng.integers(5, 9)), replace=False):
            rows.append(_block_row(str(coach), _ROUTES[int(rng.integers(0, len(_ROUTES)))], day, rng, finished=True))

    df = pd.DataFrame(rows)
    return df if not df.empty else None


def mock_active_location():
    """Latest GPS fix per coach - mirrors supabase_active_location()."""
    now = _now_pacific()
    serving = in_service()
    rng = _rng(f'location-{now.strftime("%Y-%m-%d-%H-%M")}')
    rows = []

    for coach in COACHES:
        if coach in serving:
            # Out on a route, somewhere north San Jose.
            lat = _DEPOT_LAT + float(rng.uniform(-0.05, 0.05))
            lon = _DEPOT_LON + float(rng.uniform(-0.06, 0.06))
            speed = float(rng.uniform(8, 38))
        else:
            # Parked inside the depot polygon.
            lat = _DEPOT_LAT + float(rng.uniform(-0.0010, 0.0018))
            lon = _DEPOT_LON + float(rng.uniform(-0.0025, 0.0028))
            speed = 0.0

        rows.append({
            'coach': coach,
            'lat': round(lat, 6),
            'long': round(lon, 6),
            'speed': speed,
            'created_at': (now - pd.Timedelta(minutes=int(rng.integers(1, 7)))).tz_convert('UTC').isoformat(),
        })

    return pd.DataFrame(rows)
