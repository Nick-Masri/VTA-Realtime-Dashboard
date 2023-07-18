import streamlit as st
from page_files.dashboard import dashboard
from page_files.history import show_history
from page_files.vehicles import show_vehicles
from page_files.chargers import show_chargers


##########################################################
# Setup
##########################################################

def main():
    st.title("E-Bus Data Portal")

    dash, vehicles, chargers, hist = st.tabs(["Dashboard", 
                                                        # "Location", 
                                                        "Vehicles", 
                                                        "Chargers",
                                                        "History",
                                            #    "Optimization (Future)",
                                            #    "APIs",
                                               # "Energy Prediction",
                                               # # "Simulation", "Cost Analysis",
                                               # "Config"
                                               ])
    with dash:
        dashboard()

    with vehicles:
        show_vehicles()

    with hist:
        show_history()

    with chargers:
        show_chargers()
    # with opt:
    #     opt_form()
    #
    # with pred:
    #     energy_predictions()
    # #
    # with api:
    #     show_apis()

    # with config:
    #     show_config()


if __name__ == "__main__":

    main()

