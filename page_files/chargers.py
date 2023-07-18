
from calls.chargepoint import chargepoint_stations, chargepoint_active_sessions, chargepoint_map, chargepoint_past_sessions
import streamlit as st 
import pandas as pd
import data

# for the page on chargers
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
        active = active.copy()
        active['vehicle'] = active['vehiclePortMAC'].map(data.mac_to_name)
        active['vehicle'] = active['vehicle'].fillna('Unknown')k

        active['startTime'] = pd.to_datetime(active['startTime'])
        active['startTime'] = active['startTime'].dt.tz_convert('US/Pacific')
        active['currentSOC'] = active['startBatteryPercentage'] + (active['Energy'] / 440) * 100
        active['currentSOC'] = active['currentSOC'].astype(int)
        # st.write(active.dtypes)

        # convert to timedelta for conversion
        active['totalChargingDuration'] = pd.to_timedelta(active['totalChargingDuration'])
        active['totalSessionDuration'] = pd.to_timedelta(active['totalSessionDuration'])
        # make idle column. True if totalSessionDuration - totalChargingDuration > 5 minutes
        active['Idle'] = active['totalSessionDuration'] - active['totalChargingDuration'] > pd.Timedelta(minutes=5)
            
        # TODO: this seems like a hacky way to do this / redundant
        # Format as days, hours, minutes
        active['totalChargingDuration'] = active['totalChargingDuration'].apply(lambda x: f'{x.days} d {x.seconds // 3600} hr {x.seconds // 60 % 60} min')
        active['totalSessionDuration'] = active['totalSessionDuration'].apply(lambda x: f'{x.days} d {x.seconds // 3600} hr {x.seconds // 60 % 60} min')

        # change back to object for streamlit
        active['totalChargingDuration'] = active['totalChargingDuration'].astype(str)
        active['totalSessionDuration'] = active['totalSessionDuration'].astype(str)
        # remove 0 days
        active['totalChargingDuration'] = active['totalChargingDuration'].str.replace('0 d ', '')
        active['totalSessionDuration'] = active['totalSessionDuration'].str.replace('0 d ', '')
        # remove 0 hours
        active['totalChargingDuration'] = active['totalChargingDuration'].str.replace('0 hr ', '')
        active['totalSessionDuration'] = active['totalSessionDuration'].str.replace('0 hr ', '')

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