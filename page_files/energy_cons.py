import streamlit as st
from components.consumption_model import predict_consumption
import warnings 

warnings.filterwarnings("ignore", category=UserWarning)

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
    energy_used = predict_consumption(block, v, miles)
    st.button('Generate estimated energy used')
    if energy_used is not None and energy_used != -1 and startSOC is not None:
        st.write('The amount of energy the bus uses in the route is ' + str(energy_used) + '%')
        batteryLeft =format(float(startSOC)-float(energy_used), ".2f")
        if float(batteryLeft) > 5:
            st.write('The amount of energy the bus will return with is ' + str(batteryLeft) + '%')
        else:
            st.write('The bus will not be able to complete the route.')
    else:
        st.warning('Please enter the number of miles.')
    #st.button('Generate estimated battery remaining')
   #  st.write('The bus will use ' + energy_used + 'percent battery')
    #st.write('The amount of energy the bus uses in the route is ' + str(energy_used) + '%')
    #st.success('Bus will be able to travel route without needing to recharge')

