# from streamlit_supabase_auth import login_form, logout_button
import streamlit as st
from streamlit_supabase_auth import login_form, logout_button

from components.api import show_apis
from components.dashboard import dashboard
from components.config import show_config
from components.optimization import opt_form
from components.performance import performance
from components.active_blocks import show_active_blocks
from components.vehicle_map import vehicle_map


##########################################################
# Setup
##########################################################

# logging.getLogger('googleapicliet.discovery_cache').setLevel(logging.ERROR)


def main():
    st.title("E-Bus Data Portal")

    session = login_form(
        url="https://ztkxpouaswqlomjpjnwl.supabase.co",
        apiKey="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp0a3hwb3Vhc3dxbG9tanBqbndsIiwicm9sZSI6ImFub24iLCJpYXQiOjE2ODY5MDczMTEsImV4cCI6MjAwMjQ4MzMxMX0.w6FazqiQ9BA1oSbPBf4MmXqeye7Y2U2b5Y2ERDWdcA8",
        # providers=["google"]
    )

    if session:
        # login stuffvta
        st.experimental_set_query_params(page=["success"])

        with st.sidebar:
            st.write(f"Welcome {session['user']['email']}")
            logout_button(
                url="https://ztkxpouaswqlomjpjnwl.supabase.co",
                apiKey="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp0a3hwb3Vhc3dxbG9tanBqbndsIiwicm9sZSI6ImFub24iLCJpYXQiOjE2ODY5MDczMTEsImV4cCI6MjAwMjQ4MzMxMX0.w6FazqiQ9BA1oSbPBf4MmXqeye7Y2U2b5Y2ERDWdcA8",
                # providers=["google"]
            )

        # show soc
        dash, location, hist, opt, api = st.tabs(["Realtime", "Location", "History",
                                                  "Optimization (Future)",
                                                  "APIs",
                                                  # # "Simulation", "Cost Analysis",
                                                  # "Config"
                                                  ])
        with dash:
            dashboard()

        with location:
            vehicle_map()

        with hist:
            performance()

        with opt:
            opt_form()

        # with tab3:
        #     energy_predictions()
        # 
        with api:
            show_apis()

        # with config:
        #     show_config()


if __name__ == "__main__":
    main()
