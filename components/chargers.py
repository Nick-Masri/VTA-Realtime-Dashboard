
from calls.chargepoint import chargepoint_stations, chargepoint_active_sessions, chargepoint_map, chargepoint_past_sessions
import streamlit as st 
import pandas as pd

def show_chargers():
    stations = chargepoint_stations()
    sessions = chargepoint_active_sessions()
    df = pd.merge(stations, sessions, on='stationName', how='left')
    # st.write(df)
    # Display the DataFrame
    # vehicle macs seen
    # 70b3d52c3126 (maybe 7505)
    #  70b3d52c3747 (probably 9504)
    # do these link up to vehicle? I guess we will see
    df["stationName"] = df["stationName"].str.replace(' / ', ' ')
    active = df[df['Charging'] == True]
    active['startTime'] = pd.to_datetime(active['startTime'])
    active['startTime'] = active['startTime'].dt.tz_convert('US/Pacific')
    inactive = df[df['Charging'] == False]
    st.subheader("Currently Charging")
    st.dataframe(active, hide_index=True, use_container_width=True,
                    column_order=[
                        "stationName","startTime", "startBatteryPercentage", "Energy", 
                                   "totalChargingDuration", "totalSessionDuration",
                                      ],
                    column_config={
                        "stationName": st.column_config.TextColumn("Station Name"),
                        "startTime": st.column_config.DatetimeColumn("Start Time",
                                                                        format="MM/DD/YY hh:mmA"),
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
                    })
    
    st.subheader("Inactive ")
    st.dataframe(inactive, hide_index=True, use_container_width=True,
                    column_order=[
                    "stationName", 
                    "Status",
                    "networkStatus",
                     ], 
                     column_config={
                        "stationName": st.column_config.TextColumn("Station Name"),
                        "networkStatus": st.column_config.TextColumn("Network Status")
                        })
    chargepoint_map(stations)