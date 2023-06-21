import streamlit as st
import os
import io
from gurobipy import Model, quicksum
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from gurobipy import GRB
import numpy as np
import pandas as pd


def solve(probabilities, ebec_input, prob_data, threshold=0.95):
    mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}
    coach_names = sorted(list(ebec_input['Vehicle'].unique()))
    coaches = {idx: route for idx, route in enumerate(coach_names)}
    bus_iter = range(len(coaches.keys()))

    block_names = sorted(mileages.keys())
    blocks = {idx: block for idx, block in enumerate(block_names)}
    block_iter = range(len(blocks.keys()))

    model = Model('EDis')

    p_j = np.reshape(probabilities.sort_index().to_records(), (len(bus_iter), len(block_iter)))
    vars = model.addVars(bus_iter, block_iter, vtype=GRB.BINARY, name='X')
    model.addConstrs(vars.sum('*', j) <= 1 for j in block_iter)  # each block can only be assigned to one coach
    model.addConstrs(vars.sum(i, '*') <= 1 for i in bus_iter)  # each coach can only be assigned to one block
    model.addConstrs(vars[i, j] * threshold <= p_j[i, j][-1] for i in bus_iter for j in block_iter)  # probability constraint
    model.modelSense = GRB.MAXIMIZE

    z = (quicksum(p_j[i, j][-1] * vars[i, j] for i in bus_iter for j in block_iter))
    model.setObjective(z)
    model.optimize()
    model.getObjective().getValue()

    solution_vars = []
    for v in model.getVars():
        solution_vars.append(v.x)
    solution_vars = np.reshape(np.abs(solution_vars), (len(bus_iter), len(block_iter)))

    solution_vars = pd.DataFrame(solution_vars, index=coach_names, columns=block_names)
    solution_vars = solution_vars.melt(ignore_index=False, var_name='Block')
    solution_vars = solution_vars[solution_vars['value'] == 1]

    return solution_vars



def download():
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/drive']

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    try:
        # create drive api client
        service = build('drive', 'v3', credentials=creds)

        file_id = '1PZvEfJ0CDBDxuSQZOocr9a7ONPAwxqom'

        request = service.files().get_media(fileId=file_id)
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


def sidebar():
    with st.sidebar:
        fleet = st.sidebar.selectbox(
            "Fleet",
            ("both", "7500s", "9500s")
        )

        vehicles = st.multiselect(
            'Vehicle',
            ['Green', 'Yellow', 'Red', 'Blue'])


def tab2():

    with tab2:
        st.markdown("## Solar LSTM/prophet")
        st.markdown("## Form for user input")
        st.markdown("## Charging Schedule for week")
        st.write("Optimal Cost: {}".format(10))
        st.markdown("")
