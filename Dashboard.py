# from streamlit_supabase_auth import login_form, logout_button
import streamlit as st
from streamlit_supabase_auth import login_form, logout_button

# from energy_predictions import energy_predictions
from soc_view import show_soc
from opt_input import selection_process
from config import show_config
from performance import performance


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
        tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "Performance", "Optimization",
                                          # "Simulation", "Cost Analysis",
                                          "Config"])
        with tab1:
            show_soc()

        with tab2:
            performance()

        with tab3:
            selection_process()

        with tab4:
            show_config()

        # with tab2:
        #     energy_predictions()


if __name__ == "__main__":
    main()
