import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import os
from datetime import datetime
import pytz

def setup_client():
    # (if local) Load environment variables
    load_dotenv()
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    supabase: Client = create_client(url, key)
    return supabase

def supabase_block_history():
    supabase = setup_client()
    response = supabase.table('block_history').select("*").execute()
    data = response.data
    df = pd.DataFrame(data).drop(columns='id')

    if len(df) > 0:
        df = df.rename(columns={"start_time": "block_startTime", "end_time": "block_endTime",
                                "predicted_arrival": "predictedArrival", "route_id": "id"})
        df['coach'] = df['coach'].astype(str)
        df = df.sort_values('created_at', ascending=False).drop_duplicates(subset=['coach'], keep='first')
        return df
    else:
        return None

def supabase_soc():
    supabase = setup_client()
    yesterday = datetime.today() - pd.Timedelta(days=1)
    response = supabase.table('soc').select("*").gt("created_at", yesterday).execute()
    data = response.data
    df = pd.DataFrame(data)
    df['vehicle'] = df['vehicle'].astype(str)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.sort_values(by='created_at', ascending=False, inplace=True)
    # st.write(df)

    # Drop duplicate entries for each vehicle, keeping only the first (most recent)
    df.drop_duplicates(subset='vehicle', keep='first', inplace=True)
    df = df[['soc', 'vehicle', 'odometer', 'status', 'last_transmission']]
    # st.write(df)
    # Format the odometer column with thousands separator
    df['odometer'] = df['odometer'].apply(lambda x: "{:,}".format(x))

    # Convert last_transmission column to California timezone
    california_tz = pytz.timezone('America/Los_Angeles')
    df['last_transmission'] = pd.to_datetime(df['last_transmission']).dt.tz_convert(california_tz)
    return df.copy()

def supabase_soc_history():
    supabase = setup_client()
    yesterday = datetime.today() - pd.Timedelta(days=1)
    response = supabase.table('soc').select("*").order("created_at", desc=True).execute()
    data = response.data
    df = pd.DataFrame(data)
    df['vehicle'] = df['vehicle'].astype(str)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df.sort_values(by='created_at', ascending=False, inplace=True)

    # Convert last_transmission column to California timezone
    california_tz = pytz.timezone('America/Los_Angeles')
    df['last_transmission'] = pd.to_datetime(df['last_transmission']).dt.tz_convert(california_tz)
    return df.copy()