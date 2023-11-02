import requests
import streamlit as st
import datetime

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(minutes=30))
def get_todays_weather():
    url = 'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/santa%20clara/today?unitGroup=metric&include=days%2Ccurrent&key=3GYK8TN3A8NWKPGCYYW5S59CM&contentType=json'
    response = requests.get(url)

    if response.status_code == 200:
        response_json = response.json()

        desired_attribute = response_json['days'][0]
    else:
        raise Exception("Error retriving weather data")
    
    return desired_attribute