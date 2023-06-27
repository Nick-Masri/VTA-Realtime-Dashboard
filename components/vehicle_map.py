import folium
from streamlit_folium import folium_static, st_folium
import requests
from google.transit import gtfs_realtime_pb2
from protobuf_to_dict import protobuf_to_dict
import random
import streamlit as st
import pandas as pd


def vehicle_map():
    st.subheader("Vehicle Map")
    st.caption("Zoomed in On Depot")
    api_key = "bcfb0797-65e1-494a-ab8d-054b48f0e111"
    url = f"http://api.511.org/Transit/VehiclePositions?api_key={api_key}&agency=RG"
    try:

        feed = gtfs_realtime_pb2.FeedMessage()
        response = requests.get(url)
        feed.ParseFromString(response.content)

        old_buses = [f'750{x}' for x in range(1, 6)]
        new_buses = [f'950{x}' for x in range(1, 6)]
        ebuses = old_buses + new_buses

        output_dict = protobuf_to_dict(feed)
        entities = output_dict['entity']

        # Create a Folium Map object centered around the Cerone Bus Yard
        m = folium.Map(location=[37.41845007126032, -121.93728511980153], zoom_start=14)

        # Offset for closely located points
        offset = 0.0002

        found_vehicles = pd.DataFrame(columns=['coach', 'position', 'at_depot'])

        for entity in entities:
            if entity['id'] in ebuses:
                lat = entity['vehicle']['position']['latitude'] + offset * random.choice([1, -1])
                lon = entity['vehicle']['position']['longitude'] + offset * random.choice([1, -1])
                speed = round(entity['vehicle']['position']['speed'], 2)
                popup_text = f"Coach: {entity['id']}<br>Latitude: {lat}<br>Longitude: {lon}<br>Speed: {speed}"
                folium.Marker(location=[lat, lon], popup=popup_text).add_to(m)
                temp = pd.DataFrame({"Coach": entity['id'], "Go To Position": False, "At Depot": "False"}, index=[0])
                found_vehicles = pd.concat([found_vehicles, temp], ignore_index=True)

        # st.data_editor(found_vehicles, hide_index=True, key="Map",
        #                column_config={
        #                    "position": st.column_config.CheckboxColumn("Go To Position"),
        #                    "coach": st.column_config.TextColumn("Coach", disabled=True),
        #                    "at_depot": st.column_config.TextColumn("At Depot", disabled=True),
        #                })

        # Add a rectangle to the map
        og_coordinates = [
            [37.41999522465071, -121.93949237138894],
            [37.41649876221854, -121.93810797555054],
            [37.41748834361772, -121.932785425544],
            [37.42105072840012, -121.93267467387127],
        ]

        folium.Polygon(og_coordinates, color='red', fill=True, fill_color='red', fill_opacity=0.2).add_to(m)

        # Display the Folium Map
        folium_static(m)
    except:
        st.write("Map Currently Unavailable")
