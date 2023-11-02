#import pandas as pd
import streamlit as st
#import pickle

def show_energy_cons():
    st.write("Here we will load our model saved model")
    st.write("Then we will add buttons for user input")

    vehicle_options = [f'750{x}' for x in range(1, 6)] + [f'950{x}' for x in range(1, 6)]

    vehicle = st.selectbox('Select a vehicle', vehicle_options)

    #block_option = [7770,7774,7773,7772,7771,7776,7775,7777,9883,9882,9983, 9982,9984,9986,9985,9987,7777071,7777072]
    #block = st.selectbox('Select block', block_option)
    st.text_input('Number of miles left to be travelled:')
    st.text_input('Current temperature:')
    st.text_input('Cloud cover:')
    st.text_input('Current SOC:')

    st.button('Generate estimated battery remaining')

    st.success('Bus will be able to travel route without needing to recharge')

    


