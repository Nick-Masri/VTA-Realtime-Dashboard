import pandas as pd
import streamlit as st
import requests


def show_apis():
    st.write("# Swiftly")
    st.write("## Vehicles API Fetch")
    # Define API endpoint and headers
    url = "https://api.goswift.ly/real-time/vta/vehicles"
    headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}

    # Send GET request to API endpoint and retrieve JSON response
    response = requests.get(url, headers=headers)
    json_data = response.json()

    # Extract vehicles data from JSON response
    vehicles_data = json_data["data"]["vehicles"]

    # Create pandas DataFrame from vehicles data
    df = pd.DataFrame(vehicles_data)

    # Convert 'id' column to string (if it's not already)
    df['id'] = df['id'].astype(str)

    # Filter DataFrame by list of ids (as strings)
    ids_to_filter = ['7501', '7502', '7503', '7504', '7505', '9501', '9502', '9503', '9504', '9505']
    filtered_df = df[df['id'].isin(ids_to_filter)]

    st.write("See if ebuses show up in vehicles fetch")
    filtered_df = filtered_df[['id', 'routeId']]

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

    st.write("## Blocks Api")
    st.write("Used on dashboard for buses on routes")
    st.markdown("""<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True)

    st.write("# GTFS")

    st.write("## Realtime Vehicle Positions")
    st.write("Used on location for map")
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
