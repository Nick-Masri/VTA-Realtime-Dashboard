import streamlit as st
st.set_page_config(page_title="VTA E-Bus Portal", page_icon="🚌", layout="wide")
from page_files.dashboard import dashboard
from page_files.history import show_history
from page_files.vehicles import show_vehicles
from components.optimization import opt_form
from page_files.energy_cons import show_energy_cons
from calls import demo_state
from calls.bundled import active_info




##########################################################
# Setup
##########################################################

def main():

    st.title("VTA Electric Bus Data Portal")

    # Touch the shared feeds first so the disclosure can be rendered above the
    # tabs. These are cached, so the dashboard reuses the same results.
    try:
        active_info()
    except Exception:
        pass
    demo_state.render_banner()
    demo_state.render_issues()
    # Lighting bolt emoji: ⚡
    # light bulb emoji: 💡
    dash, veh, hist, enrg, opt = st.tabs(["📊 Dashboard", "🚍 Vehicles", "🕓 History", "⚡ Energy Predictions", "💡 Optimization"])
    

    with dash:
        dashboard()

    with veh:
        show_vehicles()

    with hist:
        show_history()

    # with pred:
    #     energy_predictions()

    with opt:
        opt_form()

    #with charge:
        #show_form()
    
    with enrg:
        show_energy_cons()
    
    #with sim:
        #show_simulation()



if __name__ == "__main__":

    main()

