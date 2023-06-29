import folium
import pandas as pd
import pytz
import streamlit as st
from shapely.geometry import Point, Polygon
from streamlit_folium import folium_static
from components.active_blocks import get_active_blocks

from calls.supa_select import supabase_active_location


def move_to_vehicle_location(pos, m):
    # Update the map's center to the vehicle's position
    m.location = pos
    # Re-render the map
    folium_static(m)


def vehicle_map():
    df = supabase_active_location()

    if df is None:
        st.write("Map Currently Unavailable")
    else:
        st.subheader("Vehicle Map")

        old_buses = [f'750{x}' for x in range(1, 6)]
        new_buses = [f'950{x}' for x in range(1, 6)]
        ebuses = old_buses + new_buses

        # Create a Folium Map object centered around the Cerone Bus Yard
        depot_center = [37.41845007126032, -121.93728511980153]
        m = folium.Map(depot_center, zoom_start=14)

        # Define the polygon coordinates of the depot
        depot_coordinates = [
            [37.41999522465071, -121.93949237138894],
            [37.41649876221854, -121.93810797555054],
            [37.41748834361772, -121.932785425544],
            [37.42105072840012, -121.93267467387127],
        ]
        folium.Polygon(depot_coordinates, color='red', fill=True, fill_color='red', fill_opacity=0.2).add_to(m)

        # Create a Shapely Polygon object from the depot coordinates
        depot_polygon = Polygon(depot_coordinates)

        # Tolerance for the depot polygon
        tolerance = 0.0005

        # convert date to california time and format
        california_tz = pytz.timezone('US/Pacific')
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['created_at'] = df['created_at'].dt.tz_convert(california_tz)
        df['created_at'] = df['created_at'].dt.strftime('%m/%d/%y %I:%M %p')

        # round lat and long to 6 decimal places
        df['lat'] = df['lat'].round(6)
        df['long'] = df['long'].round(6)

        # add markers to map
        for index, row in df.iterrows():
            popup_text = f"Coach: {row['coach']}" \
                         f"<br>Latitude: {row['lat']}" \
                         f"<br>Longitude: {row['long']}" \
                         f"<br>Speed: {row['speed']} " \
                         f"<br>Last Transmission: {row['created_at']}"
            folium.Marker(location=[row['lat'], row['long']], popup=popup_text).add_to(m)

        # df = df.drop(columns=['created_at'])
        df['at_depot'] = df.apply(
            lambda row: depot_polygon.buffer(tolerance).contains(Point(row['long'], row['lat'])), axis=1)
        df['at_depot'] = df['at_depot'].replace({True: 'Yes', False: 'No'})


        merged_df = get_active_blocks()
        df['location'] = df.apply(
            lambda row: 'Depot' if row['at_depot'] == 'Yes'
    else "Block " + str(merged_df[merged_df['coach'] == row['coach']].iloc[0, 1]) if row['coach'] in merged_df['coach'].values
            else 'Unknown', axis=1)
        df = df.sort_values(by=['coach'])

        st.dataframe(df, hide_index=True,
                     column_order=["coach",  "location", "lat", "long", "speed", "created_at"],
                     column_config={
                         "coach": st.column_config.TextColumn("Coach"),
                         "location": st.column_config.TextColumn("Location"),
                         "lat": st.column_config.TextColumn("Latitude"),
                         "long": st.column_config.TextColumn("Longitude"),
                         "speed": st.column_config.TextColumn("Speed"),
                         "created_at": st.column_config.DatetimeColumn("Last Transmission",
                                                                       format="MM/DD/YY hh:mm A"),
                     })

        # Display the Folium Map
        # selectbox for location
        options = df.coach.unique().tolist() + ["Depot"]
        location = st.selectbox("Select Location", options, index=len(options) - 1)
        if location != "Depot":
            selected_vehicle = df[df['coach'] == location].iloc[0, :]
            move_to_vehicle_location([selected_vehicle.lat, selected_vehicle.long], m)
        else:
            move_to_vehicle_location(depot_center, m)
