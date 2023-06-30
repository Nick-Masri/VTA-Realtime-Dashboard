import pandas as pd
import streamlit as st
import requests
from datetime import timedelta, datetime
import os
from zeep import Client
from zeep.transports import Transport
import requests
from zeep.wsse.username import UsernameToken

def chargepoint():

    # Import required modules
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()
    license_key = os.getenv('CHARGEPOINT_KEY')
    password = os.getenv('CHARGEPOINT_PASSWD')

    # Define the API endpoint URL
    url = "https://webservices.chargepoint.com/cp_api_5.1.wsdl"

    # Create a Zeep client with proper authentication
    wsse = UsernameToken(license_key, password)
    client = Client(url, wsse=wsse)
    tStart = datetime(2023, 5, 23)
    tEnd = tStart + timedelta(days=10)

    usageSearchQuery = {
        'Address': '3990 Zanker Rd',
        'City': 'San Jose',
        'State': 'California',
        'Country': 'United States',
        'Proximity': 0.4,
        'postalCode': '95134',
    }

    station_ids = {
        'VTA STATION #1': '1:1804421',
        'VTA STATION #2': '1:1695951',
        'VTA STATION #3': '1:1804511',
        'VTA STATION #4': '1:1804551',
        'VTA STATION #5': '1:1696131',
        'VTA STATION #6': '1:162215',
    }

    addresses = {
        'station 1-4': 'Holger Way, San Jose, California, 95134, United States',
        'station 5': 'Coyote Creek Trail, San Jose, California, 95134, United States',
    }

    # data = client.service.getChargingSessionData(usageSearchQuery)
    # st.write(data['responseText'])
    # st.write(data)
    # df = pd.DataFrame(data)
    # st.write(df)

    # data = client.service.getChargingSessionData(stationQuery)
    queryString = {
        'Address': 'Holger Way, San Jose, California, 95134, United States',
        # 'Proximity': 2,
        # 'proximityUnit': 'M',
        'activeSessionsOnly': True,
    }
    data = client.service.getChargingSessionData(queryString)
    st.write(data['responseText'])
    st.write(data)
    df = pd.DataFrame(data)
    st.write(df)


    # data = client.service.getStations(usageSearchQuery)
    # st.write(data)
    # st.write(data['responseText'])
    # df = pd.DataFrame(data)
    # st.write(df)
    # other_df = pd.DataFrame()
    # st.write(data['responseText'])
    # st.write(other_df)
    # charge_df = pd.DataFrame(data['ChargingSessionData'])
    # st.write(charge_df)
    # st.write(df)
    # st.write(data.__dict__)

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
    # st.write(df)

    # Convert 'id' column to string (if it's not already)
    df['id'] = df['id'].astype(str)

    # Filter DataFrame by list of ids (as strings)
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
    chargepoint()

    with st.expander("Swiftly"):
        st.write("## Vehicles")
        swiftly_vehicles()

        st.write("GTFS")
        st.write("Waiting on response email from swiftly")
        
    with st.expander("Blocks Api"):
        st.write("Used on dashboard for buses on routes")

    with st.expander("GTFS from 511"):    
        st. write("Holding off until I hear back from swiftly and try theirs out")
        st.write("Used 511.org previously for location but ended up replacing with swiftly")

    with st.expander("Inrix"):
        st.write("Waiting for credentials")



