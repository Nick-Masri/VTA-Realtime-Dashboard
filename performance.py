import streamlit as st
from dotenv import load_dotenv
import os
from supabase import Client, create_client
import pandas as pd


def performance():
    load_dotenv()

    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)

    response = supabase.table('soc').select("*").execute()

    # Extract the data from the APIResponse object
    data = response.data

    # placeholder
    placeholder = pd.DataFrame()

    # Convert the data to a DataFrame
    df = pd.DataFrame(data)

    st.write(df)
