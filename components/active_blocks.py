import streamlit as st
import requests
import pandas as pd


def get_active_blocks():
    # Fetch data from API
    url = "https://api.goswift.ly/real-time/vta/active-blocks"
    headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}
    response = requests.get(url, headers=headers)
    json_data = response.json()

    # Extract relevant data and create DataFrame
    block_data = json_data["data"]["blocksByRoute"]
    df = pd.DataFrame(block_data)
    # df["id"] = pd.to_numeric(df["id"], errors="coerce")
    # filtered_df = df[df["id"].isin([70, 71, 77, 104])]
    # st.write(filtered_df)
    # st.write(df)

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
    old_buses = [f'750{x}' for x in range(1, 6)]
    new_buses = [f'950{x}' for x in range(1, 6)]
    ebuses = old_buses + new_buses
    # st.write(merged_df)

    merged_df = merged_df[merged_df.coach.isin(ebuses)]
    return merged_df.copy()


def show_active_blocks():
    st.subheader("Out on Routes")
    st.write("Predicted Arrival Time from Swiftly")

    merged_df = get_active_blocks()

    # Display the DataFrame
    st.dataframe(merged_df, hide_index=True,
                 column_order=['coach', 'id', 'block_id', 'block_startTime', 'block_endTime', 'isPredictable',
                               'schAdhSecs', 'predictedArrival'],
                 column_config={
                     "coach": st.column_config.TextColumn("Coach"),
                     "id": st.column_config.TextColumn("Route ID"),
                     "block_id": st.column_config.TextColumn("Block ID"),
                     "block_startTime": st.column_config.TimeColumn("Scheduled Start Time", format="hh:mmA"),
                     "block_endTime": st.column_config.TimeColumn("Scheduled End Time", format="hh:mmA"),
                     "predictedArrival": st.column_config.TimeColumn("Predicted Arrival Time",
                                                                     format="hh:mmA")
                 })
