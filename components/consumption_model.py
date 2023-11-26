import pickle
import numpy as np
from datetime import date #TODO grab date
import warnings
from scipy.stats import t
from calls.visual_crossing import get_todays_weather


warnings.filterwarnings("ignore", category=UserWarning)

def predict_consumption(block, coach, miles_travelled, percent):
    weather_data = get_todays_weather()
    # today = date.today()
    if miles_travelled != '':
        inputs = np.array([[weather_data['cloudcover'], coach, weather_data['humidity'], miles_travelled, weather_data['visibility'], weather_data['winddir'], weather_data['windspeed'], weather_data['feelslikemin'], weather_data['solarradiation'], weather_data['precipcover'], 4, 11]])
    # inputs = np.array([[block, 67.5, coach, 43.2, miles_travelled, 14.5, 330.5, 8.9, 12.7, 34.1,0.0, 4, 11, 2023, 1]])
    #inputs = np.array([[7773, 28.9, 7505, 65.3, 84, 12.2, 322, 14.9, 24, 34.5, 0.0, 23, 8, 2019,1]])
        pkl_path = './ML_models/mapie_energy_consumption_model.sav'
    # return pkl_path
    # pkl_path = 'ML_models/energy_consumption_model.sav'
    # pkl_path = os.path.join(os.getcwd(), 'energy_consumption_model.sav')
        model = pickle.load(open(pkl_path, 'rb'))
        a = 0.01
        deg_free = 8
        pred, interval = model.predict(inputs, alpha = a)
        pred = pred[0]
        interval = interval[0,:,0]
        if(percent>pred):
            sd = (interval[1] - pred)/t.ppf(1-a/2, deg_free)
        else:
            sd = (pred - interval[0])/t.ppf(1-a/2, deg_free)
        prob = t.cdf((percent-pred)/sd, deg_free)
        return round(pred,1), round(prob,3)
    else:
        return -1, 0