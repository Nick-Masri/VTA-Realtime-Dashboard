import streamlit as st
import requests
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import os


def get_active_blocks():
    # Fetch data from API
    url = "https://api.goswift.ly/real-time/vta/active-blocks"
    headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}
    response = requests.get(url, headers=headers)
    json_data = response.json()

    # Extract relevant data and create DataFrame
    block_data = json_data["data"]["blocksByRoute"]
    df = pd.DataFrame(block_data)
    old_buses = [f'750{x}' for x in range(1, 6)]
    new_buses = [f'950{x}' for x in range(1, 6)]
    ebuses = old_buses + new_buses
    df = df[df.id.isin(ebuses)]

    if len(df) > 0:

        # Explode "block" column into separate rows
        exploded_df = df.explode("block")
        exploded_df = exploded_df.reset_index(drop=True)
        block_df = pd.DataFrame(exploded_df["block"].to_list())
        block_df = block_df.add_prefix("block_")

        # Concatenate exploded DataFrame and block DataFrame
        final_df = pd.concat([exploded_df.drop("block", axis=1), block_df], axis=1)

        # Expand the 'block_vehicle' column
        expanded_df = final_df.explode('block_vehicle')
        expanded_df = expanded_df[['id', 'block_id', 'block_startTime', 'block_endTime', 'block_vehicle']]

        # Extract vehicle details from 'block_vehicle' column
        vehicle_df = expanded_df.block_vehicle.apply(pd.Series)
        vehicle_df = vehicle_df.rename(columns={"id": "coach"})

        # Concatenate expanded DataFrame and vehicle DataFrame
        merged_df = pd.concat([expanded_df, vehicle_df], axis=1)
        merged_df = merged_df[
            ['id', 'block_id', 'block_startTime', 'block_endTime', 'coach', 'isPredictable', 'schAdhSecs']]

        # Convert 'block_endTime' column to datetime format
        merged_df['block_endTime'] = pd.to_datetime(merged_df['block_endTime'], errors='coerce')

        # Calculate 'predictedArrival' by adding 'block_endTime' and 'schAdhSecs' columns
        merged_df['predictedArrival'] = merged_df['block_endTime'] + pd.to_timedelta(merged_df['schAdhSecs'], unit='s')

        merged_df.drop(columns=['isPredictable', 'schAdhSecs'], inplace=True)

        return merged_df.copy()
    else:
        # grab from supabase
        # Load environment variables
        load_dotenv()

        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)

        response = supabase.table('block_history').select("*").execute()
        data = response.data
        df = pd.DataFrame(data)
        df = df.drop(columns='id')

        df = df[df.created_at == df.created_at.max()]
        df = df.rename(columns={"start_time": "block_startTime", "end_time": "block_endTime",
                                "predicted_arrival": "predictedArrival", "route_id": "id"})
        # st.write(df)
        return df.copy()


def show_active_blocks(merged_df=get_active_blocks()):
    if len(merged_df) > 0:
        st.subheader("Out on Routes")
        st.caption("Predicted Arrival Time from Swiftly")

        # Display the DataFrame
        merged_df = merged_df[
            ['coach', 'id', 'block_id', 'block_startTime', 'block_endTime', 'predictedArrival', 'soc']]

    st.dataframe(merged_df, hide_index=True,
                 column_order=['coach', 'soc', 'id', 'block_id', 'block_startTime', 'block_endTime',
                               'predictedArrival'],
                 column_config={
                     "coach": st.column_config.TextColumn("Coach"),
                     "id": st.column_config.TextColumn("Route"),
                     "block_id": st.column_config.TextColumn("Block"),
                     "block_startTime": st.column_config.TimeColumn("Start Time", format="hh:mmA"),
                     "block_endTime": st.column_config.TimeColumn("End Time", format="hh:mmA"),
                     "predictedArrival": st.column_config.TimeColumn("Predicted Arrival Time",
                                                                     format="hh:mmA"),
                     "soc": st.column_config.ProgressColumn("State of Charge",
                                                            help="Battery Percentage of Bus",
                                                            format="%d%%",
                                                            width='medium',
                                                            min_value=0,
                                                            max_value=100, )
                 })
