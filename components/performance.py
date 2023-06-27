import streamlit as st
from dotenv import load_dotenv
import os
from supabase import Client, create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime


def performance():
    load_dotenv()

    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    response = supabase.table('soc').select("*").execute()
    data = response.data

    df = pd.DataFrame(data)
    df = df.sort_values('vehicle')
    df['soc'] = df['soc'].astype(int)
    old_buses = [f'750{x}' for x in range(1, 6)]
    new_buses = [f'950{x}' for x in range(1, 6)]
    ebuses = old_buses + new_buses + ["All"]

    # Get unique vehicles

    data = {"coaches": "All", "start_date": df.created_at.min(), "end_date": df.created_at.max()}
    vehicles = pd.DataFrame(data, index=[0])
    vehicles.start_date = pd.to_datetime(vehicles.start_date)
    vehicles.end_date = pd.to_datetime(vehicles.end_date)
    st.write("### Options")
    st.data_editor(vehicles, hide_index=True,
                   column_config={
                       "coaches": st.column_config.SelectboxColumn(
                           "Coaches",
                           options=ebuses
                       ),
                       "start_date": st.column_config.DatetimeColumn(
                           "Start Date",
                           format="hh:mmA MM/DD/YY"
                       ),
                       "end_date": st.column_config.DatetimeColumn(
                           "End Date",
                           format="hh:mmA MM/DD/YY"
                       )
                   })
    unique_vehicles = df.vehicle.unique()

    # st.selectbox(label="Coaches", options=ebuses)
    # today = datetime.date.today()
    # tomorrow = today + datetime.timedelta(days=1)
    # start_date = st.date_input('Start date', today)
    # end_date = st.date_input('End date', tomorrow)
    # if start_date < end_date:
    #     st.success('Start date: `%s`\n\nEnd date:`%s`' % (start_date, end_date))
    # else:
    #     st.error('Error: End date must fall after start date.')

    # Iterate through each vehicle and create an area graph
    for vehicle in unique_vehicles:
        col1, col2 = st.columns(2)
        # fig = go.Figure()
        filtered_df = df[df.vehicle == vehicle]
        filtered_df = filtered_df.sort_values('created_at')
        # Calculate the energy lost and gained
        filtered_df['energy_change'] = filtered_df['soc'].diff()

        energy_loss = filtered_df[filtered_df['energy_change'] < 0]['energy_change'].sum()
        energy_gain = filtered_df[filtered_df['energy_change'] > 0]['energy_change'].sum()

        fig = px.area(filtered_df,
                      x=filtered_df['created_at'],
                      y=filtered_df['soc'])

        # Set the layout for the chart
        fig.update_layout(
            title=f'State of Charge for Coach {vehicle}',
            xaxis_title="Date Recorded",
            yaxis_title="State of Charge Percentage (%)",
            yaxis_range=[-5, 105]
        )

        # Render the scatter plot in Streamlit
        with col1:
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.write("#### Gain and Loss for Time Period")
            # st.write(filtered_df)
            st.write(f'Gain: {round(energy_gain)}%')
            st.write(f'Loss: {round(energy_loss)}%')
