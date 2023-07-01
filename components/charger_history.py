
import streamlit as st
import numpy as np
import pandas as pd
from calls.chargepoint import chargepoint_past_sessions

def show_charger_history():      
    st.caption("Currently only shows the last 7 days of charging history. In the future there will be a way to query for a longer and specific time period.")
    df = chargepoint_past_sessions()
    df = df.sort_values('startTime', ascending=False)
    # Change station name from VTA / STATION #1 to VTA STATION #1
    df['stationName'] = df['stationName'].str.replace(' / ', ' ')
    df['totalChargingDuration'] = pd.to_timedelta(df['totalChargingDuration'])
    df['totalChargingDuration'] = df['totalChargingDuration'].dt.floor('s')
    df['totalSessionDuration'] = pd.to_timedelta(df['totalSessionDuration'])
    df['totalSessionDuration'] = df['totalSessionDuration'].dt.floor('s')
    df['totalChargingDuration'] = df['totalChargingDuration'].astype(str)
    df['totalSessionDuration'] = df['totalSessionDuration'].astype(str)
    df['startTime'] = pd.to_datetime(df['startTime']).dt.tz_convert('US/Pacific')
    df['endTime'] = pd.to_datetime(df['endTime']).dt.tz_convert('US/Pacific')
    df = df.drop(columns=['totalChargingDuration', 'totalSessionDuration'])
    # st.write(df)
    st.dataframe(df, 
                 hide_index=True, use_container_width=True,
                 column_config={
                     "stationName": st.column_config.TextColumn("Station Name"),
                     "startTime": st.column_config.DatetimeColumn("Start Time", 
                                                                  format="MM/DD/YY hh:mmA"),
                        "endTime": st.column_config.DatetimeColumn("End Time",
                                                                     format="MM/DD/YY hh:mmA"),
                        "energy": st.column_config.NumberColumn("Energy (kWh)"),
                        "totalChargingDuration": st.column_config.TextColumn("Charging Duration"),
                        "totalSessionDuration": st.column_config.TextColumn("Session Duration (hrs)"),
                        "startBatteryPercentage": st.column_config.ProgressColumn("Start SOC (%)",
                                                                                format='%d%%',
                                                                                min_value=0,max_value=100),
                        "stopBatteryPercentage": st.column_config.ProgressColumn("End SOC (%)",
                                                                                format='%d%%',
                                                                                min_value=0,max_value=100),
                        "endedBy": st.column_config.TextColumn("Ended By"),
                 },
                    column_order=[
                        "stationName",
                        "startTime",
                        "endTime",
                        # "totalChargingDuration",
                        # "totalSessionDuration",
                        "startBatteryPercentage",
                        "stopBatteryPercentage",
                        "energy",
                        "endedBy",
                    ])
