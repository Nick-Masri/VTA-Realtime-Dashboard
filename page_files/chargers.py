
from calls.chargepoint import chargepoint_stations, chargepoint_active_sessions, chargepoint_map, chargepoint_past_sessions
import streamlit as st 
import pandas as pd
import data
from components.chargers import format_active_sessions

def show_chargers():
    stations = chargepoint_stations()
    sessions = chargepoint_active_sessions()
    df = pd.merge(stations, sessions, on='stationName', how='left')
    
    df["stationName"] = df["stationName"].str.replace(' / ', ' ', regex=False)
    # Replace the desired format in the 'Station' column
    df["stationName"] = df["stationName"].str.replace(r"VTA STATION #(\d+)", r"Station \1", regex=True)

    active = df[df['Charging'] == True]
    inactive = df[df['Charging'] == False]

    if not active.empty:
        active = format_active_sessions(active)
        st.subheader("Currently Charging")
        st.dataframe(active, hide_index=True, use_container_width=True,
                        column_order=[
                            "stationName","Idle", "startTime", "vehicle", "startBatteryPercentage", 
                             "currentSOC", "totalChargingDuration", 
                            #  "totalSessionDuration",
                                        ],
                        column_config={
                            "stationName": st.column_config.TextColumn("Station"),
                            "startTime": st.column_config.DatetimeColumn("Start Time",
                                                                            format="hh:mmA"),
                            "vehicle": st.column_config.TextColumn("Coach"),
                            "totalChargingDuration": st.column_config.TextColumn("Charging Duration"),
                            "totalSessionDuration": st.column_config.TextColumn("Session Duration"),
                            "startBatteryPercentage": st.column_config.ProgressColumn("Start SOC (%)",
                                                                                    format='%d%%',
                                                                                    min_value=0,max_value=100),
                            "stopBatteryPercentage": st.column_config.ProgressColumn("End SOC (%)",
                                                                                    format='%d%%',
                                                                                    min_value=0,max_value=100),
                            "Energy": st.column_config.NumberColumn("Energy (kWh)"),
                            "endedBy": st.column_config.TextColumn("Ended By"),
                            "currentSOC": st.column_config.ProgressColumn("Current SOC (%)",
                                                                                    format='%d%%',
                                                                                    min_value=0,max_value=100),

                        })
        
    if not inactive.empty:
        inactive = inactive.copy()
        st.subheader("Inactive ")
        st.dataframe(inactive, hide_index=True, use_container_width=True,
                        column_order=[
                        "stationName", 
                        "Status",
                        "networkStatus",
                        ], 
                        column_config={
                            "stationName": st.column_config.TextColumn("Station"),
                            "networkStatus": st.column_config.TextColumn("Network Status")
                            })
        
    # if not stations.empty:
    #     chargepoint_map(stations)