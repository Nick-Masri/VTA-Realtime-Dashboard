import pickle
import warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import t

from calls.visual_crossing import get_todays_weather

warnings.filterwarnings("ignore", category=UserWarning)

PKL_PATH = './ML_models/mapie_energy_consumption_model.sav'
ALPHA = 0.01
DEG_FREE = 8


@st.cache_resource
def load_model():
    with open(PKL_PATH, 'rb') as handle:
        return pickle.load(handle)


def _features(coach, miles, weather, today):
    """Feature order the model was trained on. Block id is not an input -
    a block only enters the model through its mileage."""
    return [
        weather['cloudcover'], coach, weather['humidity'], miles,
        weather['visibility'], weather['winddir'], weather['windspeed'],
        weather['feelslikemin'], weather['solarradiation'], weather['precipcover'],
        today.month, today.day,
    ]


def _spread(pred, low, high, percent):
    """Half-width implied by the conformal interval, on whichever side of the
    prediction the available charge falls."""
    if percent > pred:
        return (high - pred) / t.ppf(1 - ALPHA / 2, DEG_FREE)
    return (pred - low) / t.ppf(1 - ALPHA / 2, DEG_FREE)


def completion_probability(pred, low, high, percent):
    sd = _spread(pred, low, high, percent)
    if sd <= 0:
        return 1.0 if percent >= pred else 0.0
    return float(t.cdf((percent - pred) / sd, DEG_FREE))


def predict_batch(pairs):
    """Predict energy use for many (coach, miles) pairs in one model call.

    Returns a DataFrame of coach, miles, pred, low, high - all in percent of
    pack capacity.
    """
    pairs = tuple((float(coach), float(miles)) for coach, miles in pairs)
    if not pairs:
        return pd.DataFrame(columns=['coach', 'miles', 'pred', 'low', 'high'])
    return _predict_batch(pairs)


@st.cache_data(show_spinner=False, ttl=timedelta(minutes=30))
def _predict_batch(pairs):
    """Cached so a rerun triggered elsewhere in the app does not re-score the
    whole fleet grid - the energy tab alone asks for 300-odd predictions."""

    weather = get_todays_weather()
    today = date.today()
    rows = np.array(
        [_features(coach, miles, weather, today) for coach, miles in pairs]
    ).astype(np.float32)

    pred, interval = load_model().predict(rows, alpha=ALPHA)

    return pd.DataFrame({
        'coach': [c for c, _ in pairs],
        'miles': [m for _, m in pairs],
        'pred': pred,
        'low': interval[:, 0, 0],
        'high': interval[:, 1, 0],
    })


def predict_detail(coach, miles_travelled, percent):
    """Single prediction plus the interval, for charting."""
    if miles_travelled == '' or miles_travelled is None:
        return None

    row = predict_batch([(coach, miles_travelled)]).iloc[0]
    return {
        'pred': float(row['pred']),
        'low': float(row['low']),
        'high': float(row['high']),
        'sd': _spread(row['pred'], row['low'], row['high'], percent),
        'prob': completion_probability(row['pred'], row['low'], row['high'], percent),
    }


def predict_consumption(block, coach, miles_travelled, percent):
    detail = predict_detail(coach, miles_travelled, percent)
    if detail is None:
        return -1, 0
    return round(detail['pred'], 1), round(detail['prob'], 3)
