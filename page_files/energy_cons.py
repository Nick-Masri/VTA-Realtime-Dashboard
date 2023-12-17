import streamlit as st
import pandas as pd 
from components.consumption_model import predict_consumption
import warnings 
from page_files.dashboard import get_overview_df

warnings.filterwarnings("ignore", category=UserWarning)

def show_energy_cons():
    voption = [7501, 7502,7503, 7504,7505, 9501, 9502,9503,9504,9505]
    
    v = st.selectbox('Select a vehicle', voption, key='v')

    df = pd.read_csv('data_files/block_miles.csv', header=1, delimiter=';')
    df = df[['BLOCK', 'TOTAL MILES']]
    df = df[df['TOTAL MILES'] > 0]

    get_live_soc = st.toggle('Use realtime SOC', value=True) 
    approved_blocks = st.toggle('Use approved blocks', value=True)

    if approved_blocks:
        # from block 476 to 6081 
        df = df.loc[50:79]

    block_option = df['BLOCK'].unique()
    block_to_miles_dictionary = df.set_index('BLOCK').to_dict()['TOTAL MILES']

    block = int(st.selectbox('Select block', block_option, key='block'))


    if get_live_soc:
        serving, charging, idle, offline, df = get_overview_df()
        df = df[['vehicle', 'soc']]
        # convert to dictionary
        # st.write(df.vehicle.dtype)
        df['vehicle'] = df['vehicle'].astype(int)
        df = df.set_index('vehicle')
        vehicle_soc = df.to_dict()
        startSOC = vehicle_soc['soc'][v]
    else:
        startSOC = st.text_input('Input  the current bus SOC') #TODO make str to float conversion more robust
        startSOC = int(startSOC) if startSOC != '' else ''



    miles = block_to_miles_dictionary[block]
    energy_used, probability = predict_consumption(block, v, miles, 0 if startSOC=='' else float(startSOC))
    # st.button('Generate estimated energy used')
    if energy_used is not None and energy_used != -1 and startSOC is not None and startSOC != '':
        # st.write('The amount of energy the bus uses in the route is ' + str(energy_used) + '%')
        energy_used = int(energy_used)
        batteryLeft = int(startSOC - energy_used)
        startSOC = int(startSOC)
        cols = st.columns(5)

        cols[0].metric(label='Current SOC', value=str(startSOC) + '%')
        cols[1].metric(label='Block Mileage', value=str(miles))
        cols[2].metric(label='Energy used', value=str(energy_used) + '%')
        # st.metric(label='Energy used', value=str(energy_used) + '%')
        # st.metric(label='Battery left', value=str(batteryLeft) + '%')
        cols[3].metric(label='Battery left', value=str(batteryLeft) + '%')
        probability = int(probability*100)
        cols[4].metric(label='Completion Prob.', value=str(probability) + '%')
        # st.metric(label='Probability of completion', value=str(100*probability) + '%')
        # st.write('The probability the bus completes the route is ' + str(100*probability) + '%')
    elif energy_used == -1 or energy_used is None:
        st.warning('Please enter the number of miles.')
    elif startSOC == '' or startSOC is None:
        st.warning('Please enter the current SOC.')

