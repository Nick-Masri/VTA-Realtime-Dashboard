import streamlit as st
from page_files.dashboard import get_overview_df
from calls.supa_select import supabase_blocks
from calls.chargepoint import chargepoint_stations
from datetime import datetime
import data
import pandas as pd
from chargeopt.optimization import ChargeOpt
import os
import plotly.graph_objects as go

import altair as alt
import plotly.express as px

def opt_form():

    supabase = False

    serving, charging, idle, offline, df = get_overview_df()

    # Mileage Data
    mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}

    with st.form("opt_input"):
        buses, block_tab, chargers, options = st.tabs(["Buses", "Blocks", "Chargers", "Options"])
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
    
            supabase = False
            # if using supabase
            if supabase:
                blocks = supabase_blocks(active=False)
                blocks = blocks.drop_duplicates(subset=['block_id'])
                blocks = blocks[['id', 'block_id', 'block_startTime', 'block_endTime']]
                blocks['Select'] = True
                blocks['Mileage'] = blocks['block_id'].map(mileages)
                blocks['block_startTime'] = pd.to_datetime(blocks['block_startTime'], format="%H:%M:%S")
                blocks['block_endTime'] = pd.to_datetime(blocks['block_endTime'], format="%H:%M:%S")
                blocks['block_id'] = blocks['block_id'].astype(str)

            else:

                block_data = {
                'block_id': ['7771', '7172', '6682', '6675', '6180', '7073', '7774', '7173/sx', '6686'],
                # 'Mileage': [148, 119.9, 144.4, 144.4, 149.3, 113.3, 48.3, 29.2, 55.0]
                # so it runs now, but real is above
                'Mileage': [100, 100.9, 100.4, 100.4, 100.3, 113.3, 48.3, 29.2, 55.0]

                }

                blocks = pd.DataFrame(block_data)


                # highlight as many blocks as there are buses  
                blocks['Select'] = False
                num_buses = len(edited_buses_df[edited_buses_df.Select == True])
                for i in range(num_buses):
                    blocks.loc[i, 'Select'] = True
                    
                # if select is not true, make false
                blocks['Select'] = blocks['Select'].fillna(False)
                
                # make start time and end time 6AM and 6PM (make it a time object)
                blocks['block_startTime'] = pd.to_datetime('6:00:00', format="%H:%M:%S")
                blocks['block_endTime'] = pd.to_datetime('12:00:00', format="%H:%M:%S")

                # make id the first two digits of the block number
                blocks['id'] = blocks['block_id'].str[:2]


            # # sort by mileage
            # blocks = blocks.sort_values('Mileage', ascending=True)
            
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
            if chargers_df is not None:
                chargers_df = chargers_df[['stationName', 'networkStatus']]
                chargers_df['Select'] = chargers_df.apply(lambda row: True if row['networkStatus'] == 'Reachable' else False, axis=1)
                # change station name from format of VTA / STATION #1 to Station 1
                chargers_df['stationName'] = chargers_df['stationName'].str.replace(' / ', ' ')
                chargers_df['stationName'] = chargers_df['stationName'].str.replace('VTA STATION #', 'Station ')
            else:
                fake_stations = {'stationName': ['Station 1', 'Station 2', 'Station 3', 'Station 4', 'Station 5'],
                'networkStatus': ['Reachable', 'Reachable', 'Reachable', 'Reachable', 'Reachable'],
                'Select': [True, True, True, True, True]}
                chargers_df = pd.DataFrame(fake_stations)
                
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
            
        with options:
            st.info("Route Assignment Options Coming Soon")
            run_type = st.radio("Route Assignment", options=['Provide Assignments', 'Heuristic', 'Optimal'], disabled=True)

            # display current config options from chargeopt/config.yml
            submit = st.form_submit_button("Submit")

    if submit:
        selected_buses = edited_buses_df[edited_buses_df.Select == True]
        selected_blocks = edited_blocks_df[edited_blocks_df.Select == True]
        selected_chargers = edited_chargers_df[edited_chargers_df.Select == True]

        selected_buses = selected_buses[['vehicle', 'soc', 'status']]
        selected_blocks = selected_blocks[['block_id', 'block_startTime', 'block_endTime', 'Mileage']]
        # make start time and end time hours and minutes, not military time, and include AM/PM)
        selected_blocks['block_startTime'] = selected_blocks['block_startTime'].dt.strftime("%I:%M %p")
        selected_blocks['block_endTime'] = selected_blocks['block_endTime'].dt.strftime("%I:%M %p")
        selected_blocks['block_id'] = selected_blocks['block_id'].astype(str)
        selected_chargers = selected_chargers[['stationName']]

      

        opt = ChargeOpt(selected_buses, selected_blocks, selected_chargers)

        results = opt.solve()

        with st.expander("Input Data"):
            col1, col2, col3 = st.columns(3)

            col1.write("Buses:")
            col1.dataframe(selected_buses, hide_index=True, use_container_width=True)
            
            col2.write("Blocks:")
            
            col2.dataframe(selected_blocks, hide_index=True, use_container_width=True)

            col3.write("Chargers:")
            col3.dataframe(selected_chargers, hide_index=True, use_container_width=True)

        if results is None:
            st.error("Report Error")
        elif results == 'Optimal solution found':
            results_df = pd.read_csv(os.path.join(os.getcwd(), 'chargeopt', 'outputs', 'results.csv')).iloc[-1]
            results_df.dropna(inplace=True)
            #  results_df  
            #     {
            #         "case_name": filename,
            #         "numBuses": B,
            #         "ebMaxKwh": eB_max,
            #         "numChargers": numChargers,
            #         "chargerPower": pCB_ub,
            #         "chargerEff": eff_CB,
            #         "routes": str(routes),
            #         "gridMaxPower": gridKWH,
            #         "obj_val": obj_val,
            #         "sol_time": sol_time,
            #         "date": current_date,
            #         # "type": config['runType']
            #     },
            with st.expander("Results and Input Details"): 
                st.dataframe(results_df, use_container_width=True)
            cost = results_df['obj_val']
            cost = float(cost)
            st.metric("Cost", f"${cost:.2f}")
            # visualize in altair
     
            # visualize assignments:
            # 'bus', 'day', 'route'
            # here is where it is saved
            #             assignment_df.to_csv(f'{path}/outputs/assignments_{filename}.csv')


            # # visualize twodim df
            # # bus,time,powerCB,gridPowToB,eB
            # here is where it is saved
            # path = os.path.join(os.getcwd(), "chargeopt")
            # twodim_df.to_csv(f'{path}/outputs/{filename}.csv')
               # visualize in altair
            # Getting the path to the csv files
            path = os.path.join(os.getcwd(), "chargeopt", "outputs")
            filename = results_df["case_name"]

            # visualize assignments: 'bus', 'day', 'route'
            assignment_df = pd.read_csv(f'{path}/assignments_{filename}.csv')


            st.write("### Assignment Distribution")
            filtered_assignment_df = assignment_df[assignment_df['assignment'] == 1]
            st.write(
                alt.Chart(filtered_assignment_df).mark_circle().encode(
                    x='day:O',
                    y='route:O',
                    color='route:N',
                    column='bus:N',
                    size=alt.value(100),  # controls the size of circles
                    tooltip=['day', 'route', 'bus']
                ).properties(
                    width=alt.Step(40)  # controls width of each facet
                )
            )


            # visualize twodim df: 'bus', 'time', 'powerCB', 'gridPowToB', 'eB'
            twodim_df = pd.read_csv(f'{path}/{filename}.csv')

            st.write("### Power CB Distribution")
            cols = st.columns(3)
            for bus in twodim_df['bus'].unique():
                col = cols[bus % 3]
                with col:
                    bus_df = twodim_df[twodim_df['bus'] == bus]
                    
                    # Initialize the figure
                    fig = go.Figure()
                    
                    # Add line plot to the figure
                    fig.add_trace(go.Scatter(x=bus_df['time'], y=bus_df['powerCB'], mode='lines', fill='tozeroy',
                                        name='Power CB', line=dict(color='blue')))
                    
                    # Add scatter plot to the figure with dot markers and without a color scale
                    # fig.add_trace(go.Scatter(x=bus_df['time'], y=bus_df['chargerUse'], mode='markers', 
                    #                         marker=dict(color='red'), name='Charger Use'))
                    
                    # add a vertical dash line every 96 time steps
                    for i in range(96, len(bus_df), 96):
                        fig.add_shape(type="line",
                                    x0=i, y0=0, x1=i, y1=bus_df['powerCB'].max(),
                                    line=dict(color="RoyalBlue", width=1, dash="dashdot"))

                    # Update layout properties
                    fig.update_layout(title=f'Bus {bus} Power Recieved', 
                                    xaxis_title='time', 
                                    yaxis_title='powerCB', 
                                    legend_title='Legend')

                    # Display the plot
                    st.plotly_chart(fig, use_container_width=True)

            cols = st.columns(3)
            st.write("### Energy Distribution in Bus Batteries")
            for bus in twodim_df['bus'].unique():
                col = cols[bus % 3]
                with col:
                    bus_df = twodim_df[twodim_df['bus'] == bus]

                    # Initialize the figure
                    fig = go.Figure()
                    
                    # Add line plot to the figure
                    fig.add_trace(go.Scatter(x=bus_df['time'], y=bus_df['eB'], mode='lines', fill='tozeroy',
                                        name='Power CB', line=dict(color='red')))
                    
                    # add a vertical dash line every 96 time steps
                    for i in range(96, len(bus_df), 96):
                        fig.add_shape(type="line",
                                    x0=i, y0=0, x1=i, y1=1,
                                    yref="paper",
                                    line=dict(color="RoyalBlue", width=1, dash="dashdot"))
                        
                    # Update layout properties
                    fig.update_layout(title=f'Bus {bus} Energy', 
                                    xaxis_title='time', 
                                    yaxis_title='powerCB', 
                                    legend_title='Legend')

                    # Display the plot
                    st.plotly_chart(fig, use_container_width=True)



        st.write(results)
        st.toast("Solving...")
        
