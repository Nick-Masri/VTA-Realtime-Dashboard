from calls.supa_select import supabase_soc
from components.active_blocks import get_active_blocks
import streamlit as st
import pandas as pd
from calls.chargepoint import chargepoint_active_sessions


@st.cache_data(ttl=pd.Timedelta(minutes=5), show_spinner="Updating data...")
def active_info():
    # get necessary data
    active_blocks = get_active_blocks()
    soc = supabase_soc()
    charging_sessions = get_charging_sessions()

    return active_blocks, soc, charging_sessions


def get_charging_sessions():
    df = chargepoint_active_sessions()
    df["stationName"] = df["stationName"].str.replace(' / ', ' ', regex=False)
    # Replace the desired format in the 'Station' column
    df["stationName"] = df["stationName"].str.replace(r"VTA STATION #(\d+)", r"Station \1", regex=True)
    df = df[df['Charging'] == True]
    if not df.empty:
        df = format_active_sessions(df)
        df = df[['stationName', 'Idle', 'vehicle', 'totalSessionDuration', 'currentSOC']]
        return df
    else:
        return None