from datetime import timedelta

import pandas as pd
import streamlit as st

from calls.supa_select import supabase_blocks
from calls.supa_select import supabase_soc_history


def performance():

    # Route History
    st.subheader("Service History")

    df = supabase_soc_history()
    df = df.sort_values('vehicle')
    df = df.drop(columns=['created_at'])
    # st.write(df)

    # Get the active blocks from supabase
    blocks = supabase_blocks(active=False)
    blocks['created_at'] = pd.to_datetime(blocks['created_at'])
    blocks['date'] = blocks['created_at'].dt.strftime('%Y-%m-%d')
    blocks = blocks.sort_values('created_at', ascending=False)
    blocks = blocks.drop_duplicates(subset=['date', 'coach'], keep='first')
    blocks = blocks.drop(columns=['created_at'])

    results = []

    for idx, row in blocks.iterrows():
        relevant_df = df[df['vehicle'] == row['coach']]
        relevant_df['last_transmission'] = pd.to_datetime(relevant_df['last_transmission'])

        block_start_time = pd.to_datetime(row['date'] + ' ' + row['block_startTime'])
        block_end_time = pd.to_datetime(row['date'] + ' ' + row['block_endTime'])

        relevant_starts = relevant_df[
            (relevant_df['last_transmission'] <= block_start_time + timedelta(hours=1)) &
            (relevant_df['last_transmission'] >= block_start_time - timedelta(hours=7))
            ]
        relevant_starts = relevant_starts.sort_values('last_transmission', ascending=False)

        if relevant_starts.empty:
            # Omit writing SOC and odometer changes
            start_soc = None
            start_odometer = None
            start_time_change = None
            start_trans = None
        else:
            start_soc = relevant_starts.iloc[0]['soc']
            start_odometer = relevant_starts.iloc[0]['odometer']

            # calculate time change between last_transmission and block_start_time in hours
            start_time_change = block_start_time - relevant_starts.iloc[0]['last_transmission']
            start_time_change = start_time_change.total_seconds() / 3600
            start_time_change = int(start_time_change)
            start_trans = relevant_starts.iloc[0]['last_transmission']

        relevant_ends = relevant_df[
            (relevant_df['last_transmission'] >= block_end_time - timedelta(hours=1)) &
            (relevant_df['last_transmission'] <= block_end_time + timedelta(hours=5))
            ]
        relevant_ends = relevant_ends.sort_values('last_transmission', ascending=True)

        if relevant_ends.empty:
            # Omit writing SOC and odometer changes
            end_soc = None
            end_odometer = None
            end_time_change = None
            end_trans = None
        else:
            soc_idx = relevant_ends.iloc[0:2]['soc'].argmin()
            end_soc = relevant_ends.iloc[soc_idx]['soc']

            end_odometer = relevant_ends.iloc[0:2]['odometer'].max()
            end_trans = relevant_ends.iloc[soc_idx]['last_transmission']

            # calculate time change between block_end_time and first_transmission in hours
            end_time_change = relevant_ends.iloc[soc_idx]['last_transmission'] - block_end_time
            end_time_change = end_time_change.total_seconds() / 3600
            end_time_change = int(end_time_change)

        soc_change = None if start_soc is None or end_soc is None else abs(end_soc - start_soc)
        miles_travelled = None if start_odometer is None or end_odometer is None else end_odometer - start_odometer
        # Calculate kWh used
        if start_soc is not None and end_soc is not None and miles_travelled is not None:
            soc_change = abs(end_soc - start_soc)
            kwh_used = soc_change / 100 * 440  # Assuming the bus has a 440 kWh capacity
            kwh_per_mile = kwh_used / miles_travelled
            if kwh_per_mile < 1 or kwh_per_mile > 4:
                kwh_per_mile = None
                kwh_used = None
                # start_soc = None
                # start_trans = None
                # start_time_change = None
                soc_change = None
                # end_trans = None
                end_soc = None
                # end_time_change = None
        else:
            kwh_used = None
            kwh_per_mile = None

        result = {
            'Vehicle': row['coach'],
            'Date': row['date'],
            'Start SOC (%)': start_soc,
            'End SOC (%)': end_soc,
            'SOC Change (%)': soc_change,
            'Start Odometer': start_odometer,
            'End Odometer': end_odometer,
            'Start Trans': start_trans,
            'End Trans': end_trans,
            "Miles Travelled": miles_travelled,
            "kWh Used": kwh_used,
            "kWh per Mile": kwh_per_mile,
            'Start Time Change (hrs)': start_time_change,
            'End Time Change (hrs)': end_time_change,
        }
        results.append(result)

    result_df = pd.DataFrame(results)
    # st.dataframe(result_df)

    # merge blocks and result_df
    block_col_config = {
        "coach": st.column_config.TextColumn("Coach"),
        "id": st.column_config.TextColumn("Route"),
        "block_id": st.column_config.TextColumn("Block"),
        "block_startTime": st.column_config.TimeColumn("Start Time", format="hh:mmA"),
        "block_endTime": st.column_config.TimeColumn("End Time", format="hh:mmA"),
        "predictedArrival": st.column_config.TimeColumn("Predicted Arrival Time",
                                                        format="hh:mmA"),
        "date": st.column_config.DateColumn("Date", format="MM/DD/YY")
    }
    block_col_order = ["date", "coach", "id", "block_id",
                       "block_startTime",
                       "block_endTime", "predictedArrival",
                       "Start SOC (%)", "End SOC (%)", "SOC Change (%)",
                       "Miles Travelled", "kWh per Mile",
                       ]

    blocks = blocks.merge(result_df, left_on=['coach', 'date'], right_on=['Vehicle', 'Date'], how='left')
    blocks = blocks.drop(columns=['Vehicle'])
    blocks = blocks.sort_values(by=['date', 'block_startTime'], ascending=False)
    show_details = st.checkbox("Toggle More Details")
    if show_details:
        block_col_order = ["date", "coach", "id", "block_id",
                           "block_startTime",
                           "Start Trans", "Start Time Change (hrs)",
                            "block_endTime", "predictedArrival",
                           "End Trans", "End Time Change (hrs)",
                           "Start SOC (%)", "End SOC (%)", "SOC Change (%)",
                           "Start Odometer", "End Odometer", "Miles Travelled", "kWh Used", "kWh per Mile",
                           ]

    st.dataframe(blocks, hide_index=True,
                 column_order=block_col_order,
                 column_config=block_col_config
                 )