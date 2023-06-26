import folium
from streamlit_folium import folium_static, st_folium
import requests
from google.transit import gtfs_realtime_pb2
from protobuf_to_dict import protobuf_to_dict
import streamlit as st


def vehicle_map():
    st.subheader("Realtime Vehicle Map")
    api_key = "bcfb0797-65e1-494a-ab8d-054b48f0e111"
    url = f"http://api.511.org/Transit/VehiclePositions?api_key={api_key}&agency=RG"
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(url)
    feed.ParseFromString(response.content)

    old_buses = [f'750{x}' for x in range(1, 6)]
    new_buses = [f'950{x}' for x in range(1, 6)]
    ebuses = old_buses + new_buses

    output_dict = protobuf_to_dict(feed)
    entities = output_dict['entity']

    # Create a Folium Map object centered around the Cerone Bus Yard
    m = folium.Map(location=[37.414063, -121.927171], zoom_start=11)

    # Offset for closely located points
    offset = 0.0008

    for entity in entities:
        if entity['id'] in ebuses:
            # coach_header = f"Coach {entity['id']}"
            # st.subheader(coach_header)
            lat = entity['vehicle']['position']['latitude']
            lon = entity['vehicle']['position']['longitude']
            speed = entity['vehicle']['position']['speed']
            popup_text = f"Coach: {entity['id']}<br>Latitude: {lat}<br>Longitude: {lon}<br>Speed: {speed}"
            # Add an offset to the latitude for better marker visibility
            lat_offset = lat + offset
            folium.Marker(location=[lat_offset, lon], popup=popup_text).add_to(m)

    # Display the Folium Map
    folium_static(m)
