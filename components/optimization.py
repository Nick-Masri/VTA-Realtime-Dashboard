import streamlit as st
from helper import convert_block_time
from page_files.dashboard import get_overview_df
from calls.supa_select import supabase_blocks
from calls.chargepoint import chargepoint_stations
import data
import pandas as pd
from chargeopt.optimization import ChargeOpt
import os
import plotly.graph_objects as go

import altair as alt
import numpy as np
def opt_form():

    keys = ['buses', 'blocks', 'chargers', 'results', 'startTimeNum']
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None

    serving, charging, idle, offline, df = get_overview_df()

    # Mileage Data
    mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}
    with st.form("Optimization Form"):

        st.write("# Buses")
        df = df.sort_values('transmission_hrs', ascending=True)
        df = df[['vehicle', 'soc', 'status', 'last_seen']]
        df['Select'] = df.apply(lambda row: True if row['status'] != 'Offline' else False, axis=1)
        column_config = data.dash_column_config
        column_config['last_seen'] = st.column_config.TextColumn("Time Offline", disabled=True)
        column_config['status'] = st.column_config.SelectboxColumn("Status", 
                                                                    options=['Idle', 'Charging',],
                                                                    disabled=False)
        df['soc'] = df['soc'].astype(int).astype(str) + '%'
        column_config['soc'] = st.column_config.TextColumn("State of Charge", disabled=False)
        edited_buses_df = st.data_editor(df, hide_index=True, column_config=column_config,
                                        use_container_width=True,
                                        column_order=['Select', 'vehicle', 'soc', 'status', 'last_seen'])

        st.write("# Blocks")


        df = pd.read_excel('data_files/BlockSummary_Oct2023_REV_identified below 165 mi range.xlsx', header=1)
        df = df[['BLOCK', 'TOTAL MILES', 'PULL OUT', 'PULL IN']]
        df = df[df['TOTAL MILES'] > 0]

        # approved_blocks = st.toggle('Use approved blocks', value=True)

        # TODO: figure out how to use approved blocks toggle
        # if approved_blocks:
            # from block 476 to 6081 
        df = df.loc[50:79]

        blocks = df.copy()

        # highlight as many blocks as there are buses  
        blocks['Select'] = False
            
        # if select is not true, make false
        # blocks['Select'] = blocks['Select'].fillna(False)
        blocks.columns = ['block_id', 'Mileage', 'block_startTime', 'block_endTime', 'Select']
        blocks['block_id'] = blocks['block_id'].astype(str)
        # route id is first two digits of block id
        blocks['id'] = blocks['block_id'].str[:2]

        # convert block start and end times
        blocks['block_startTime'] = blocks['block_startTime'].apply(convert_block_time)
        blocks['block_endTime'] = blocks['block_endTime'].apply(convert_block_time)

        # sort by mileage
        blocks = blocks.sort_values('Mileage', ascending=True)

        # drop nans
        blocks = blocks.dropna(axis=1)

        num_buses = len(edited_buses_df[edited_buses_df.Select == True])
        for i in range(num_buses):
            blocks.iat[i, blocks.columns.get_loc('Select')] = True
        
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

        submit = st.form_submit_button("Submit")



        
    # with options:
    #     # st.info("Route Assignment Options Coming Soon")
    #     # run_type = st.radio("Route Assignment", options=['Heuristic', 'Optimal'])
    #     st.info("Optimization Options Coming Soon")
        # if run_type == 'Provide Assignments':
        #     st.dataframe(pd.DataFrame({'bus': [1, 2, 3, 4, 5], 'day': [1, 1, 1, 1, 1], 'route': [np.nan, np.nan, np.nan, np.nan, np.nan]}))
        #     st.info("Not legit for now, need to add dataframe editor")
        # elif run_type == 'Heuristic':
        #     st.info("Heuristic Coming Soon")
            
            
        # display current config options from chargeopt/config.yml

        if submit: 
            st.toast("Solving...")

            # # get df's from session state
            # edited_buses_df = st.session_state['buses']
            # edited_blocks_df = st.session_state['blocks']
            # edited_chargers_df = st.session_state['chargers']

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

            results, startTimeNum = opt.solve()

            st.toast("Complete")
            st.toast(results)
            
            # save results, selected buses, blocks, and chargers to session state
            st.session_state['results'] = results
            st.session_state['startTimeNum'] = startTimeNum
            st.session_state['buses'] = selected_buses
            st.session_state['blocks'] = selected_blocks
            st.session_state['chargers'] = selected_chargers





    # get df's from session state
    results = st.session_state['results']
    startTimeNum = st.session_state['startTimeNum']
    selected_buses = st.session_state['buses']
    selected_blocks = st.session_state['blocks']
    selected_chargers = st.session_state['chargers']

    show_results(selected_buses, selected_blocks, selected_chargers, results, startTimeNum)

