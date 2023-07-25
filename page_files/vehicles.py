import streamlit as st
from dotenv import load_dotenv
import os
from supabase import Client, create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from calls.supa_select import supabase_soc_history

import pytz
from components.vehicle_map import vehicle_map
from page_files.history import show_history , get_block_data, show_and_format_block_history
from page_files.dashboard import make_transmission_hrs

def transmission_formatting():


    # format the columns
    column_order=['vehicle', 'soc',  'last_transmission', 'odometer', 'status', 'fault']
    column_config={
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
        ),
        "last_transmission": st.column_config.DatetimeColumn(
            "Last Transmission Time",
            help="Time of Last Transmission",
            format="h:mmA MM/DD/YYYY",
        ),
        "status": st.column_config.CheckboxColumn("Status"),
        "fault": st.column_config.TextColumn("Fault")
    }
    
    return column_order, column_config

def show_most_recent(df):
    st.subheader("Transmissions")

    # get the formatting for the columns
    column_order, column_config = transmission_formatting()

    df = df.copy()

    # Display Vehicle Visual Status indicator
    hours_df = df.copy()
    hours_df = make_transmission_hrs(hours_df)
    hours_df = hours_df.sort_values('transmission_hrs', ascending=True)
    hours_df = hours_df.drop_duplicates(subset=['vehicle'], keep='first')
    hours = hours_df['transmission_hrs'].iloc[0]
    last_seen = hours_df['last_seen'].iloc[0]
    # four levels
    options = ['🟢', '🟡', '🔴']
    if hours <= 2:
        st.caption(f'🟢 Last transmission was {last_seen} ago')
    elif hours <= 12:
        st.caption(f'🟡 Last transmission was {last_seen} ago')
    else:
        st.caption(f'🔴 Last transmission was {last_seen} ago')  


    # remove asterix from fault column
    df['fault'] = df['fault'].str.replace('*', '', regex=False)

    # convert last transmission to local time
    utc = pytz.timezone('UTC')
    california_tz = pytz.timezone('US/Pacific')
    df['last_transmission'] = pd.to_datetime(df['last_transmission'])
    df['last_transmission'] = df['last_transmission'].dt.tz_localize(utc).dt.tz_convert(california_tz)
    most_recent = df.drop_duplicates(subset=['vehicle'], keep='first')

    if most_recent['last_transmission'].iloc[0] <  datetime(2023, 6, 30).astimezone(california_tz):
        inactive = True
    else:
        inactive = False

    if not inactive:
        show_all = st.checkbox('Show All')
    else: 
        show_all = False
    
    if show_all:
        all_df = df.sort_values('last_transmission', ascending=False)
        all_df = all_df.drop_duplicates(subset=['last_transmission'], keep='first')
        st.dataframe(all_df, hide_index=True, use_container_width=True,
                    column_order=column_order,
                    column_config=column_config)
    else:
        st.caption("Most Recent Transmission")

        # if most_recent['last_transmission'].iloc[0] <  datetime.now(tz=california_tz) - timedelta(days=1):
        #     st.warning("Vehicle has not transmitted in over 24 hours. Data may be outdated.")
            
        st.dataframe(most_recent, hide_index=True, use_container_width=True,
                    column_order=column_order,
                    column_config=column_config)

    return inactive

def show_vehicles():
    
    options = [f'750{x}' for x in range(1, 6)] + [f'950{x}' for x in range(1, 6)]

    vehicle = st.selectbox(
        'Select a vehicle',
        options)

    df = supabase_soc_history(vehicle=vehicle)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at', ascending=False)
    data = {"coaches": "All", "start_date": df.created_at.min(), "end_date": df.created_at.max()}
    vehicles = pd.DataFrame(data, index=[0])
    vehicles.start_date = pd.to_datetime(vehicles.start_date)
    vehicles.end_date = pd.to_datetime(vehicles.end_date)

    filtered_df = df[df.vehicle == vehicle]
    filtered_df = filtered_df.sort_values('created_at')
    # Calculate the energy lost and gained
    filtered_df['energy_change'] = filtered_df['soc'].diff()

    # Display map
    vehicle_map(vehicle)

    # Show the most recent transmission
    inactive = show_most_recent(df)
    df = df.drop(columns=['created_at'])

    # Get the active blocks from supabase
    blocks = get_block_data()
    blocks = blocks[blocks['coach'] == vehicle]
    if not inactive:
        st.write("## History")
        show_and_format_block_history(blocks, df, key="vehicle")
        
        fig = px.area(filtered_df,
                    x=filtered_df['created_at'],
                    y=filtered_df['soc'])
        # Set the layout for the chart
        fig.update_layout(
            title=f'State of Charge for Coach {vehicle}',
            # title size
            title_font_size=20,
            xaxis_title="Date Recorded",
            yaxis_title="State of Charge Percentage (%)",
            yaxis_range=[-5, 105]
        )

        # Render the scatter plot in Streamlit
        st.plotly_chart(fig, use_container_width=True)

