import requests
from googleapiclient.http import MediaIoBaseDownload

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import pickle
from pgbm import PGBM
import altair as alt
from scipy.stats import norm
import os
import io

# get the file from the google drive
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set the file ID of the file you want to download
file_id = 'YOUR_FILE_ID'
def upload_basic():
    """Insert new file.
    Returns : Id's of the file uploaded

    Load pre-authorized user credentials from the environment.
    # TODO(developer) - See https://developers.google.com/identity
    for guides on implementing OAuth2 for the application.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    SCOPES = ['https://www.googleapis.com/auth/drive']

    if os.path.exists('../token.json'):
        creds = Credentials.from_authorized_user_file('../token.json', SCOPES)
    try:
        # create drive api client
        service = build('drive', 'v3', credentials=creds)

        file_id = '1PZvEfJ0CDBDxuSQZOocr9a7ONPAwxqom'

        # pylint: disable=maybe-no-member
        request = service.files().get_media(fileId=file_id)
        # file = io.BytesIO()
        file = io.FileIO('df.pkl', mode='wb')
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(F'Download {int(status.progress() * 100)}.')

    except HttpError as error:
        print(F'An error occurred: {error}')
        file = None



    return file



# Upload file
file = upload_basic()
# print(file)


# setup the data
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
st.title("E-BUS Data Portal")
mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}

df = pd.read_pickle('df.pkl')

# Using "with" notation
with st.sidebar:
    fleet = st.sidebar.selectbox(
        "Fleet",
        ("both", "7500s", "9500s")
    )

    vehicles = st.multiselect(
        'Vehicle',
        ['Green', 'Yellow', 'Red', 'Blue'])

coaches = df.vehicle.value_counts()

ebec_input = pd.DataFrame(columns=['Date', 'Vehicle', 'start_per'])

for coach in coaches.index:
    # grab most recent data
    coach_df = df[df.vehicle == coach]
    row = coach_df[coach_df.Date == coach_df.Date.max()].iloc[0, :]
    # print(row['Date'])
    #
    ebec_input = ebec_input.append({'Date': row['Date'], 'Vehicle': row['vehicle'], 'start_per': row['soc']},
                                   ignore_index=True)

ebec_input['month'] = ebec_input['Date'].dt.month

# setup tabs for output
tab1, tab2 = st.tabs(['Today', 'Historical'])
with tab1:
    # write output to dashboard
    output = ebec_input
    output.start_per = output.start_per.astype('float64')
    output.start_per = round(output.start_per, 1)
    output.Date = output.Date.dt.strftime("%m/%d %I:%M%P")
    output = output.rename(columns={'start_per': "SOC %", "Date": "Last Online"})

    cols = st.columns(2)
    with cols[0]:
        # st.bar_chart(data=output, y="Vehicle:N", x='SOC %:Q')

        bar = alt.Chart(output).mark_bar(color='green').encode(
            x='SOC %:Q',
            y=alt.Y('Vehicle:N')
        ).properties(
            height=alt.Step(40)  # controls width of bar.
        )

        st.altair_chart(bar, use_container_width=True)
    output.index = output.Vehicle
    with cols[1]:
        st.dataframe(output[['SOC %', "Last Online"]])

    #
    ebec_final = ebec_input[['start_per', 'month']]
    ebec_final['start_per'] = ebec_final['start_per'].astype(float)

    model_new = PGBM()
    model_new.load('model1.pt')

    # Point and probabilistic predictions
    yhat_point = model_new.predict(ebec_final.values)
    yhat_dist = model_new.predict_dist(ebec_final.values, output_sample_statistics=True)

    means = yhat_dist[1]
    variance = yhat_dist[2]

    mean = means.mean()
    var = variance.mean()

    predictions = []
    for coaches in range(ebec_final.shape[0]):
        min = yhat_dist[0][:, coaches].min().item()
        max = yhat_dist[0][:, coaches].max().item()
        predictions.append((min, max))

    coaches = list(ebec_input.Vehicle.values)

    preds_df = pd.DataFrame(columns=['coach', 'block', 'pred_eff', 'pred_miles', 'type'])

    for idx, coach in enumerate(coaches):
        pred = predictions[idx]

        low = pred[0]
        mid = yhat_point[idx].item()
        high = pred[1]
        preds = [low, mid, high]

        for block in mileages.keys():
            miles = mileages[block]
            for idx, pred in enumerate(preds):
                if idx == 0:
                    type = 'low'
                elif idx == 1:
                    type = 'mid'
                else:
                    type = 'high'

                preds_df = preds_df.append(
                    {'coach': coach, 'block': block, 'pred_eff': pred, 'pred_miles': pred * miles, 'type': type},
                    ignore_index=True)

    fig, ax = plt.subplots(1, len(coaches), figsize=(10, 40))
    N_series = 3
    coaches = sorted(coaches)

    st.header("Energy Consumption Predictions")

    n_coaches = ebec_final.shape[0]

    preds_df.type = pd.Categorical(preds_df.type,
                                   categories=["high", "mid", "low"],
                                   ordered=True)
    nrows = int(n_coaches / 2)
    preds_df = preds_df.sort_values('type')

    for j in range(nrows):
        cols = st.columns(2)
        for idx, col in enumerate(cols):
            with col:
                coach = coaches[idx + j * 2]
                data = preds_df[preds_df["coach"] == coach]
                st.header("Coach: {}".format(coach))

                colors = list(sns.color_palette())

                chart = alt.Chart(data).mark_bar(opacity=0.6).encode(
                    x='block',
                    y=alt.Y('pred_miles', stack=None, sort='ascending'),
                    color=alt.Color('type', scale=alt.Scale(
                        domain=['high', 'low', 'mid'],
                        range=["#4878D0", "#EE854A", "#6ACC64"]))
                )

                current_soc = float(ebec_input[ebec_input['Vehicle'] == coach]['start_per'].values[0]/100)
                val = 440*(current_soc - 0.2)
                line = alt.Chart(pd.DataFrame({'y': [val]})).mark_rule(strokeDash=[5, 1], color="red").encode(y='y')
                st.altair_chart(chart + line, use_container_width=True)
                # st.write(norm.ppf())
                # st.write()

                mids = preds_df.query("type == 'mid' and coach == @coach")
                # st.dataframe(mids)


                for val in mids:
                    st.write(val)
                    st.write(mean)
                    st.write(var)
                    miles = mileages[block]
                    x = val/miles
                    st.write(x)
                    prob = norm.ppf(x, mean, var)
                    st.write(prob)
                # break

                # st.write(variance.mean())
                # TODO: add in SOC to the graphs/calculations
                # TODO: Get Probs
                # TODO: rewrite table
                # TODO: add in optimization predictions
