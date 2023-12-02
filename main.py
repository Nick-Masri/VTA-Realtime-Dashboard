import streamlit as st
st.set_page_config(page_title="VTA E-Bus Portal", page_icon="🚌")
from page_files.dashboard import dashboard
from page_files.history import show_history
from page_files.vehicles import show_vehicles



##########################################################
# Setup
##########################################################

def main():

    st.title("VTA Electric Bus Data Portal")
    dash, veh, hist = st.tabs(["📊 Dashboard", "🚍 Vehicles", "🕓 History"])

    with dash:
        dashboard()

    with veh:
        show_vehicles()

    with hist:
        show_history()

    # with pred:
    #     energy_predictions()

    # with opt:
    #     opt_form()

    #with charge:
        #show_form()
    
    # with enrg:
    #     show_energy_cons()
    
    #with sim:
        #show_simulation()



if __name__ == "__main__":

    main()

