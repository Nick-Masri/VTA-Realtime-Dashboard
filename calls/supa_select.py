import re

import pandas as pd
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import os
from datetime import datetime, timedelta
import pytz
import streamlit as st

from calls import demo_state
from calls.supabase_mock import (
    mock_active_location, mock_blocks, mock_soc, mock_soc_history,
)

# Rows older than this count as "not live" when DEMO_MODE is left on auto.
DEMO_STALE_AFTER = timedelta(hours=24)

# How far back history queries reach. The soc table gains a row per bus per
# transmission, so an unfiltered select("*") pulls every reading ever recorded
# and intermittently exceeds the client's socket timeout - the source of
# "Supabase unavailable (The read operation timed out)". PostgREST also caps a
# response, so an unbounded query was never returning the whole table anyway.
HISTORY_WINDOW = timedelta(days=60)
MAX_ROWS = 5000

# postgrest-py defaults to a 5 second budget for the whole request, which a
# history query over a table this size will not meet. Raised rather than
# removed so a genuinely stuck request still gives up.
CLIENT_TIMEOUT_SECONDS = 30


def _since():
    return (pd.Timestamp.now(tz='UTC') - HISTORY_WINDOW).isoformat()


def _demo_setting():
    try:
        return str(st.secrets.get("DEMO_MODE", "auto")).strip().lower()
    except Exception:
        return "auto"


def _latest(data):
    if not data:
        return None
    try:
        stamps = pd.to_datetime(pd.DataFrame(data)['created_at'], utc=True, format='mixed')
        return stamps.max()
    except Exception:
        return None


def _use_demo(data):
    """Whether to serve simulated data instead of what Supabase returned."""
    setting = _demo_setting()
    if setting in ('on', 'true', '1', 'yes'):
        return True
    if setting in ('off', 'false', '0', 'no'):
        return False

    latest = _latest(data)
    if latest is None:
        return True
    return (pd.Timestamp.now(tz='UTC') - latest) > DEMO_STALE_AFTER


def _demo_notice():
    demo_state.mark('fleet')


@st.cache_resource
def setup_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    options = ClientOptions(postgrest_client_timeout=CLIENT_TIMEOUT_SECONDS)
    supabase: Client = create_client(url, key, options=options)
    return supabase


def _describe(exc):
    """A short reason, fit to show on the page.

    The raw exception is not. A paused project answers with a Cloudflare
    error page, and interpolating that painted a full HTML document across
    the dashboard.
    """
    text = ' '.join(str(exc).split())
    low = text.lower()

    if 'timed out' in low or 'timeout' in low:
        return (f"a query took longer than {CLIENT_TIMEOUT_SECONDS}s. The "
                "history tables likely need an index on created_at")

    for phrase in ('name or service not known', 'nodename nor servname',
                   'temporary failure in name resolution', 'errno -2'):
        if phrase in low:
            return ("the project's hostname does not resolve, which is how a "
                    "paused project looks. Restoring it in Supabase fixes this")

    status = re.search(r"'code':\s*(5\d\d)", text)
    if status or 'web server is down' in low:
        code = status.group(1) if status else '521'
        return (f"the database is not accepting connections yet (HTTP {code}). "
                "A project that has just been restored needs a minute")

    if '<html' in low:
        return "the host returned an error page instead of data"

    if len(text) > 160:
        return text[:160].rstrip() + '...'
    return text


def _fetch(build_query):
    """Run a Supabase query, returning None instead of raising.

    A free-tier project auto-pauses after inactivity, which otherwise turns
    every tab of the portal into a stack trace.
    """
    try:
        return build_query(setup_client()).execute().data
    except Exception as exc:
        demo_state.note_issue(f"Supabase unavailable: {_describe(exc)}")
        return None

@st.cache_data(show_spinner=False, ttl=timedelta(minutes=10))
def supabase_blocks(active=True):
    data = _fetch(lambda sb: sb.table('block_history').select("*")
                  .gte('created_at', _since())
                  .order("created_at", desc=True).limit(MAX_ROWS))
    if _use_demo(data):
        _demo_notice()
        return mock_blocks(active=active)
    # The _since() window can legitimately outrun the newest row, so an empty
    # frame is a normal result, not an error. Callers expect None for it.
    df = pd.DataFrame(data)

    if len(df) > 0:
        df = df.drop(columns='id')
        df = df.rename(columns={"start_time": "block_startTime", "end_time": "block_endTime",
                                "predicted_arrival": "predictedArrival", "route_id": "id"})
        df['coach'] = df['coach'].astype(str)
        df = df.sort_values('created_at', ascending=False)
        if active:
            df = df.drop_duplicates(subset=['coach'], keep='first')
        return df.copy()
    else:
        return None

@st.cache_data(show_spinner=False, ttl=timedelta(minutes=5))
def supabase_soc():
    data = _fetch(lambda sb: sb.table('soc').select("*").order("created_at", desc=True).limit(10))
    if _use_demo(data):
        _demo_notice()
        return mock_soc()
    df = pd.DataFrame(data)
    if df.empty:
        return None
    df['vehicle'] = df['vehicle'].astype(str)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.sort_values(by='created_at', ascending=False, inplace=True)

    # Drop duplicate entries for each vehicle, keeping only the first (most recent)
    df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
    df = df[['soc', 'vehicle', 'odometer', 'status', 'last_transmission', 'created_at']]
    # Format the odometer column with thousands separator
    df['odometer'] = df['odometer'].apply(lambda x: "{:,}".format(x))

    return df.copy()

@st.cache_data(show_spinner=False, ttl=timedelta(minutes=60))
def supabase_active_location():
    # Only the newest fix per coach is used, so a small page is plenty.
    data = _fetch(lambda sb: sb.table('location').select("*")
                  .order("created_at", desc=True).limit(500))
    if _use_demo(data):
        return mock_active_location()
    df = pd.DataFrame(data)
    if len(df) > 0:
        df['coach'] = df['coach'].astype(str)
        df = df.sort_values('created_at', ascending=False)
        df = df.drop_duplicates(subset=['coach'], keep='first')
        df = df.drop(columns=['id'])
        return df.copy()

    else:
        return None

@st.cache_data(show_spinner=False, ttl=timedelta(minutes=60))
def supabase_soc_history(vehicle=None):
    if vehicle is None:
        data = _fetch(lambda sb: sb.table('soc').select("*")
                      .gte('created_at', _since())
                      .order("created_at", desc=True).limit(MAX_ROWS))
    else:
        data = _fetch(lambda sb: sb.table('soc').select("*").eq('vehicle', vehicle)
                      .gte('created_at', _since())
                      .order("created_at", desc=True).limit(MAX_ROWS))

    if _use_demo(data):
        return mock_soc_history(vehicle=vehicle)
    df = pd.DataFrame(data)
    if df.empty:
        return None
    df['vehicle'] = df['vehicle'].astype(str)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.sort_values(by='created_at', ascending=False, inplace=True)

    # Convert last_transmission column to California timezone
    california_tz = pytz.timezone('US/Pacific')
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(california_tz)
    return df.copy()
