import streamlit as st
import pandas as pd
import os
from zeep import Client
from zeep.wsse.username import UsernameToken
from zeep.helpers import serialize_object
import pydeck as pdk
import datetime

@st.cache_resource
def chargepoint_client():
    # Import required modules
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()
    license_key = st.secrets["CHARGEPOINT_KEY"]
    password = st.secrets["CHARGEPOINT_PASSWD"]
    # Define the API endpoint URL
    url = "https://webservices.chargepoint.com/cp_api_5.1.wsdl"

    # Create a Zeep client with proper authentication
    wsse = UsernameToken(license_key, password)
    client = Client(url, wsse=wsse)
    return client

def chargepoint_locations():
    addresses = {
        # station 1-4
        'loc 1': 'Holger Way, San Jose, California, 95134, United States',
        # station 5
        'loc 2': 'Coyote Creek Trail, San Jose, California, 95134, United States',
    }

    station_ids = {
        'VTA / STATION #1': '1:1804421',
        'VTA / STATION #2': '1:1695951',
        'VTA / STATION #3': '1:1804511',
        'VTA / STATION #4': '1:1804551',
        'VTA / STATION #5': '1:1696131',
        # 'VTA STATION #6': '1:162215',
    }

    return (addresses, station_ids)

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(minutes=5))
def chargepoint_active_sessions():
    (addresses, station_ids) = chargepoint_locations()
    client = chargepoint_client()
    df = pd.DataFrame()
    for name, station_id in station_ids.items():
        queryString = {
            'stationID': station_id,
            'activeSessionsOnly': True
        }
        data = client.service.getChargingSessionData(queryString)
        # code = data['responseCode']
        # text = data['responseText']
        # more = data['MoreFlag']
        charging_data = data['ChargingSessionData']
        charge_data = serialize_object(charging_data)
        charge_df = pd.json_normalize(charge_data)
        if len(charge_df) > 0:
            charge_df['stationName'] = name
            # st.write(charge_df)
            # TODO: add total time not charging and if it exists 
            # then add a checkbox saying able to remove
            charge_df['Charging'] = True
            charge_df = charge_df[["stationName", "Energy", "startTime", "endTime", 
                                   "totalChargingDuration", "totalSessionDuration",
                                      "startBatteryPercentage", 
                                      "stopBatteryPercentage", "Charging",
                                      "vehiclePortMAC"
                                    #   "stopBatteryPercentage", "endedBy"
                                      ]]
            temp = charge_df
        else:
            temp = {"stationName": name,
                    # "chargingData": charging_data, 
                    "Charging": True if len(charging_data) > 0 else False}
            
        df = pd.concat([df, pd.DataFrame(temp, index=[0])], ignore_index=True)
    return df.copy()

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(hours=2))
def chargepoint_past_sessions(start_date, end_date):
    (addresses, station_ids) = chargepoint_locations()
    client = chargepoint_client()
    df = pd.DataFrame()
    for name, station_id in station_ids.items():
        queryString = {
            'stationID': station_id,
            'fromTimeStamp': start_date,
            'toTimeStamp': end_date,
        }
        data = client.service.getChargingSessionData(queryString)
        # code = data['responseCode']
        # text = data['responseText']
        # more = data['MoreFlag']
        charging_data = data['ChargingSessionData']
        charge_data = serialize_object(charging_data)
        charge_df = pd.json_normalize(charge_data)
        if len(charge_df) > 0:
            charge_df['stationName'] = name
            
            df = pd.concat([df, charge_df], ignore_index=True)
    return df

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(hours=2))
def chargepoint_stations():
    client = chargepoint_client()
    usageSearchQuery = {
        'stationModel': 'CPE250C-500-CCS1-CHD',
    }
    response = client.service.getStations(usageSearchQuery)
    # st.write(response['stationData'])
    data = serialize_object(response)
    # df = pd.json_normalize(data['stationData'])
    df = pd.json_normalize(data['stationData'], 'Port', ['stationName', 'Address', 'networkStatus'])

    df = df.sort_values('stationName')
    df = df[["stationName",
                    "Address",
                    "Status",
                    "networkStatus",
                    "Voltage",
                    "Current",
                    "Power",
                    "Geo.Lat",
                    "Geo.Long"]]

    return df

# currently unused
def chargepoint_map(df):
    positions = df[['stationName', 'Geo.Lat', 'Geo.Long']]
    positions = positions.rename(columns={'Geo.Lat': 'LAT', 'Geo.Long': 'LON'})
    positions['LAT'] = positions['LAT'].astype(float)
    positions['LON'] = positions['LON'].astype(float)

    # Calculate the center latitude and longitude
    center_lat = (positions['LAT'].min() + positions['LAT'].max()) / 2
    center_lon = (positions['LON'].min() + positions['LON'].max()) / 2

    # Create the PyDeck Deck
    deck = pdk.Deck(
        tooltip={"text": "{stationName}"},
        map_style=None,
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=19,
            pitch=50,
        ),
        layers=[pdk.Layer(
                'ScatterplotLayer',
                data=positions,
                get_position='[LON, LAT]',
                get_color='[200, 30, 0, 160]',
                get_radius=1.8,
                pickable=True,
                filled=True
            )])


    # Render the PyDeck Deck using Streamlit
    st.pydeck_chart(deck)

