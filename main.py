import streamlit as st
st.set_page_config(page_title="VTA E-Bus Portal", page_icon="🚌")
from page_files.dashboard import dashboard
from page_files.history import show_history
from page_files.vehicles import show_vehicles
from page_files.chargers import show_chargers
from components.optimization import opt_form
from calls.error_email import send_email
from streamlit_option_menu import option_menu



##########################################################
# Setup
##########################################################

def main():

    st.title("VTA Electric Bus Data Portal")

    # tabs for page selection
    # add icons
    dash, veh, hist = st.tabs(["📊 Dashboard", "🚍 Vehicles", "🕓 History"])

    with dash:
        dashboard()
        
        st.toast("Updates: Updated charging history tab and removed charging tab. \n\n More Details: Removed charger tab since all active chargers are shown on the dashboard tab. Integrating ML for energy consumption predictions is next.")


    with veh:
        show_vehicles()

    with hist:
        show_history()




if __name__ == "__main__":

    main()

