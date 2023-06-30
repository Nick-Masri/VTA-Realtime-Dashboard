import pandas as pd
import streamlit as st
import requests
from datetime import timedelta, datetime
import os
import xml.etree.ElementTree as ET
import requests


def show_apis():
    st.write("# Swiftly")
    st.write("## Vehicles API Fetch with Unassigned = True")
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

    st.markdown("""<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True)

    st.write("## GTFS")
    st.caption("Waiting on response email from swiftly")
    st.write("## Blocks Api")
    st.write("Used on dashboard for buses on routes")
    st.markdown("""<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True)

    st.write("# GTFS")
    st.caption("Holding off until I hear back from swiftly and try theirs out")
    # st.write("## Realtime Vehicle Positions")
    # st.write("Used on location for map")
    # api_key = "bcfb0797-65e1-494a-ab8d-054b48f0e111"
    # url = f"http://api.511.org/Transit/VehiclePositions?api_key={api_key}&agency=RG"
    # feed = gtfs_realtime_pb2.FeedMessage()
    # response = requests.get(url)
    # feed.ParseFromString(response.content)
    # 
    # old_buses = [f'750{x}' for x in range(1, 6)]
    # new_buses = [f'950{x}' for x in range(1, 6)]
    # ebuses = old_buses + new_buses
    # 
    # output_dict = protobuf_to_dict(feed)
    # entities = output_dict['entity']
    # 
    # # Create a Folium Map object centered around the Cerone Bus Yard
    # m = folium.Map(location=[37.414063, -121.927171], zoom_start=11)
    # 
    # # Offset for closely located points
    # offset = 0.0001
    # 
    # for entity in entities:
    #     if entity['id'] in ebuses:
    #         coach_header = f"Coach {entity['id']}"
    #         st.subheader(coach_header)
    #         for key, value in entity['vehicle']['position'].items():
    #             if key != 'bearing':
    #                 st.write(str(key).upper(), ":\t", value)
    #                 if key in ['latitude', 'longitude']:
    #                     lat = value
    #                     lon = entity['vehicle']['position']['longitude']
    #                     speed = entity['vehicle']['position']['speed']
    #                     popup_text = f"Coach: {entity['id']}<br>Latitude: {lat}<br>Longitude: {lon}<br>Speed: {speed}"
    #                     # Add an offset to the latitude for better marker visibility
    #                     lat_offset = lat + offset
    #                     folium.Marker(location=[lat_offset, lon], popup=popup_text).add_to(m)
    # 
    # # Display the Folium Map
    # folium_static(m)

    st.write("# Inrix")

    st.markdown("""<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True)

    st.write("# Chargepoint")


    # Define the SOAP XML namespace
    soap_namespace = {"soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
                      "urn": "urn:dictionary:com.chargepoint.webservices",
                      "wsse": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"}

    # Define the API license key and password
    from dotenv import load_dotenv
    load_dotenv()
    license_key = os.getenv('CHARGEPOINT_KEY')
    password = os.getenv('CHARGEPOINT_PASSWD')

    # Create the SOAP XML payload
    envelope = ET.Element("soapenv:Envelope", soap_namespace)
    header = ET.SubElement(envelope, "soapenv:Header")
    security = ET.SubElement(header, "wsse:Security", attrib={"soapenv:mustUnderstand": "1"})
    username_token = ET.SubElement(security, "wsse:UsernameToken")
    username = ET.SubElement(username_token, "wsse:Username")
    username.text = license_key
    password_element = ET.SubElement(username_token, "wsse:Password", attrib={
        "Type": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText"})
    password_element.text = password
    body = ET.SubElement(envelope, "soapenv:Body")
    get_public_stations = ET.SubElement(body, "urn:getPublicStations")
    search_query = ET.SubElement(get_public_stations, "searchQuery")
    # address = ET.SubElement(search_query, "Address")
    # address.text = "1692 Dell Avenue"
    city = ET.SubElement(search_query, "City")
    city.text = "San Jose"
    state = ET.SubElement(search_query, "State")
    state.text = "CA"
    # postal_code = ET.SubElement(search_query, "postalCode")
    # postal_code.text = "95008"
    proximity = ET.SubElement(search_query, "Proximity")
    proximity.text = "10"
    proximity_unit = ET.SubElement(search_query, "proximityUnit")
    proximity_unit.text = "M"

    # Convert the SOAP XML payload to a string
    xml_payload = ET.tostring(envelope, encoding="utf-8", method="xml")

    # Define the API endpoint URL
    url = "https://webservices.chargepoint.com/webservices/chargepoint/services/5.1"

    # Set the SOAPAction header
    headers = {
        "Content-Type": "text/xml;charset=UTF-8",
        "SOAPAction": "urn:getPublicStations"
    }

    # Send the SOAP request
    response = requests.post(url, data=xml_payload, headers=headers)

    # Print the SOAP response
    print(response.content)
