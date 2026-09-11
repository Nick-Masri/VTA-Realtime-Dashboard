import requests
import streamlit as st
import datetime

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(minutes=30))
def get_todays_weather():
    url = (
        'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services'
        '/timeline/santa%20clara/today'
    )
    params = {
        'unitGroup': 'metric',
        'include': 'days,current',
        'contentType': 'json',
        'key': st.secrets['VISUAL_CROSSING_KEY'],
    }

    response = requests.get(url, params=params, timeout=15)
    if response.status_code != 200:
        raise Exception("Error retriving weather data")

    return response.json()['days'][0]