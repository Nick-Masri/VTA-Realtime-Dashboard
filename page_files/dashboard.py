import pandas as pd
import streamlit as st
import pytz
# calls
# from calls.supa_select import supabase_soc
from calls.bundled import active_info
# components
from components.active_blocks import show_active_blocks, get_active_blocks
# page files
from page_files.chargers import format_active_sessions
# data
import data



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

    # get necessary data
    serving, charging, idle, offline, df = get_overview_df()

    # show data scraping status
    show_data_scraping_status(df)

    # get column config
    column_config = data.dash_column_config

    # Active Blocks
    if serving is not None:
        merged_df = pd.merge(serving, df, left_on='coach', right_on='vehicle',
                                how='inner', suffixes=('', '_y'))
        merged_df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
        df = df[~df['vehicle'].isin(merged_df['vehicle'])]
        show_active_blocks(merged_df)

    # Actively Charging
    if charging is not None and not charging.empty:
        st.subheader("Currently Charging")
        # current soc if less than equal to 100 and above 0 otherwise soc
        charging['soc'] = charging.apply(lambda row: row['currentSOC'] if row['currentSOC'] <= 100 and row['currentSOC'] > 0 else row['soc'], axis=1)
        charging = charging[['soc', 'vehicle', 'stationName', 'totalSessionDuration']]
        
        st.dataframe(charging, hide_index=True, use_container_width=True, 
                        column_order=[
                             "vehicle", "soc","stationName", "totalSessionDuration"],
                        column_config={
                            "stationName": st.column_config.TextColumn("Station"),
                            "vehicle": st.column_config.TextColumn("Coach"),
                            "totalSessionDuration": st.column_config.TextColumn("Session Duration"),
                            "soc": st.column_config.ProgressColumn("State of Charge",
                                                                                    format='%d%%',
                                                                                    min_value=0,max_value=100),

                        }
                        )

    # Idle and Offline
    column_config['last_seen'] = st.column_config.TextColumn("Time Offline")
        
    # Idle
    st.subheader("Idle Buses")
    idle = idle.sort_values('transmission_hrs')
    idle.style.background_gradient(cmap='RdYlGn_r', vmin=1, vmax=24 * 4, axis=1)
    idle = idle[['vehicle', 'soc', 'last_seen']]
    idle['soc'] = idle['soc'].astype(int)
    st.dataframe(idle, hide_index=True, use_container_width=True, column_config=column_config)

    # Offline
    st.subheader("Offline for more than a day")
    offline = offline.sort_values('transmission_hrs')
    offline = offline[['vehicle', 'last_seen', 'odometer']]
    st.dataframe(offline, use_container_width=True, hide_index=True, column_config=column_config)

def get_overview_df():
    # initialize
    serving, charging, idle, offline, df = None, None, None, None, None

    # get necessary data
    active_blocks, df, charging_sessions = active_info()

    # add transmission hrs and last seen
    df = make_transmission_hrs(df)

    # make serving df
    if active_blocks is not None and not active_blocks.empty:
        df = pd.merge(active_blocks, df, left_on='coach', right_on='vehicle',
                             how='left', suffixes=('', '_y'), indicator=True)
        df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
        df.rename(columns={'_merge': 'active'}, inplace=True)
        serving = df[df['active'] == 'both']
        serving = serving.copy()
        df['active'] = df.apply(lambda row: True if row['active'] =='both' else False, axis=1)
    else:
        df['active'] = False

    # make charging df
    if charging_sessions is not None and not charging_sessions.empty:
        df = pd.merge(df, charging_sessions, left_on='vehicle', right_on='vehicle', how='left', suffixes=('', '_y'), indicator=True)
        df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
        df.rename(columns={'_merge': 'charging'}, inplace=True)
        charging = df[df['charging'] == 'both']
        charging = charging.copy()
        df['charging'] = df.apply(lambda row: True if row['charging'] =='both' else False, axis=1)
    else:
        df['charging'] = False

    inactive = df[df['active'] == False]
    inactive = inactive[inactive['charging'] == False]

    inactive.sort_values(['last_transmission', 'status', 'vehicle'], ascending=False, inplace=True)
  
    df['idle'] = df['transmission_hrs'] <= 24
    df['offline'] = df['transmission_hrs'] > 24

    idle = df[df['idle'] == True]
    idle = idle[idle['active'] == False]
    idle = idle[idle['charging'] == False]

    offline = df[df['offline'] == True]
    offline = offline[offline['active'] == False]
    offline = offline[offline['charging'] == False]

    idle = idle.copy()
    offline = offline.copy()
    # make status based on charging, active, idle and offilne columns
    df['status'] = df.apply(lambda row: 'Driving' if row['active'] 
                            else 'Charging' if row['charging'] 
                            else 'Idle' if row['idle'] 
                            else 'Offline' if row['offline']
                            else None, axis=1)
    df = df.drop(columns=['active', 'charging', 'idle', 'offline'])

    return serving, charging, idle, offline, df.copy()