import streamlit as st
st.set_page_config(page_title="VTA E-Bus Portal", page_icon="🚌")
from page_files.dashboard import dashboard
from page_files.history import show_history
from page_files.vehicles import show_vehicles
# from page_files.chargers import show_chargers
from components.optimization import opt_form
from calls.error_email import send_email
from streamlit_option_menu import option_menu



##########################################################
# Setup
##########################################################

def main():

    st.title("VTA Electric Bus Data Portal")
    selected = option_menu(None, ["Dashboard" , "Vehicles", "History"], 
    # icons from bootstrap icons
    icons=["speedometer", "bus-front", "clock-history", "cpu"],
    styles = {
    "container": {"padding": "0", "background-color": "#f0ece2", "border-radius": "10px"},
    # "menu-title": {"font-weight": "bold", "margin": "10px"},
    # "menu-icon": {"color": "black", "font-size": "24px", "margin-right": "5px"},
    "nav": {"margin": "0", "padding": "0"},
    "nav-item": {"display": "inline-block", "margin": "0", "list-style-type": "none"},
    "nav-link": {
        "padding": "10px 20px",
        "text-align": "center",
        "border-radius": "10px 10px 0 0",  # Rounded only at the top
        # "margin": "0 5px",
        "color": "black",
        "font-size": "16px",
        "text-decoration": "none",
        # make a little darker when not hovered to show it's clickable
        "background-color": "#e5e5e5",
    },
    "icon": {"color": "black", "font-size": "24px", "position": "relative", "top": "3px"},
    "nav-link-selected": {"background-color": "#50c878", "font-weight":  "normal"},
    },

    menu_icon="cast", default_index=0, orientation="horizontal")
    if selected == "Dashboard":
        dashboard()
    elif selected == "Vehicles":
        show_vehicles()
    elif selected == "History":
        show_history()
    # elif selected == "Optimization (Future)":
    #     opt_form()


    # dash, vehicles, hist = st.tabs(["Dashboard", 
    #                                             # "Location", 
    #                                             "Vehicles", 
    #                                             # "Chargers",
    #                                             "History",
    #                                     # "Optimization (Future)",
    #                                 #    "APIs",
    #                                     # "Energy Prediction",
    #                                     # # "Simulation", "Cost Analysis",
    #                                     # "Config"
    #                                     ])
    
    # with dash:
    #     dashboard()

    # with vehicles:
    #     show_vehicles()

    # with hist:
    #     show_history()

    # with opt:
    #     opt_form()


    # with chargers:
    #     show_chargers()




if __name__ == "__main__":

    main()

