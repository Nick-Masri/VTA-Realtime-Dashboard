import os

import streamlit as st
import pandas as pd
from st_aggrid import GridOptionsBuilder, DataReturnMode, AgGrid

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Vehicles", "Blocks", "Chargers", "Parameters", "Run Optimization", "Results"]
)

output = pd.read_csv(os.path.join(os.getcwd(), "output.csv"))
# output = pd.read_csv()

with tab1:
    with st.form("chargeopt-form"):
        ########################
        # Vehicles
        ########################

        st.write("# Vehicles")
        vehicles = output[['Vehicle', 'SOC (%)', 'Last Online']]
        vehicles = vehicles.sort_index(ascending=True)

        # Set up the grid options
        gb = GridOptionsBuilder.from_dataframe(vehicles)
        gb.configure_default_column(groupable=False, value=True, enableRowGroup=True,
                                    aggFunc='sum', editable=True, min_column_width=1)
        gb.configure_selection('multiple', use_checkbox=True, pre_selected_rows=[i+1 for i in range(len(vehicles))])
        gb.configure_grid_options(domLayout='normal')

        # Build the grid options
        gridOptions = gb.build()

        return_mode = DataReturnMode.__members__['FILTERED_AND_SORTED']

        vehicleResponse = AgGrid(vehicles, gridOptions=gridOptions,
                                 width='100%')

        submitted = st.form_submit_button("Next Page")
        # # Get the list of selected checkboxes
        # if selected_rows is not None:
        #     selected_checkboxes = selected_rows['selected_rows']
        #     st.write(selected_checkboxes)

        # Submit
with tab2:
    with st.form("blocks"):
        ########################
        # Blocks
        ########################

        st.write("# Blocks")
        data = pd.read_excel('allRoutes.xlsx')

        # Set up the grid options
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_default_column(groupable=False, value=True, enableRowGroup=True,
                                    aggFunc='sum', editable=True, min_column_width=1)
        gb.configure_selection('multiple', use_checkbox=True)
        gb.configure_grid_options(domLayout='normal')

        # Build the grid options
        gridOptions = gb.build()

        # Display the AgGrid
        selected_rows = AgGrid(data,
                               gridOptions=gridOptions,
                               width='100%', )

        submitted = st.form_submit_button("Next Page")
