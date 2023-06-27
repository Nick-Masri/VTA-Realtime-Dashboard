# from streamlit_supabase_auth import login_form, logout_button

import json
import os

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv
from supabase import create_client, Client
import pytz
from components.active_blocks import show_active_blocks, get_active_blocks


def dashboard():
    merged_df = get_active_blocks()

    # Load environment variables
    load_dotenv()

    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    response = supabase.table('soc').select("*").execute()

    # Extract the data from the APIResponse object
    data = response.data

    # Convert the data to a DataFrame
    df = pd.DataFrame(data)

    # make vehicle column text
    df['vehicle'] = df['vehicle'].astype('object')

    # Convert the 'created_at' column to datetime type
    df['created_at'] = pd.to_datetime(df['created_at'])

    # Sort the DataFrame by 'created_at' column in descending order
    df.sort_values(by='created_at', ascending=False, inplace=True)

    if len(merged_df) > 0:
        # drop ones currently on ruotes
        df = df[~df['vehicle'].isin(merged_df.vehicle.unique())]

    show_active_blocks(merged_df)

    # Drop duplicate entries for each vehicle, keeping only the first (most recent)
    df.drop_duplicates(subset='vehicle', keep='first', inplace=True)

    df = df[['soc', 'vehicle', 'odometer', 'status', 'last_transmission']]

    # Format the odometer column with thousands separator
    df['odometer'] = df['odometer'].apply(lambda x: "{:,}".format(x))

    # Convert last_transmission column to California timezone
    california_tz = pytz.timezone('America/Los_Angeles')
    df['last_transmission'] = pd.to_datetime(df['last_transmission']).dt.tz_convert(california_tz)

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
        )
    }

    col_order = ['vehicle', 'soc', 'odometer', 'last_transmission']

    # Display the active buses DataFrame
    st.subheader("Active Buses")
    active_buses.sort_values('vehicle', inplace=True)
    st.dataframe(active_buses, hide_index=True, column_config=column_config, column_order=col_order)

    # Display the inactive buses DataFrame
    st.subheader("Inactive Buses")
    inactive_buses.sort_values('vehicle', inplace=True)
    st.dataframe(inactive_buses, hide_index=True, column_config=column_config, column_order=col_order)
