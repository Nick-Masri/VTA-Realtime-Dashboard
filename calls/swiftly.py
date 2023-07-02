import requests
import pandas as pd
import streamlit as st

def swiftly_call_active_blocks():
    # Fetch data from API
    url = "https://api.goswift.ly/real-time/vta/active-blocks"
    headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}
    response = requests.get(url, headers=headers)
    json_data = response.json()

    # Extract relevant data and create DataFrame
    block_data = json_data["data"]["blocksByRoute"]
    df = pd.DataFrame(block_data)
    return df


def clean_active_blocks(df):
    # Explode "block" column into separate rows
    exploded_df = df.explode("block")
    exploded_df = exploded_df.reset_index(drop=True)
    block_df = pd.DataFrame(exploded_df["block"].to_list())
    block_df = block_df.add_prefix("block_")

    # Concatenate exploded DataFrame and block DataFrame
    df = pd.concat([exploded_df.drop("block", axis=1), block_df], axis=1)

    # Expand the 'block_vehicle' column
    expanded_df = df.explode('block_vehicle')
    expanded_df = expanded_df[['id', 'block_id', 'block_startTime', 'block_endTime', 'block_vehicle']]

    # Extract vehicle details from 'block_vehicle' column
    vehicle_df = expanded_df.block_vehicle.apply(pd.Series)
    vehicle_df = vehicle_df.rename(columns={"id": "coach"})

    # Concatenate expanded DataFrame and vehicle DataFrame
    df = pd.concat([expanded_df, vehicle_df], axis=1)
    df = df[
        ['id', 'block_id', 'block_startTime', 'block_endTime', 'coach', 'isPredictable', 'schAdhSecs']]

    df['block_endTime'] = pd.to_datetime(df['block_endTime'], errors='coerce')
    df['predictedArrival'] = df['block_endTime'] + pd.to_timedelta(df['schAdhSecs'], unit='s')
    df['coach'] = df['coach'].astype(str)
    df.drop(columns=['isPredictable', 'schAdhSecs'], inplace=True)
    ebuses = [f'750{i}' for i in range(1, 6)] + [f'950{i}' for i in range(1, 6)]
    df = df[df.coach.isin(ebuses)]

    return df


def swiftly_active_blocks():
    df = swiftly_call_active_blocks()
    if len(df) > 0:
        return clean_active_blocks(df)
    else:
        return None