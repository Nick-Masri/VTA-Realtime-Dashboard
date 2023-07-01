import streamlit as st
from components.vehicle_history import show_vehicle_history
from components.charger_history import show_charger_history
def show_history():
    # Route History
    st.write("## History")
    # select vehicle or charger history
    selection = st.selectbox("Select History", ["Vehicles", "Chargers"])
    if selection == "Chargers":
        show_charger_history()
    elif selection == "Vehicles":
        show_vehicle_history()