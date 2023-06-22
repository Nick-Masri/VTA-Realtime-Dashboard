import datetime

import streamlit as st

import json
import os

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import time, timedelta, datetime, date


def convert_depart_index_to_time(depart_index):
    base_time = time(0, 0)  # Start with midnight as the base time
    increment = timedelta(minutes=15)  # Each index represents a 15-minute increment
    delta = increment * depart_index
    return (datetime.combine(date.today(), base_time) + delta).time()


def selection_process():
    # get config settings from YAML
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Convert the data to a JSON string
    config_json = json.dumps(config)

    # Mileage Data
    # mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}

    # Load environment variables
    load_dotenv()

    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    response = supabase.table('soc').select("*").execute()

    # Extract the data from the APIResponse object
    data = response.data

    # placeholder
    placeholder = pd.DataFrame()

    # Convert the data to a DataFrame
    df = pd.DataFrame(data)

    # make vehicle column text
    df['vehicle'] = df['vehicle'].astype(str)
    # Convert the 'created_at' column to datetime type
    df['created_at'] = pd.to_datetime(df['created_at'])
    # Sort the DataFrame by 'created_at' column in descending order
    df.sort_values(by='created_at', ascending=False, inplace=True)
    # Drop duplicate entries for each vehicle, keeping only the first (most recent)
    df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
    df = df[['soc', 'vehicle', 'odometer', 'status', 'last_transmission']]
    # Format the odometer column with thousands separator
    df['odometer'] = df['odometer'].apply(lambda x: "{:,}".format(x))
    # selected
    # df['selected'] = df['status'].apply(lambda x: x['status'])

    # Format the last_transmission column
    df['last_transmission'] = pd.to_datetime(df['last_transmission'])
    df['status_symbol'] = df['status'].apply(lambda x: "✅" if x else "🚫")

    df = df.sort_values('vehicle')
    # df['selection'] = df['status']
    # df['status'] = df['status'].astype(str)
    # df['last_transmission'] = df['last_transmission'].dt.strftime("%H:%M %m/%d/%y")

    # dataframe string formatting
    column_config = {
        "soc": st.column_config.NumberColumn(
            "State of Charge",
            help="Battery Percentage of Bus",
            format="%d%%",
            # width='medium',
            # min_value=0,
            # max_value=100,
        ),
        "vehicle": st.column_config.TextColumn(
            "Coach",
            help="Bus Identification Number",
            # format="%d",
            disabled=True
        ),
        "odometer": st.column_config.NumberColumn(
            "Odometer (mi)",
            help="Bus Odometer Reading in miles",
            # format="%d",
            disabled=True
        ),
        "last_transmission": st.column_config.DatetimeColumn(
            "Last Transmission Time",
            help="Time of Last Transmission",
            format="HH:mm MM/DD/YYYY",
            disabled=True
        ),
        "status": st.column_config.CheckboxColumn(
            "Select",
        ),
        "status_symbol": st.column_config.TextColumn(
            "Status",
            disabled=True
        )

    }

    col_order = ['status',
                 'status_symbol',
                 'vehicle', 'soc', 'odometer', 'last_transmission']

    # Separate the DataFrame into active and inactive buses
    active_buses = df[df['status'] == True]
    inactive_buses = df[df['status'] == False]

    # active_buses = active_buses.drop(columns=['status'])
    # inactive_buses = inactive_buses.drop(columns=['status'])
    with st.form("opt_input"):
        # Display the active buses DataFrame
        st.write("# Buses")
        active_buses.sort_values('vehicle', inplace=True)
        df = df.sort_values(['status', 'vehicle'], ascending=[False, True])
        data = st.data_editor(df, hide_index=True, column_config=column_config, column_order=col_order)

        st.write("# Blocks")
        blocks = pd.read_excel('allRoutes.xlsx')
        blocks['selection'] = True
        blocks['routeNum'] = blocks['routeNum'].astype(str)
        blocks['departIndex'] = blocks['departIndex'].apply(convert_depart_index_to_time)
        # Set up the grid options
        st.data_editor(blocks, hide_index=True,
                       column_config={
                           "routeNum": st.column_config.TextColumn(
                               "Block ID",
                               disabled=True
                           ),
                           "selection": st.column_config.CheckboxColumn(
                               "Select"
                           ),
                           "distance": st.column_config.NumberColumn(
                               "Block Mileage"
                           ),

                       },
                       column_order=['selection', 'routeNum', 'departIndex', 'returnIndex', 'distance']
                       )

        st.write("# Chargers ")
        data = {"id": range(1, 6), "selection": [True for i in range(1, 6)],
                "name": ["VTA Station #" + str(i) for i in range(1, 6)], 'status (from api)': True}

        chargers_df = pd.DataFrame(data)
        st.data_editor(chargers_df, hide_index=True, column_order=['selection', 'name', 'status (from api)', 'id', ],
                       column_config={
                           "selection": st.column_config.CheckboxColumn(
                               "Select"
                           )
                       })

        st.form_submit_button("Submit")
