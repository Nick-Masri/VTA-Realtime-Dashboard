import pandas as pd
from supabase import create_client, Client
import os
from datetime import datetime, timedelta
import pytz
import streamlit as st

@st.cache_resource
def setup_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
    return supabase


def _fetch(build_query):
    """Run a Supabase query, returning None instead of raising.

    A free-tier project auto-pauses after inactivity, which otherwise turns
    every tab of the portal into a stack trace.
    """
    try:
        return build_query(setup_client()).execute().data
    except Exception as exc:
        st.warning(f"Supabase unavailable ({exc})")
        return None

@st.cache_data(show_spinner=False, ttl=timedelta(minutes=10))
def supabase_blocks(active=True):
    data = _fetch(lambda sb: sb.table('block_history').select("*").order("created_at", desc=True))
    if not data:
        return None
    df = pd.DataFrame(data).drop(columns='id')

    if len(df) > 0:
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
    if not data:
        return None
    df = pd.DataFrame(data)
    # st.write(df.columns)
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
    data = _fetch(lambda sb: sb.table('location').select("*").order("created_at", desc=True))
    if not data:
        return None
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
        data = _fetch(lambda sb: sb.table('soc').select("*").order("created_at", desc=True))
    else:
        data = _fetch(lambda sb: sb.table('soc').select("*").eq('vehicle', vehicle).order("created_at", desc=True))

    if not data:
        return None
    df = pd.DataFrame(data)
    df['vehicle'] = df['vehicle'].astype(str)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.sort_values(by='created_at', ascending=False, inplace=True)

    # Convert last_transmission column to California timezone
    california_tz = pytz.timezone('US/Pacific')
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(california_tz)
    return df.copy()
