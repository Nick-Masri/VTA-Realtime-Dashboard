import pandas as pd
import streamlit as st
import math
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pickle

def show_energy_cons():
    st.write("Here we will load our model saved model")
    st.write("Then we will add buttons for user input")

    st.text_input('Number of miles left to be travelled:')
    st.text_input('Current temperature:')
    st.text_input('Cloud cover:')
    st.text_input('Current SOC:')

    st.button('Generate estimated battery remaining')

    st.success('Bus will be able to travel route without needing to recharge')
