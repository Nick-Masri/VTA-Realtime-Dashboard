import requests
import streamlit as st
import datetime

from calls import demo_state

# Santa Clara monthly normals, metric, used when the weather API is unreachable.
# Keyed by month -> the fields the consumption model consumes.
_CLIMATOLOGY = {
    1:  (52, 74, 14.0, 140, 10.5,  4.5,  95, 12.0),
    2:  (50, 71, 15.0, 150, 11.5,  6.0, 135,  9.0),
    3:  (46, 68, 16.0, 300, 12.5,  7.5, 190,  8.0),
    4:  (38, 63, 16.5, 310, 13.5,  9.0, 245,  4.5),
    5:  (28, 60, 17.0, 320, 14.0, 11.0, 290,  2.0),
    6:  (16, 57, 17.5, 320, 14.5, 13.5, 315,  0.5),
    7:  (10, 58, 17.5, 320, 14.0, 15.0, 310,  0.2),
    8:  (11, 60, 17.0, 320, 13.5, 15.0, 285,  0.2),
    9:  (13, 61, 16.5, 315, 12.0, 13.5, 240,  0.6),
    10: (22, 64, 16.0, 300, 11.0, 10.5, 180,  2.5),
    11: (38, 70, 15.0, 180, 10.5,  7.0, 115,  7.0),
    12: (52, 75, 13.5, 140, 10.5,  4.5,  90, 11.5),
}

_FIELDS = ('cloudcover', 'humidity', 'visibility', 'winddir',
           'windspeed', 'feelslikemin', 'solarradiation', 'precipcover')


# Set when a lookup falls back, so the page can mention it once rather than
# having the cached function replay a caption at every call site.
_ESTIMATED = {'value': False}


def weather_is_estimated():
    return _ESTIMATED['value']


def _seasonal_normals():
    _ESTIMATED['value'] = True
    demo_state.mark('weather')
    return dict(zip(_FIELDS, _CLIMATOLOGY[datetime.date.today().month]))


@st.cache_data(show_spinner=False, ttl=datetime.timedelta(minutes=30))
def get_todays_weather():
    url = (
        'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services'
        '/timeline/santa%20clara/today'
    )
    try:
        key = st.secrets['VISUAL_CROSSING_KEY']
    except Exception:
        return _seasonal_normals()

    params = {
        'unitGroup': 'metric',
        'include': 'days,current',
        'contentType': 'json',
        'key': key,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()['days'][0]
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        # Never interpolate the exception: requests puts the full request URL,
        # api key and all, into its message.
        del exc
        return _seasonal_normals()
