"""Simulated ChargePoint data.

The VTA ChargePoint account no longer authenticates, so the live SOAP API
returns nothing usable. These builders reproduce the exact frame shapes the
real `calls.chargepoint` functions return, letting the portal stay a working
demo. Anything served from here is labelled in the UI as simulated.
"""

import numpy as np
import pandas as pd

import data

BATTERY_KWH = 440

_STATION_SITES = {
    'VTA / STATION #1': ('Holger Way, San Jose, California, 95134, United States', 37.4031, -121.9492),
    'VTA / STATION #2': ('Holger Way, San Jose, California, 95134, United States', 37.4033, -121.9489),
    'VTA / STATION #3': ('Holger Way, San Jose, California, 95134, United States', 37.4035, -121.9486),
    'VTA / STATION #4': ('Holger Way, San Jose, California, 95134, United States', 37.4037, -121.9483),
    'VTA / STATION #5': ('Coyote Creek Trail, San Jose, California, 95134, United States', 37.4089, -121.9431),
}

# One port MAC per coach, so a mocked session maps back through data.mac_to_name.
_COACH_MACS = {}
for _mac, _coach in data.mac_to_name.items():
    _COACH_MACS.setdefault(_coach, _mac)


def _rng(seed_source):
    """Stable within a period so a demo does not reshuffle on every rerun."""
    return np.random.default_rng(abs(hash(seed_source)) % (2 ** 32))


def _duration(total_seconds):
    total_seconds = int(total_seconds)
    return f"{total_seconds // 3600:02d}:{total_seconds % 3600 // 60:02d}:{total_seconds % 60:02d}"


def mock_stations():
    rows = []
    rng = _rng('stations')
    for name, (address, lat, lon) in _STATION_SITES.items():
        charging = name in _currently_charging()
        rows.append({
            'stationName': name,
            'Address': address,
            'Status': 'INUSE' if charging else 'AVAILABLE',
            'networkStatus': 'Connected',
            'Voltage': round(float(rng.uniform(495, 505)), 1) if charging else 0.0,
            'Current': round(float(rng.uniform(180, 240)), 1) if charging else 0.0,
            'Power': round(float(rng.uniform(90, 125)), 1) if charging else 0.0,
            'Geo.Lat': lat,
            'Geo.Long': lon,
        })
    return pd.DataFrame(rows)


def _currently_charging():
    """Which stations are busy, rotating slowly so the demo looks alive."""
    from calls.supabase_mock import in_service

    now = pd.Timestamp.now(tz='US/Pacific')
    rng = _rng(f'active-{now.strftime("%Y-%m-%d-%H")}')
    names = list(_STATION_SITES)

    # A bus out on a block cannot also be plugged in.
    coaches = [c for c in sorted(_COACH_MACS) if c not in in_service()]
    if not coaches:
        return {}

    size = min(3, len(coaches), len(names))
    busy = rng.choice(len(names), size=size, replace=False)
    picked = rng.choice(len(coaches), size=size, replace=False)
    return {names[int(s)]: coaches[int(c)] for s, c in zip(busy, picked)}


def mock_active_sessions():
    now = pd.Timestamp.now(tz='US/Pacific')
    charging = _currently_charging()
    rows = []

    for name in _STATION_SITES:
        if name not in charging:
            rows.append({'stationName': name, 'Charging': False})
            continue

        coach = charging[name]
        rng = _rng(f'session-{name}-{now.strftime("%Y-%m-%d-%H")}')
        elapsed = int(rng.integers(15 * 60, 3 * 3600))
        idle = int(rng.integers(0, 600))
        start_soc = int(rng.integers(18, 55))
        # Cap energy so the derived current SOC stays under 100%.
        headroom = (100 - start_soc) / 100 * BATTERY_KWH / 0.96
        energy = round(min(elapsed / 3600 * float(rng.uniform(95, 125)), headroom * 0.95), 1)

        rows.append({
            'stationName': name,
            'Energy': energy,
            'startTime': (now - pd.Timedelta(seconds=elapsed)).isoformat(),
            'endTime': None,
            'totalChargingDuration': _duration(elapsed - idle),
            'totalSessionDuration': _duration(elapsed),
            'startBatteryPercentage': start_soc,
            'stopBatteryPercentage': 0,
            'Charging': True,
            'vehiclePortMAC': _COACH_MACS[coach],
        })

    return pd.DataFrame(rows)


def mock_past_sessions(start_date, end_date):
    start = pd.Timestamp(start_date).tz_localize('US/Pacific')
    end = pd.Timestamp(end_date).tz_localize('US/Pacific')
    if end <= start:
        return pd.DataFrame()

    names = list(_STATION_SITES)
    coaches = sorted(_COACH_MACS)
    rows = []

    for day in pd.date_range(start.normalize(), end.normalize(), freq='D', tz='US/Pacific'):
        rng = _rng(f'history-{day.date()}')
        # Buses charge overnight back at the yard.
        for coach in rng.choice(coaches, size=int(rng.integers(4, 8)), replace=False):
            station = names[int(rng.integers(0, len(names)))]
            begin = day + pd.Timedelta(hours=int(rng.integers(19, 24)), minutes=int(rng.integers(0, 60)))
            charge_secs = int(rng.integers(45 * 60, 4 * 3600))
            idle_secs = int(rng.integers(0, 2 * 3600))
            start_soc = int(rng.integers(12, 45))
            headroom = (100 - start_soc) / 100 * BATTERY_KWH / 0.96
            energy = round(min(charge_secs / 3600 * float(rng.uniform(95, 125)), headroom * 0.95), 1)
            stop_soc = int(min(100, start_soc + energy / BATTERY_KWH * 100 * 0.96))

            rows.append({
                'stationName': station,
                'vehiclePortMAC': _COACH_MACS[str(coach)],
                'startTime': begin.isoformat(),
                'endTime': (begin + pd.Timedelta(seconds=charge_secs + idle_secs)).isoformat(),
                'totalChargingDuration': _duration(charge_secs),
                'totalSessionDuration': _duration(charge_secs + idle_secs),
                'startBatteryPercentage': start_soc,
                'stopBatteryPercentage': stop_soc,
                'Energy': energy,
                'endedBy': 'Vehicle',
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    within = (pd.to_datetime(df['startTime']) >= start) & (pd.to_datetime(df['startTime']) <= end)
    return df[within].reset_index(drop=True)
