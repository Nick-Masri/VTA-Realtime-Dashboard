import pandas as pd
import streamlit as st
import pytz
# calls
from calls.supa_select import supabase_soc
from calls.chargepoint import chargepoint_active_sessions
# components
from components.active_blocks import show_active_blocks, get_active_blocks
# page files
from page_files.chargers import format_active_sessions
# data
import data

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
def show_data_scraping_status(df):
    df['created_at'] = df['created_at'].dt.tz_convert(pytz.timezone('US/Pacific'))
    # time with am pm 
    last_updated = pd.to_datetime(df['created_at'].max())
    hours = (pd.Timestamp.now(tz=pytz.timezone('US/Pacific')) - last_updated).total_seconds() / 3600
    options = ['🟢', '🟡', '🔴']
    emoji = options[0] if hours <= 2 else options[1] if hours <= 5 else options[2]
    last_updated = last_updated.strftime('%m/%d/%Y %I:%M %p') 
    st.caption(f'{emoji} Last accessed Proterra and Swiftly data  on {last_updated} PST') 
          
def make_transmission_hrs(df):
    df['last_transmission'] = pd.to_datetime(df['last_transmission'])
        # must localize so that .now stays the same even on server
    utc = pytz.timezone('UTC')
    df['last_transmission'] = df['last_transmission'].dt.tz_localize(utc)
    df['transmission_hrs'] = pd.Timestamp.now(tz=pytz.timezone('US/Pacific')) - df['last_transmission']
    df['transmission_hrs'] = df['transmission_hrs'].dt.total_seconds() / 3600
    # make transmission hrs a string, checks if years, months, days, hours, minutes
    df['last_seen'] = df['transmission_hrs'].apply(lambda x: f"{int((x % 8760) // 720)} months " if x >= 1440 else '') + \
                    df['transmission_hrs'].apply(lambda x: f"{int((x % 8760) // 720)} month " if (1440 > x >= 720) else '') + \
                    df['transmission_hrs'].apply(lambda x: f"{int((x % 720) // 24)} days " if (720 > x >= 48) else '') + \
                    df['transmission_hrs'].apply(lambda x: f"{int((x % 720) // 24)} day " if (48 > x >= 24) else '') + \
                    df['transmission_hrs'].apply(lambda x: f"{int(x % 24)} hours " if (2 <= x < 24) else '') + \
                    df['transmission_hrs'].apply(lambda x: f"{int(x % 24)} hour " if (1 <= x < 2) else '') + \
\
                    df['transmission_hrs'].apply(lambda x: f"{int(x*60)} minutes " if (x < 1) else '')
    df['last_transmission'] = df['last_transmission'].dt.tz_convert(pytz.timezone('US/Pacific'))
    df['last_transmission'] = df['last_transmission'].dt.strftime('%I:%M:%S %p %m/%d/%Y')
    df['transmission_hrs'] = df['transmission_hrs'].astype(int)
    # df['last_transmission'] = pd.to_datetime(df['last_transmission'])
    return df

def dashboard():
    # Load the active blocks DataFrame from swiftly API
    active_blocks = get_active_blocks()

    # get soc from supabase
    df = supabase_soc()
    show_data_scraping_status(df)

    # get column config
    column_config = data.dash_column_config

    # get charging sessions from chargepoint
    charging_sessions = get_charging_sessions()
    if charging_sessions is not None:
        merged_df = pd.merge(df, charging_sessions, left_on='vehicle', right_on='vehicle', how='inner', suffixes=('', '_y'))
        merged_df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
        # remove vehicles that are charging from df
        df = df[~df['vehicle'].isin(merged_df['vehicle'])]
        st.subheader("Currently Charging")
        st.dataframe(merged_df, hide_index=True, use_container_width=True, 
                        column_config=column_config)
        
    # add transmission hrs and last seen
    df = make_transmission_hrs(df)

    if active_blocks is not None:
        merged_df = pd.merge(active_blocks, df, left_on='coach', right_on='vehicle',
                             how='inner', suffixes=('', '_y'))
        merged_df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
        df = df[~df['vehicle'].isin(merged_df['vehicle'])]

        show_active_blocks(merged_df)

    df.sort_values(['last_transmission', 'status', 'vehicle'], ascending=False, inplace=True)
    active = df[df['transmission_hrs'] <= 24]
    inactive = df[df['transmission_hrs'] > 24]
    column_config['last_seen'] = st.column_config.TextColumn("Time Offline")
        
    st.subheader("Idle Buses")
    active = active.sort_values('transmission_hrs')
    active.style.background_gradient(cmap='RdYlGn_r', vmin=1, vmax=24 * 4, axis=1)
    active = active[['vehicle', 'soc', 'last_seen']]
    st.dataframe(active, hide_index=True, use_container_width=True, column_config=column_config)

    st.subheader("Offline for more than a day")
    inactive = inactive.sort_values('transmission_hrs')
    inactive = inactive[['vehicle', 'last_seen', 'odometer']]
    
    st.dataframe(inactive, use_container_width=True, hide_index=True, column_config=column_config)
