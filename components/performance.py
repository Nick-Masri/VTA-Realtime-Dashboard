import streamlit as st
from dotenv import load_dotenv
import os
from supabase import Client, create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from calls.supa_select import supabase_soc_history
from calls.supa_select import supabase_blocks
import pytz


def performance():
    df = supabase_soc_history()
    df = df.sort_values('vehicle')

    california_tz = pytz.timezone('US/Pacific')
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(california_tz)

    # Route History
    st.subheader("Bus Block History")

    # Get the active blocks from supabase
    blocks = supabase_blocks(active=False)
    blocks['created_at'] = pd.to_datetime(blocks['created_at'])
    blocks['date'] = blocks['created_at'].dt.strftime('%Y-%m-%d')
    blocks = blocks.sort_values('created_at')
    blocks = blocks.drop_duplicates(subset=['coach', 'date'], keep='first')
    blocks = blocks.drop(columns=['created_at'])
    # st.dataframe(blocks, hide_index=True,
    #              column_order=["date", "coach", "id", "block_id", "block_startTime", "block_endTime",
    #                            "predictedArrival"],
    #              column_config={
    #                  "coach": st.column_config.TextColumn("Coach"),
    #                  "id": st.column_config.TextColumn("Route"),
    #                  "block_id": st.column_config.TextColumn("Block"),
    #                  "block_startTime": st.column_config.TimeColumn("Start Time", format="hh:mmA"),
    #                  "block_endTime": st.column_config.TimeColumn("End Time", format="hh:mmA"),
    #                  "predictedArrival": st.column_config.TimeColumn("Predicted Arrival Time",
    #                                                                  format="hh:mmA"),
    #                  "date": st.column_config.DateColumn("Date", format="MM/DD/YY")
    #              })

    # Bus Block History with SOC and Odometer Changes
    # st.subheader("Bus Block History with SOC and Odometer Changes")

    results = []

    for idx, row in blocks.iterrows():
        relevant_df = df[df['vehicle'] == row['coach']]
        relevant_df['created_at'] = pd.to_datetime(relevant_df['created_at'])

        block_start_time = pd.to_datetime(row['date'] + ' ' + row['block_startTime'])
        block_end_time = pd.to_datetime(row['date'] + ' ' + row['block_endTime'])

        # Localize block start and end times to the desired timezone
        timezone = pytz.timezone('US/Pacific')
        block_start_time = timezone.localize(block_start_time)
        block_end_time = timezone.localize(block_end_time)

        relevant_starts = relevant_df[
            (relevant_df['created_at'] <= block_start_time + timedelta(hours=1)) &
            (relevant_df['created_at'] >= block_start_time - timedelta(days=1))
            ]
        relevant_starts = relevant_starts.sort_values('created_at', ascending=False)

        # Check if block start time - 1 hour is in the future and there are entries in relevant starts
        if block_start_time - timedelta(hours=1) > datetime.now(timezone) or relevant_starts.empty:
            # Omit writing SOC and odometer changes
            start_soc = None
            start_odometer = None
        else:
            start_soc = relevant_starts.iloc[0]['soc']
            start_odometer = relevant_starts.iloc[0]['odometer']

        relevant_ends = relevant_df[
            (relevant_df['created_at'] >= block_end_time - timedelta(hours=2)) &
            (relevant_df['created_at'] <= block_end_time + timedelta(days=1))
            ]
        relevant_ends = relevant_ends.sort_values('created_at', ascending=True)

        # Check if block end time + 1 hour is in the future
        if block_end_time + timedelta(hours=1) > datetime.now(timezone):
            # Omit writing SOC and odometer changes
            end_soc = None
            end_odometer = None
        else:
            end_soc = min(relevant_ends.iloc[0]['soc'], relevant_ends.iloc[1]['soc'])
            end_odometer = relevant_ends.iloc[1]['odometer']

        soc_change = None if start_soc is None or end_soc is None else end_soc - start_soc
        odometer_change = None if start_odometer is None or end_odometer is None else end_odometer - start_odometer

        result = {
            'Vehicle': row['coach'],
            'Date': row['date'],
            'Start SOC': start_soc,
            'End SOC': end_soc,
            'SOC Change': soc_change,
            'Start Odometer': start_odometer,
            'End Odometer': end_odometer,
            'Odometer Change': odometer_change
        }
        results.append(result)

    result_df = pd.DataFrame(results)
    # st.dataframe(result_df)

    # merge blocks and result_df
    blocks = blocks.merge(result_df, left_on=['coach', 'date'], right_on=['Vehicle', 'Date'], how='left')
    blocks = blocks.drop(columns=['Vehicle', 'Start Odometer', 'End Odometer'])
    blocks = blocks.rename(columns={'Start SOC': 'Start SOC (%)', 'End SOC': 'End SOC (%)',
                                    'SOC Change': 'SOC Change (%)', 'Odometer Change': 'Miles Travelled'})
    st.dataframe(blocks, hide_index=True,
                    column_order=["date", "coach", "id", "block_id", "block_startTime", "block_endTime",
                                    "predictedArrival", "Start SOC (%)", "End SOC (%)", "SOC Change (%)",
                                    "Miles Travelled"],
                 column_config={
                     "coach": st.column_config.TextColumn("Coach"),
                     "id": st.column_config.TextColumn("Route"),
                     "block_id": st.column_config.TextColumn("Block"),
                     "block_startTime": st.column_config.TimeColumn("Start Time", format="hh:mmA"),
                     "block_endTime": st.column_config.TimeColumn("End Time", format="hh:mmA"),
                     "predictedArrival": st.column_config.TimeColumn("Predicted Arrival Time",
                                                                     format="hh:mmA"),
                     "date": st.column_config.DateColumn("Date", format="MM/DD/YY")
                 })

    # Get unique vehicles
    data = {"coaches": "All", "start_date": df.created_at.min(), "end_date": df.created_at.max()}
    vehicles = pd.DataFrame(data, index=[0])
    vehicles.start_date = pd.to_datetime(vehicles.start_date)
    vehicles.end_date = pd.to_datetime(vehicles.end_date)
    unique_vehicles = df.vehicle.unique()




    # old_buses = [f'750{x}' for x in range(1, 6)]
    # new_buses = [f'950{x}' for x in range(1, 6)]
    # ebuses = old_buses + new_buses + ["All"]
    # st.write("### Options")
    # st.data_editor(vehicles, hide_index=True,
    #                column_config={
    #                    "coaches": st.column_config.SelectboxColumn(
    #                        "Coaches",
    #                        options=ebuses
    #                    ),
    #                    "start_date": st.column_config.DatetimeColumn(
    #                        "Start Date",
    #                        format="hh:mmA MM/DD/YY"
    #                    ),
    #                    "end_date": st.column_config.DatetimeColumn(
    #                        "End Date",
    #                        format="hh:mmA MM/DD/YY"
    #                    )
    #                })

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
            st.write("#### Gain and Loss")
            # st.write(filtered_df)
            st.write(f'Gain: {round(energy_gain)}%')
            st.write(f'Loss: {round(energy_loss)}%')
