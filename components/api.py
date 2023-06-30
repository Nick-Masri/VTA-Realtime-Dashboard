import pandas as pd
import streamlit as st
import requests
from datetime import timedelta, datetime
import os
from zeep import Client
from zeep.transports import Transport
import requests
from zeep.wsse.username import UsernameToken
from zeep.helpers import serialize_object
import numpy as np
import pydeck as pdk



def swiftly_vehicles():
    st.write("Vehicles API Fetch with Unassigned = True")
    # Define API endpoint and headers
    url = "https://api.goswift.ly/real-time/vta/vehicles"
    headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}
    querystring = {"unassigned": "True"}

    # Send GET request to API endpoint and retrieve JSON response
    response = requests.get(url, headers=headers, params=querystring)
    json_data = response.json()

    # Extract vehicles data from JSON response
    vehicles_data = json_data["data"]["vehicles"]

    # Create pandas DataFrame from vehicles data
    df = pd.DataFrame(vehicles_data)

    # filter for only ebuses
    df['id'] = df['id'].astype(str)
    ids_to_filter = ['7501', '7502', '7503', '7504', '7505', '9501', '9502', '9503', '9504', '9505']
    filtered_df = df[df['id'].isin(ids_to_filter)]

    st.write("See if ebuses show up in vehicles fetch")
    # filtered_df = filtered_df[['id', 'routeId']]
    # make loc column from dictionary to
    filtered_df['lat'] = filtered_df['loc'].apply(lambda x: x['lat'])
    filtered_df['lon'] = filtered_df['loc'].apply(lambda x: x['lon'])
    filtered_df['speed'] = filtered_df['loc'].apply(lambda x: x['speed'])
    # filtered_df['timestamp'] = filtered_df['loc'].apply(lambda x: x['time'])
    # filtered_df['timestamp'] = pd.to_datetime(filtered_df['timestamp'])
    filtered_df['timestamp'] = filtered_df['loc'].apply(lambda x: datetime.fromtimestamp(x['time']))

    filtered_df = filtered_df[['id', 'routeId', 'lat', 'lon', 'speed', 'timestamp']]
    st.dataframe(filtered_df,
                 use_container_width=True,
                 hide_index=True,
                 column_config={
                     "id": st.column_config.TextColumn(
                         "Coach",
                         width="medium"
                     ),
                     "routeId": st.column_config.TextColumn(
                         "Route ID",
                         width="medium"
                     )
                 })

def show_apis():
    st.write("# Chargepoint")
    # chargepoint()
    st.write("Used on Chargers Tab")

    with st.expander("Swiftly"):
        st.write("## Vehicles")
        swiftly_vehicles()

        st.write("GTFS")
        st.write("Waiting on response email from swiftly")
        
    with st.expander("Blocks Api"):
        st.write("Used on dashboard for buses on routes")

    with st.expander("GTFS from 511"):    
        st.write("Holding off until I hear back from swiftly and try theirs out")
        st.write("Used 511.org previously for location but ended up replacing with swiftly")

    with st.expander("Inrix"):
        st.write("Waiting for credentials")



