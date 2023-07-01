from datetime import datetime
import streamlit as st
from calls.supa_select import supabase_blocks
from calls.swiftly import swiftly_active_blocks
import pandas as pd
import pytz


def get_active_blocks():
    swiftly_df = swiftly_active_blocks()
    supabase_df = supabase_blocks()
    tz = pytz.timezone('US/Pacific')
    if swiftly_df is None and supabase_df is not None:
        df = supabase_df.copy()
    elif supabase_df is None and swiftly_df is not None:
        df = swiftly_df.copy()
    elif swiftly_df is not None and supabase_df is not None:
        df = pd.concat([swiftly_df, supabase_df]) \
            .sort_values(['created_at', 'coach'], ascending=False) \
            .drop_duplicates(subset='coach', keep='first')
        df = df.copy()

    df['predictedArrival'] = pd.to_datetime(df['predictedArrival'])
    # need this line to remove the current (incorrect) timezone of utc
    df['predictedArrival'] = df['predictedArrival'].dt.tz_localize(None)
    df['predictedArrival'] = df['predictedArrival'].dt.tz_localize(tz)
    df = df[df['predictedArrival'] > datetime.now(tz=tz)]

    if len(df) > 0:
        return df.copy()
    else:
        return None


def show_active_blocks(merged_df=get_active_blocks()):
    if len(merged_df) > 0:
        st.subheader("Out on Routes")
        st.caption("Predicted Arrival Time from Swiftly")
        # st.write(merged_df)
        # Display the DataFrame

        # remove timezone again so it displays right
        merged_df['predictedArrival'] = pd.to_datetime(merged_df['predictedArrival']).dt.tz_localize(None)
        merged_df = merged_df.sort_values('transmission_hrs')
        merged_df = merged_df[
            ['coach', 'id', 'block_id', 'block_startTime', 'predictedArrival', 'soc',
             'last_seen']]

        st.dataframe(merged_df, hide_index=True,
                     use_container_width=True,
                     column_order=['coach', 'soc', 'last_seen', 'id', 'block_id', 'block_startTime', 'block_endTime',
                                   'predictedArrival', 'odometer', ],
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
                         # "last_transmission": st.column_config.DatetimeColumn(
                         #     "Last Transmission Time",
                         #     help="Time of Last Transmission",
                         #     format="h:mmA MM/DD/YYYY",
                         #     # timezone=california_tz
                         # ),
                         "last_seen": st.column_config.TextColumn("Time Offline")
                     })
