#import pandas as pd
import streamlit as st
#import pickle
import os
import pickle
import requests #todo remove
import numpy as np
from datetime import date
import warnings 

#from components.consumption_model import predict_consumption
warnings.filterwarnings("ignore", category=UserWarning)

#for debugging
def get_todays_weather():
    url = 'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/santa%20clara/today?unitGroup=metric&include=days%2Ccurrent&key=3GYK8TN3A8NWKPGCYYW5S59CM&contentType=json'
    response = requests.get(url)

    if response.status_code == 200:
        response_json = response.json()

        desired_attribute = response_json['days'][0]
    else:
        raise Exception("Error retriving weather data")
    
    return desired_attribute


def predict_consumption(block, coach, miles_travelled):
    weather_data = get_todays_weather()
    # today = date.today()
    if miles_travelled != '':
        inputs = np.array([[block, weather_data['cloudcover'], coach, weather_data['humidity'], miles_travelled, weather_data['visibility'], weather_data['winddir'], weather_data['windspeed'], weather_data['feelslikemin'], weather_data['solarradiation'], weather_data['precipcover'], 4, 11, 2023, 1]])
    # inputs = np.array([[block, 67.5, coach, 43.2, miles_travelled, 14.5, 330.5, 8.9, 12.7, 34.1,0.0, 4, 11, 2023, 1]])
    #inputs = np.array([[7773, 28.9, 7505, 65.3, 84, 12.2, 322, 14.9, 24, 34.5, 0.0, 23, 8, 2019,1]])
        pkl_path = './ML_models/energy_consumption_model.sav'
    # return pkl_path
    # pkl_path = 'ML_models/energy_consumption_model.sav'
    # pkl_path = os.path.join(os.getcwd(), 'energy_consumption_model.sav')
        model = pickle.load(open(pkl_path, 'rb'))
        result = model.predict(inputs)[0]
        return round(result,1)
    else:
        return -1

def show_energy_cons():
    #st.write("Here we will load our model saved model")
    #st.write("Then we will add buttons for user input")
    
    voption = [2600, 7505, 7504, 7501, 2601, 2610, 2604, 2608, 2607, 2603, 2602,
       2606, 2605, 7503, 7502, 2609, 2612, 2611, 7506, 7507]

    v = st.selectbox('Select a vehicle', voption)
    startSOC = st.text_input('Input  the current bus SOC')
    block_option = [7770,7774,7773,7772,7771,7776,7775,7777,9883,9882,9983, 9982,9984,9986,9985,9987]
    block = st.selectbox('Select block', block_option)
    miles = st.text_input('Number of miles left to be travelled:')
    #st.text_input('Current temperature:')
    #st.text_input('Cloud cover:')
    #st.text_input('Current SOC:')
    energy_used=predict_consumption(block, v, miles)
    st.button('Generate estimated energy used')
    if energy_used is not None and energy_used != -1 and startSOC is not None:
        st.write('The amount of energy the bus uses in the route is ' + str(energy_used) + '%')
        batteryLeft =format(float(startSOC)-float(energy_used), ".2f")
        if batteryLeft > 5:
            st.write('The amount of energy the bus will return with is ' + str(batteryLeft) + '%')
        else:
            st.write('The bus will not be able to complete the route.')
    else:
        st.warning('Please enter the number of miles.')
    #st.button('Generate estimated battery remaining')
   #  st.write('The bus will use ' + energy_used + 'percent battery')
    #st.write('The amount of energy the bus uses in the route is ' + str(energy_used) + '%')
    #st.success('Bus will be able to travel route without needing to recharge')

