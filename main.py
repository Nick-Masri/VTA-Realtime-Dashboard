import streamlit as st
st.set_page_config(page_title="VTA E-Bus Portal", page_icon="🚌")
from page_files.dashboard import dashboard
from page_files.history import show_history
from page_files.vehicles import show_vehicles
from page_files.chargers import show_chargers
from calls.error_email import send_email


##########################################################
# Setup
##########################################################

def main():

    st.title("VTA Electric Bus Data Portal")
    
    try: 
        dash, vehicles, hist = st.tabs(["Dashboard", 
                                                    # "Location", 
                                                    "Vehicles", 
                                                    # "Chargers",
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

            # with chargers:
            #     show_chargers()

    # if the app is down
    except Exception as e:
        st.warning("Some Features are not working")
        # st.error(f"Sorry, the app is down. We are working to resolve this issue as soon as possible.")
        # send_email(f"Error: {e}")

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

