
from calls.chargepoint import chargepoint_stations, chargepoint_active_sessions, chargepoint_map
import streamlit as st 
import pandas as pd

def show_chargers():
    stations = chargepoint_stations()
    sessions = chargepoint_active_sessions()
    df = pd.merge(stations, sessions, on='stationName', how='left')
    # Display the DataFrame
    st.dataframe(df, hide_index=True, use_container_width=True,
                 column_order=[
                     "stationName",
                     "Charging",
                     "Address",
                    "Status",
                     "networkStatus",
                    # "Voltage",
                    #  "Current",
                    #  "Power"
                     ], 
                     column_config={
                        "stationName": st.column_config.TextColumn("Station Name"),
                        "networkStatus": st.column_config.TextColumn("Network Status")
                        })
    chargepoint_map(stations)