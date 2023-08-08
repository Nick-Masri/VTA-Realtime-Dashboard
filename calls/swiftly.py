import requests
import pandas as pd
import streamlit as st
import datetime
import data

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(minutes=5))
def swiftly_call_active_blocks():
    # Fetch data from API
    url = "https://api.goswift.ly/real-time/vta/active-blocks"
    headers = {"Authorization": st.secrets["SWIFTLY_AUTH"]}
    response = requests.get(url, headers=headers)
    json_data = response.json()

    # Extract relevant data and create DataFrame
    block_data = json_data["data"]["blocksByRoute"]
    df = pd.DataFrame(block_data)
    return df

@st.cache_data(show_spinner=False, max_entries=1)
def swiftly_active_blocks():
    df = swiftly_call_active_blocks()
    if len(df) > 0:
        exploded_df = df.explode("block").reset_index(drop=True)
        block_df = pd.DataFrame(exploded_df["block"].to_list()).add_prefix("block_")

        df = pd.concat([exploded_df, block_df], axis=1).drop("block", axis=1)
        df = df.explode('block_vehicle')

        vehicle_df = df.block_vehicle.apply(pd.Series).rename(columns={"id": "coach"})
        route_df = df.block_trip.apply(pd.Series).drop(columns=['id']).rename(columns={"routeId": "id"})

        df = pd.concat([df, vehicle_df, route_df], axis=1)
        df = df[
            ['id', 'block_id', 'block_startTime', 'block_endTime', 'coach', 'isPredictable', 'schAdhSecs']]

        df['block_endTime'] = pd.to_datetime(df['block_endTime'], errors='coerce', format='%H:%M:%S')
        df['predictedArrival'] = df['block_endTime'] + pd.to_timedelta(df['schAdhSecs'], unit='s')
        df['coach'] = df['coach'].astype(str)
        df.drop(columns=['isPredictable', 'schAdhSecs'], inplace=True)
        ebuses = data.ebuses
        df = df[df.coach.isin(ebuses)]

        return df
    else:
        return None