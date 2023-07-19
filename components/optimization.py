import streamlit as st
from page_files.dashboard import get_overview_df
from calls.supa_select import supabase_blocks
from calls.chargepoint import chargepoint_stations
import data

def opt_form():

    serving, charging, idle, offline, df = get_overview_df()
    blocks = supabase_blocks(active=False)
    blocks = blocks.drop_duplicates(subset=['block_id'])

    # Mileage Data
    mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}

    with st.form("opt_input"):
        st.write("# Buses")
        df = df.sort_values('transmission_hrs', ascending=True)
        df = df[['vehicle', 'soc', 'status', 'last_seen']]
        df['Select'] = df.apply(lambda row: True if row['status'] != 'Offline' else False, axis=1)
        column_config = data.dash_column_config
        column_config['last_seen'] = st.column_config.TextColumn("Time Offline", disabled=True)
        column_config['status'] = st.column_config.TextColumn("Status", disabled=True)
        # make str with percentage sign
        # df['soc'] = df['soc'].astype(float) * 100
        df['soc'] = df['soc'].astype(int)
        df['soc'] = df['soc'].astype(str) + '%'
        column_config['soc'] = st.column_config.TextColumn("State of Charge", disabled=False)
        edited_buses_df = st.data_editor(df, hide_index=True, column_config=column_config,
                                         use_container_width=True,
                                         column_order=['Select', 'vehicle', 'soc', 'status', 'last_seen'])

        st.write("# Blocks")
        blocks = blocks[['id', 'block_id', 'block_startTime', 'block_endTime']]
        blocks['Select'] = True
        blocks['Mileage'] = blocks['block_id'].map(mileages)
        edited_blocks_df = st.data_editor(blocks, hide_index=True, use_container_width=True,
                       column_config={
                           "id": st.column_config.TextColumn(
                                 "Route ID",
                                 disabled=True
                            ),
                            "block_id": st.column_config.TextColumn(
                                "Block ID",
                                disabled=True
                            ),
                            "block_startTime": st.column_config.TimeColumn(
                                "Start Time",
                                disabled=True,
                                format="hh:mmA"
                            ),
                            "block_endTime": st.column_config.TimeColumn(  
                                "End Time",
                                disabled=True,
                                format="hh:mmA"
                            )},
                          column_order=['Select', 'id', 'block_id', 'block_startTime', 'block_endTime', 'Mileage'])
        

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
        # st.write("Buses:")
        selected_buses = edited_buses_df[edited_buses_df.Select == True].vehicle.values.tolist()
        # st.write("Blocks")
        selected_blocks = edited_blocks_df[edited_blocks_df.Select == True].block_id.values.tolist()
        # st.write("Chargers:")
        selected_chargers = edited_chargers_df[edited_chargers_df.Select == True].stationName.values.tolist()
        col1, col2, col3 = st.columns(3)
        col1.write("Buses:")
        col1.write(selected_buses)
        col2.write("Blocks:")
        col2.write(selected_blocks)
        col3.write("Chargers:")
        col3.write(selected_chargers)

        # solve
        # st.write("Solving...")
        # results = chargeopt.run(selected_buses, selected_blocks, selected_chargers)
