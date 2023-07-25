import streamlit as st
from page_files.dashboard import get_overview_df
from calls.supa_select import supabase_blocks
from calls.chargepoint import chargepoint_stations
import data
import pandas as pd

def opt_form():

    serving, charging, idle, offline, df = get_overview_df()
    blocks = supabase_blocks(active=False)
    blocks = blocks.drop_duplicates(subset=['block_id'])

    # Mileage Data
    mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}

    with st.form("opt_input"):
        buses, block_tab, chargers = st.tabs(["Buses", "Blocks", "Chargers"])
        with buses:
            st.write("# Buses")
            df = df.sort_values('transmission_hrs', ascending=True)
            df = df[['vehicle', 'soc', 'status', 'last_seen']]
            df['Select'] = df.apply(lambda row: True if row['status'] != 'Offline' else False, axis=1)
            column_config = data.dash_column_config
            column_config['last_seen'] = st.column_config.TextColumn("Time Offline", disabled=True)
            column_config['status'] = st.column_config.SelectboxColumn("Status", 
                                                                        options=['Idle', 'Charging',],
                                                                       disabled=False)
            # make str with percentage sign
            # df['soc'] = df['soc'].astype(float) * 100
            df['soc'] = df['soc'].astype(int)
            df['soc'] = df['soc'].astype(str) + '%'
            column_config['soc'] = st.column_config.TextColumn("State of Charge", disabled=False)
            edited_buses_df = st.data_editor(df, hide_index=True, column_config=column_config,
                                            use_container_width=True,
                                            column_order=['Select', 'vehicle', 'soc', 'status', 'last_seen'])
        with block_tab:
            st.write("# Blocks")
            blocks = blocks[['id', 'block_id', 'block_startTime', 'block_endTime']]
            blocks['Select'] = True
            blocks['Mileage'] = blocks['block_id'].map(mileages)
            blocks['block_startTime'] = pd.to_datetime(blocks['block_startTime'], format="%H:%M:%S")
            blocks['block_endTime'] = pd.to_datetime(blocks['block_endTime'], format="%H:%M:%S")
            blocks['block_id'] = blocks['block_id'].astype(str)
            edited_blocks_df = st.data_editor(blocks, hide_index=True, use_container_width=True,
                        column_config={
                            "id": st.column_config.NumberColumn(
                                    "Route ID",
                                    disabled=False
                            ),
                                "block_id": st.column_config.TextColumn(
                                    "Block ID",
                                    disabled=False
                                ),
                                "block_startTime": st.column_config.TimeColumn(
                                    "Start Time",
                                    disabled=False,
                                    format="h:mmA"
                                ),
                                "block_endTime": st.column_config.TimeColumn(  
                                    "End Time",
                                    disabled=False,
                                    format="h:mmA"
                                ),
                                "Mileage": st.column_config.NumberColumn(
                                    "Mileage",
                                    disabled=False
                                )},
                            column_order=['Select', 'id', 'block_id', 'block_startTime', 'block_endTime', 'Mileage'],
                            num_rows="dynamic")

        with chargers:
            st.write("# Chargers ")
            chargers_df = chargepoint_stations()
            chargers_df = chargers_df[['stationName', 'networkStatus']]
            chargers_df['Select'] = chargers_df.apply(lambda row: True if row['networkStatus'] == 'Reachable' else False, axis=1)
            # change station name from format of VTA / STATION #1 to Station 1
            chargers_df['stationName'] = chargers_df['stationName'].str.replace(' / ', ' ')
            chargers_df['stationName'] = chargers_df['stationName'].str.replace('VTA STATION #', 'Station ')
            edited_chargers_df = st.data_editor(chargers_df, hide_index=True, use_container_width=True,
                                                column_config={
                                                    "stationName": st.column_config.TextColumn(
                                                        "Station",
                                                        disabled=True
                                                    ),
                                                    "networkStatus": st.column_config.TextColumn(
                                                        "Status",
                                                        disabled=True
                                                    )},
                                                column_order=['Select', 'stationName', 'networkStatus'])

            submit = st.form_submit_button("Submit")

        if submit:
            selected_buses = edited_buses_df[edited_buses_df.Select == True]
            selected_blocks = edited_blocks_df[edited_blocks_df.Select == True]
            selected_chargers = edited_chargers_df[edited_chargers_df.Select == True]
            col1, col2, col3 = st.columns(3)
            col1.write("Buses:")
            selected_buses = selected_buses[['vehicle', 'soc', 'status']]
            col1.dataframe(selected_buses, hide_index=True, use_container_width=True)
            col2.write("Blocks:")
            selected_blocks = selected_blocks[['block_id', 'block_startTime', 'block_endTime', 'Mileage']]
            selected_blocks['block_id'] = selected_blocks['block_id'].astype(str)
            col2.dataframe(selected_blocks, hide_index=True, use_container_width=True)
            col3.write("Chargers:")
            selected_chargers = selected_chargers[['stationName']]
            col3.dataframe(selected_chargers, hide_index=True, use_container_width=True)

            # solve
            # st.write("Solving...")
            # results = chargeopt.run(selected_buses, selected_blocks, selected_chargers)
