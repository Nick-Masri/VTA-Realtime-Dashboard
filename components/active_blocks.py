import streamlit as st
from calls.supa_select import supabase_blocks
from calls.swiftly import swiftly_active_blocks
import pandas as pd
import pytz


def get_active_blocks():
    swiftly_df = swiftly_active_blocks()
    supabase_df = supabase_blocks()

    if swiftly_df is None and supabase_df is not None:
        return supabase_df.copy()
    elif supabase_df is None and swiftly_df is not None:
        return swiftly_df.copy()
    elif swiftly_df is not None and supabase_df is not None:
        # st.write(swiftly_df)
        # st.write(supabase_df)
        merged_df = pd.merge(swiftly_df, supabase_df, on='coach', how='outer', suffixes=('', '_y'))
        merged_df = merged_df.sort_values('created_at', ascending=False)
        merged_df.drop_duplicates(subset='coach', keep='first', inplace=True)
        # st.write(merged_df)
        return merged_df
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
        california_tz = pytz.timezone('US/Pacific')
        merged_df['last_transmission'] = pd.to_datetime(merged_df['last_transmission']).dt.tz_convert(california_tz)

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
                         format="hh:mmA MM/DD/YYYY",
                         # timezone=california_tz
                     )
                 })
