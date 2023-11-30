import streamlit as st
from components.consumption_model import predict_consumption
import warnings 

warnings.filterwarnings("ignore", category=UserWarning)

def show_energy_cons():
    voption = [7501, 7502,7503, 7504,7505, 7506, 7507, 9501, 9502,9503,9504,9505]
    
    # block_to_miles_dictionary = {"7770":,"7774","7773","7772","7771","7776","7775","7777","9883","9882","9983", "9982","9984","9986","9985","9987"}

    v = st.selectbox('Select a vehicle', voption)
    startSOC = st.text_input('Input  the current bus SOC') #TODO make str to float conversion more robust
    block_option = ["7771","7772","7773","7774","7775","7776","7777","9882","9883", "9982","9983","9984","9985","9986","9987"]
    block = int(st.selectbox('Select block', block_option))
    miles = st.text_input('Number of miles left to be travelled:')
    energy_used, probability = predict_consumption(block, v, miles, 0 if startSOC=='' else float(startSOC))
    st.button('Generate estimated energy used')
    if energy_used is not None and energy_used != -1 and startSOC is not None:
        st.write('The amount of energy the bus uses in the route is ' + str(energy_used) + '%')
        batteryLeft =format(float(startSOC)-float(energy_used), ".2f")
        st.write('The probability the bus completes the route is ' + str(100*probability) + '%')
    else:
        st.warning('Please enter the number of miles.')

