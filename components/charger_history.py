import streamlit as st
from calls.chargepoint import chargepoint_past_sessions
import pandas as pd
import data
import numpy as np



def format_duration(col):

    col = col.apply(
    lambda x: f"{x.days} days {x.seconds // 3600} hours {(x.seconds % 3600) // 60} minutes"
    )

    col = col.astype(str)
    # remove 0 days 0 hours
    col = col.str.replace('0 days 0 hours ', '')
    # remove s's from days, hours, minutes
    col = col.str.replace('1 days', '1 day')
    col = col.str.replace('1 hours', '1 hour')
    col = col.str.replace('1 minutes', '1 minute')
    # remove 0 days
    col = col.str.replace('0 days ', '')
    return col

# shows the charging history of the ebuses
def show_charger_history():      
    # st.caption("Currently only shows the last 7 days of charging history. In the future there will be a way to query for a longer and specific time period.")
    # ask for start and end date input
    start_date = st.date_input('Start Date', value=pd.Timestamp.now(tz='US/Pacific') - pd.Timedelta(days=7), format="MM/DD/YYYY")
    end_date = st.date_input('End Date', value=pd.Timestamp.now(tz='US/Pacific'), format="MM/DD/YYYY")

    df = chargepoint_past_sessions(start_date, end_date)
    if len(df) > 0:
        st.write(df)

        df = df.sort_values('startTime', ascending=False)
        # Change station name from VTA / STATION #1 to VTA STATION #1
        df['stationName'] = df['stationName'].str.replace(' / ', ' ')
        df['totalChargingDuration'] = pd.to_timedelta(df['totalChargingDuration'])
        df['totalSessionDuration'] = pd.to_timedelta(df['totalSessionDuration'])
        df['timeIdle'] = df['totalSessionDuration'] - df['totalChargingDuration']
        df['totalSessionDuration'] = format_duration(df['totalSessionDuration'])
        df['totalChargingDuration'] = format_duration(df['totalChargingDuration'])
        df['timeIdle'] = format_duration(df['timeIdle'])

        df['startTime'] = pd.to_datetime(df['startTime']).dt.tz_convert('US/Pacific')
        df['endTime'] = pd.to_datetime(df['endTime']).dt.tz_convert('US/Pacific')
        # df = df.drop(columns=['totalChargingDuration', 'totalSessionDuration'])
        df['vehicle'] = df['vehiclePortMAC'].map(data.mac_to_name)
        # replace stopBatteryPercent with start + energy if stopBatteryPercent is less than start
        df['stopBatteryPercentage'] = np.where(df['stopBatteryPercentage'] < df['startBatteryPercentage'],
                                                df['startBatteryPercentage'] + df['Energy'] / 440 * 100,
                                                df['stopBatteryPercentage'])
        df['stopBatteryPercentage'] = df['stopBatteryPercentage'].astype(int)

        # remove when charging duration is 0 minutes (for some reason there is a lot)
        df = df[df['totalChargingDuration'] != '0 minutes']

        df['stationName'] = df['stationName'].str.replace('VTA STATION #', 'Station ')
        # replace 0 minutes with none (not str)
        df['timeIdle'] = df['timeIdle'].replace('0 minutes', np.nan)
        st.dataframe(df, 
                    hide_index=True, use_container_width=True,
                    column_config={
                        "stationName": st.column_config.TextColumn("Station Name"),
                            "vehicle": st.column_config.TextColumn("Coach"),
                        "startTime": st.column_config.DatetimeColumn("Start Time", 
                                                                    format="MM/DD/YY h:mmA"),
                            "endTime": st.column_config.DatetimeColumn("End Time",
                                                                        format="MM/DD/YY h:mmA"),
                            "energy": st.column_config.NumberColumn("Energy (kWh)"),
                            "totalChargingDuration": st.column_config.TextColumn("Charging Duration"),
                            "totalSessionDuration": st.column_config.TextColumn("Session Duration"),
                            "timeIdle": st.column_config.TextColumn("Time Idle"),
                            "startBatteryPercentage": st.column_config.ProgressColumn("Start SOC (%)",
                                                                                    format='%d%%',
                                                                                    min_value=0,max_value=100),
                            "stopBatteryPercentage": st.column_config.ProgressColumn("End SOC (%)",
                                                                                    format='%d%%',
                                                                                    min_value=0,max_value=100),
                            "endedBy": st.column_config.TextColumn("Ended By"),
                    },
                        column_order=[
                            "vehicle",
                            "stationName",
                            "startBatteryPercentage",
                            "stopBatteryPercentage",
                            "totalChargingDuration",
                            "totalSessionDuration",
                            "timeIdle",
                            "startTime",
                            "endTime",
                            # "energy",
                            "endedBy",
                        ])

        # make time_zone unaware
        df_copy = df.copy()
        df_copy['startTime'] = df_copy['startTime'].dt.tz_localize(None)
        df_copy['endTime'] = df_copy['endTime'].dt.tz_localize(None)
        df_copy['startTime'] = df_copy['startTime'].dt.strftime('%m/%d/%y %I:%M %p')
        df_copy['endTime'] = df_copy['endTime'].dt.strftime('%m/%d/%y %I:%M %p')
        csv = df_copy.to_csv(index=False).encode('utf-8')
    else:
        st.info("No charging history found for this time period.")