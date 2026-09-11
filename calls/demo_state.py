"""Tracks which parts of the portal are running on simulated data.

Flags are sticky for the life of the process. Streamlit replays cached
functions without re-running their bodies, so a flag cleared between reruns
would flicker; for a disclosure the safe direction is to keep saying
"simulated" rather than to quietly stop saying it.
"""

import streamlit as st

_LABELS = {
    'fleet': 'vehicle telemetry',
    'chargers': 'charger sessions',
    'weather': 'weather',
}

_state = {key: False for key in _LABELS}


def mark(source):
    _state[source] = True


def simulated_sources():
    return [key for key, on in _state.items() if on]


def any_simulated():
    return any(_state.values())


def render_banner():
    """One deliberate notice, rather than a caption per failed integration."""
    active = simulated_sources()
    if not active:
        return

    names = [_LABELS[key] for key in active]
    if len(names) == 1:
        what = names[0]
    elif len(names) == 2:
        what = ' and '.join(names)
    else:
        what = ', '.join(names[:-1]) + ' and ' + names[-1]

    st.info(
        f"**Demonstration mode** — {what} shown here are simulated. "
        "Live Proterra, Swiftly and ChargePoint feeds are pending reconnection; "
        "the models and schedules run exactly as they would on live data.",
        icon=":material/science:",
    )
