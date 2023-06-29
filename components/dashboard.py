# from streamlit_supabase_auth import login_form, logout_button

import pandas as pd
import streamlit as st

from calls.supa_select import supabase_soc
# import datetime.datetime as datetime
from components.active_blocks import show_active_blocks, get_active_blocks


def dashboard():
    # Load the active blocks DataFrame from swiftly API
    merged_df = get_active_blocks()

    # get soc from supabase
    df = supabase_soc()

    if merged_df is not None:
        merged_df = pd.merge(merged_df, df, left_on='coach', right_on='vehicle',
                             how='inner', suffixes=('', '_y'))
        merged_df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
        # st.write(merged_df)
        df = df[~df['vehicle'].isin(merged_df['vehicle'])]
        # california_tz = pytz.timezone('US/Pacific')
        # merged_df = pd.to_datetime(df['last_transmission']).dt.tz_convert(california_tz)
        # st.write(merged_df)
        show_active_blocks(merged_df)

    df['last_transmission'] = pd.to_datetime(df['last_transmission'])

    # Separate the DataFrame into active and inactive buses
    active_buses = df[df['status'] == True]
    inactive_buses = df[df['status'] == False]

    active_buses = active_buses.drop(columns=['status'])
    inactive_buses = inactive_buses.drop(columns=['status'])

    # dataframe string formatting
    column_config = {
        "soc": st.column_config.ProgressColumn(
            "State of Charge",
            help="Battery Percentage of Bus",
            format="%d%%",
            width='medium',
            min_value=0,
            max_value=100,
        ),
        "vehicle": st.column_config.TextColumn(
            "Coach",
            help="Bus Identification Number",
            # format="%d",
        ),
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
        ),
        "status": st.column_config.CheckboxColumn("Status")
    }

    # col_order = ['vehicle', 'soc', 'odometer', 'last_transmission']
    col_order = ['vehicle', 'soc', 'status', 'odometer', 'last_transmission', 'time_difference']

    st.subheader("Buses at Depot")
    df.sort_values('vehicle', inplace=True)
    st.dataframe(df, hide_index=True, column_config=column_config, column_order=col_order)