def show_results(selected_buses, selected_blocks, selected_chargers, results, startTimeNum):
    if selected_blocks is None or selected_chargers is None or selected_buses is None: 
        return
    else:
        with st.expander("Input Data", expanded=True):
            col1, col2, col3 = st.columns(3)

            col1.write("Buses:")
            col1.dataframe(selected_buses, hide_index=True, use_container_width=True)
            
            col2.write("Blocks:")
            
            col2.dataframe(selected_blocks, hide_index=True, use_container_width=True)

            col3.write("Chargers:")
            col3.dataframe(selected_chargers, hide_index=True, use_container_width=True)

        if results == 'Model is infeasible':
            st.warning(results)
        elif results == 'Optimal solution found':
            # st.write(results)

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
            #             assignment_df.to_csv(f'{path}/assignments_{filename}.csv')


            # # visualize twodim df
            # # bus,time,powerCB,gridPowToB,eB
            # here is where it is saved
            # path = os.path.join(os.getcwd(), "chargeopt", "outputs")
            # twodim_df.to_csv(f'{path}/{filename}.csv')
            # visualize in altair
            # Getting the path to the csv files
            path = os.path.join(os.getcwd(), "chargeopt", "outputs")

            filename = results_df["case_name"]

            # visualize assignments: 'bus', 'day', 'route'
            assignment_df = pd.read_csv(f'{path}/assignments_{filename}.csv')

            # map bus to bus number using edited buses_df
            # reset index
            st.write("### Bus Assignments")
            buses = selected_buses.reset_index()
            assignment_df['bus'] = assignment_df['bus'].map(buses['vehicle'])
            # map route to route number using edited blocks_df
            routes = selected_blocks.reset_index()
            assignment_df['route'] = assignment_df['route'].map(routes['block_id'])
            assignment_df = assignment_df[assignment_df['assignment'] == 1]
            today = pd.Timestamp.today().strftime("%A")
            days = []
            for i in range(7):
                day = pd.Timestamp.today() + pd.Timedelta(days=i)
                day = day.strftime("%A")
                days.append(day)
            day_map = {i: day for i, day in enumerate(days)}
            assignment_df['day'] = assignment_df['day'].map(day_map)

            assignment_df.drop(columns=['assignment'], inplace=True)
            # make day the first column
            assignment_df = assignment_df[['day', 'bus', 'route']]
            st.dataframe(assignment_df, use_container_width=True, hide_index=True)


            # st.write("### Assignment Distribution")
            # filtered_assignment_df = assignment_df[assignment_df['assignment'] == 1]
            # st.write(
            #     alt.Chart(filtered_assignment_df).mark_circle().encode(
            #         x='day:O',
            #         y='route:O',
            #         c='route:N',
            #         column='bus:N',
            #         size=alt.value(100),  # controls the size of circles
            #         tooltip=['day', 'route', 'bus']
            #     ).properties(
            #         width=alt.Step(40)  # controls width of each facet
            #     )
            # )


            # visualize twodim df: 'bus', 'time', 'powerCB', 'gridPowToB', 'eB'
            twodim_df = pd.read_csv(f'{path}/{filename}.csv')
            twodim_df = twodim_df.iloc[startTimeNum:]

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

            st.write("### Energy Distribution in Bus Batteries")
            cols = st.columns(3)
            for bus in twodim_df['bus'].unique():
                col = cols[bus % 3]
                with col:
                    bus_df = twodim_df[twodim_df['bus'] == bus]

                    # Initialize the figure
                    fig = go.Figure()
                                
                    # Add line plot to the figure
                    fig.add_trace(go.Scatter(x=bus_df['time'], y=bus_df['eB'], mode='lines', fill='tozeroy',
                                        name='Power CB', line=dict(color='red'), showlegend=False))
                    
                    # Get times when charging changes
                    charging_starts = bus_df[bus_df['powerCB'] > 0]
                    
                    # Add the fill for charging times
                    fig.add_trace(go.Scatter(x=charging_starts['time'], y=440*np.ones(len(charging_starts)), mode='lines', fill='tozeroy',
                                            name='Charging', line=dict(color='rgba(230, 230, 0, 1)'), showlegend=False))  # rgba color for semi-transparent dark yellow

                    # Add a vertical dash line every 96 time steps
                    for i in range(96, len(bus_df), 96):
                        fig.add_shape(type="line",
                                    x0=i, y0=0, x1=i, y1=1,
                                    yref="paper",
                                    line=dict(color="RoyalBlue", width=1, dash="dashdot"))
                        
                    # Update layout properties
                    fig.update_layout(title=f'Bus {bus} Energy', 
                                    xaxis_title='time', 
                                    yaxis_title='energy', 
                                    showlegend=False)  # Turn off the legend

                    # Display the plot
                    st.plotly_chart(fig, use_container_width=True)
