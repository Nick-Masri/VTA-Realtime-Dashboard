import datetime

import streamlit as st
from calls.supa_select import supabase_blocks
from calls.swiftly import swiftly_active_blocks
import pandas as pd
import pytz


def get_active_blocks():
    swiftly_df = swiftly_active_blocks()
    supabase_df = supabase_blocks()
    # st.write(swiftly_df)
    # st.write(supabase_df)

    if swiftly_df is None and supabase_df is not None:
        # filter out inactive blocks by date
        supabase_df['block_endTime'] = pd.to_datetime(supabase_df['block_endTime'])
        supabase_df = supabase_df[supabase_df['block_endTime'] > pd.to_datetime('now')]
        return supabase_df.copy()
    elif supabase_df is None and swiftly_df is not None:
        swiftly_df['block_endTime'] = pd.to_datetime(swiftly_df['block_endTime'])
        swiftly_df = swiftly_df[swiftly_df['block_endTime'] > pd.to_datetime('now')]
        return swiftly_df.copy()
    elif swiftly_df is not None and supabase_df is not None:
        df = pd.concat([swiftly_df, supabase_df])\
            .sort_values(['created_at', 'coach'], ascending=False)\
            .drop_duplicates(subset='coach', keep='first')
        df['block_endTime'] = pd.to_datetime(df['block_endTime']).dt.tz_localize('US/Pacific')
        df = df[df['block_endTime'] > pd.Timestamp.now(tz=pytz.timezone('US/Pacific'))]
        return df
    else:
        return None


def show_active_blocks(merged_df=get_active_blocks()):
    if len(merged_df) > 0:
        st.subheader("Out on Routes")
        st.caption("Predicted Arrival Time from Swiftly")
        # st.write(merged_df)
        # Display the DataFrame
        merged_df = merged_df[
            ['coach', 'id', 'block_id', 'block_startTime', 'block_endTime', 'predictedArrival', 'soc',
             'last_transmission', 'odometer']]

        merged_df['last_transmission'] = pd.to_datetime(merged_df['last_transmission']) + pd.Timedelta(hours=7)

        st.dataframe(merged_df, hide_index=True,
                     column_order=['coach', 'soc', 'id', 'block_id', 'block_startTime', 'block_endTime',
                                   'predictedArrival', 'odometer', 'last_transmission'],
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
                                                                max_value=100, ),
                         "odometer": st.column_config.NumberColumn(
                             "Odometer (mi)",
                             help="Bus Odometer Reading in miles",
                             # format="%d",
                         ),
                         "last_transmission": st.column_config.DatetimeColumn(
                             "Last Transmission Time",
                             help="Time of Last Transmission",
                             format="h:mmA MM/DD/YYYY",
                             # timezone=california_tz
                         )
                     })
