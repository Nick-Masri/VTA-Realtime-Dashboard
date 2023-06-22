import streamlit as st
from dotenv import load_dotenv
import os
from supabase import Client, create_client
import pandas as pd
import plotly.express as px


def performance():
    load_dotenv()

    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    response = supabase.table('soc').select("*").execute()

    # Extract the data from the APIResponse object
    data = response.data

    # Convert the data to a DataFrame
    df = pd.DataFrame(data)

    # Sort by vehicle
    df = df.sort_values('vehicle')

    # Get unique vehicles
    unique_vehicles = df.vehicle.unique()

    # Iterate through each vehicle and create a scatter plot
    for vehicle in unique_vehicles:
        filtered_df = df[df.vehicle == vehicle]

        # Create the scatter plot using Plotly
        fig = px.scatter(filtered_df, x='created_at', y='soc')

        # Set the layout for the chart
        fig.update_layout(
            title=f"Coach {vehicle} - State of Charge",
            xaxis_title="Date Recorded",
            yaxis_title="State of Charge Percentage (%)",
            yaxis_range=[-5, 105]
        )

        # Render the scatter plot in Streamlit
        st.plotly_chart(fig)
