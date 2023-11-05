# from calls.visual_crossing import get_todays_weather
import pickle
import requests #todo remove
import numpy as np
from datetime import date
import warnings

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
    inputs = np.array([[block, weather_data['cloudcover'], coach, weather_data['humidity'], miles_travelled, weather_data['visibility'], weather_data['winddir'], weather_data['windspeed'], weather_data['feelslikemin'], weather_data['solarradiation'], weather_data['precipcover'], 4, 11, 2023, 1]])
    model = pickle.load(open('./ML_models/energy_consumption_model.sav', 'rb'))
    result = model.predict(inputs)[0]
    return round(result,1)

print(predict_consumption(7773, 7505, 100))