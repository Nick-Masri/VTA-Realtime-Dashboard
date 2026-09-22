"""Tracks which parts of the portal are running on simulated data.

The flags live in a cache_resource store rather than in module globals.
Every mark() below is called from inside an @st.cache_data function body,
which Streamlit skips entirely on a cache hit, so the flags have to share
the data cache's lifetime. Module globals do not: Streamlit drops a changed
source file from sys.modules and re-imports it while cached values keyed on
unchanged function source survive, which reset the flags underneath the
cached simulated data. The portal then served mock telemetry with the
disclosure switched off, captioned "Last accessed Proterra and Swiftly
data" - the opposite of what it was showing. A push that changes any file
is enough to trigger it; the file need not be this one.
"""

import streamlit as st

_LABELS = {
    'fleet': 'vehicle telemetry',
    'chargers': 'charger sessions',
    'weather': 'weather',
}


@st.cache_resource(show_spinner=False)
def _store():
    return {'state': {key: False for key in _LABELS}, 'issues': []}


def mark(source):
    _store()['state'][source] = True


# Integration failures worth showing the operator. Collected rather than
# printed at the call site: those sit inside cached functions, so Streamlit
# replays them once per call site per rerun, which is how the same "Supabase
# unavailable" line ended up on the page twice.
def note_issue(message):
    message = str(message)
    issues = _store()['issues']
    if message not in issues:
        issues.append(message)


def render_issues():
    for message in _store()['issues']:
        st.warning(message)


def simulated_sources():
    return [key for key, on in _store()['state'].items() if on]


def any_simulated():
    return any(_store()['state'].values())


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
