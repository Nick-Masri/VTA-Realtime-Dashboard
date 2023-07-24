import streamlit as st
from calls.supa_select import supabase_soc_history
from components.charger_history import show_charger_history
from components.block_history import get_block_data, show_and_format_block_history

def show_history():
    # Route History
    st.write("## History")
    # select vehicle or charger history
    selection = st.selectbox("Select History", ["Block Drive History", "Charging History"])
    if selection == "Charging History":
        show_charger_history()
    elif selection == "Block Drive History":
        df = supabase_soc_history()
        df = df.sort_values('vehicle')
        blocks = get_block_data()
        st.warning("We are currently aware of an issue where the block historical data disappears every now and then. We are working on a fix for this.")
        show_and_format_block_history(blocks, df, key="all")

