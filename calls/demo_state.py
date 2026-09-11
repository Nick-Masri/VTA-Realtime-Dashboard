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

# Integration failures worth showing the operator. Collected rather than
# printed at the call site: those sit inside cached functions, so Streamlit
# replays them once per call site per rerun, which is how the same "Supabase
# unavailable" line ended up on the page twice.
_issues = []


def mark(source):
    _state[source] = True


def note_issue(message):
    message = str(message)
    if message not in _issues:
        _issues.append(message)


def render_issues():
    for message in _issues:
        st.warning(message)


def simulated_sources():
    return [key for key, on in _state.items() if on]


def any_simulated():
    return any(_state.values())


def render_banner():
    """One deliberate notice, rather than a caption per failed integration.

    Deliberately does not enumerate which sources fell back. Doing so meant
    waiting for every tab body to report before the wording was final, which
    put the disclosure at the very bottom of the script - the one element that
    must not be the last thing to appear.
    """
    if not any_simulated():
        return

    st.info(
        "**Demonstration mode** — the fleet, charger and weather data shown "
        "here are simulated. Live Proterra, Swiftly and ChargePoint feeds are "
        "pending reconnection; the models and schedules run exactly as they "
        "would on live data.",
        icon=":material/science:",
    )
