import streamlit as st
from helper import convert_block_time
from page_files.dashboard import get_overview_df
from calls.supa_select import supabase_blocks
from calls.chargepoint import chargepoint_stations
import data
import pandas as pd
import yaml

from chargeopt import demo
from chargeopt.helpers import TARIFF
from chargeopt.optimization import ChargeOpt, is_partial, is_solved
from chargeopt.helpers import time_to_quarter
import os

import altair as alt
import numpy as np

# What a bus is doing at each quarter hour of the plan.
STATE_ORDER = ['Driving', 'Plugged in', 'Unplugged']
STATE_COLORS = ['#3F51B5', '#009688', '#CFD8DC']


def _as_quarter(value):
    """Block times reach here either as a clock string or as a quarter index."""
    if isinstance(value, str):
        return time_to_quarter(value)
    return int(value)


def _label_states(twodim_df, assignment_df, selected_blocks, coach_of):
    """One row per bus per quarter hour, labelled with what the bus is doing.

    chargerUse tells us when a bus is drawing power; the assignments tell us
    when it is out on a block. Everything else is parked and unplugged.
    """
    states = twodim_df[['bus', 'time', 'chargerUse']].copy()
    states['state'] = np.where(states['chargerUse'] > 0.5, 'Plugged in', 'Unplugged')

    blocks = selected_blocks.reset_index(drop=True)
    for _, row in assignment_df[assignment_df['assignment'] == 1].iterrows():
        if int(row['route']) >= len(blocks):
            continue
        block = blocks.iloc[int(row['route'])]
        day = int(row['day'])
        depart = _as_quarter(block['block_startTime']) - 1 + day * 96
        ret = _as_quarter(block['block_endTime']) - 1 + day * 96
        on_block = (states['bus'] == row['bus']) & states['time'].between(depart, ret)
        states.loc[on_block, 'state'] = 'Driving'

    states['coach'] = states['bus'].map(coach_of)
    return states


def _compress(states, origin):
    """Collapse runs of the same state into intervals.

    A rect per quarter hour would be a few thousand marks for no benefit; the
    schedule is a handful of stretches per bus.
    """
    spans = []
    for coach, frame in states.sort_values('time').groupby('coach'):
        rows = frame[['time', 'state']].to_numpy()
        run_start, run_state = rows[0]
        previous = rows[0][0]
        for moment, state in rows[1:]:
            if state != run_state or moment != previous + 1:
                spans.append((coach, run_start, previous + 1, run_state))
                run_start, run_state = moment, state
            previous = moment
        spans.append((coach, run_start, previous + 1, run_state))

    span_df = pd.DataFrame(spans, columns=['coach', 'start', 'end', 'state'])
    span_df['from'] = origin + pd.to_timedelta(span_df['start'] * 15, unit='m')
    span_df['to'] = origin + pd.to_timedelta(span_df['end'] * 15, unit='m')
    return span_df


def show_schedule(twodim_df, assignment_df, selected_blocks, coach_of, eb_max):
    origin = pd.Timestamp.today().normalize()
    states = _label_states(twodim_df, assignment_df, selected_blocks, coach_of)
    spans = _compress(states, origin)

    order = sorted(spans['coach'].unique())
    timeline = alt.Chart(spans).mark_bar(height=18).encode(
        x=alt.X('from:T', title=None,
                axis=alt.Axis(format='%a %-I%p', tickCount=8)),
        x2='to:T',
        # Every coach gets a label: thinning them defeats the point of a
        # per-bus timeline.
        y=alt.Y('coach:N', title=None, sort=order,
                axis=alt.Axis(labelOverlap=False, labelPadding=6)),
        color=alt.Color('state:N', title=None,
                        scale=alt.Scale(domain=STATE_ORDER, range=STATE_COLORS),
                        legend=alt.Legend(orient='top')),
        tooltip=[alt.Tooltip('coach:N', title='Coach'),
                 alt.Tooltip('state:N', title='Doing'),
                 alt.Tooltip('from:T', title='From', format='%a %-I:%M%p'),
                 alt.Tooltip('to:T', title='To', format='%a %-I:%M%p')],
    ).properties(height=max(200, 32 * len(order)))

    with st.container(border=True):
        st.markdown("**Where every bus is, hour by hour**")
        st.caption("Driving a block, plugged into a charger, or parked and unplugged.")
        st.altair_chart(timeline, width='stretch')

    charge = twodim_df[['bus', 'time', 'eB']].copy()
    charge['coach'] = charge['bus'].map(coach_of)
    charge['soc'] = charge['eB'] / eb_max * 100
    charge['at'] = origin + pd.to_timedelta(charge['time'] * 15, unit='m')

    soc_chart = alt.Chart(charge).mark_line(strokeWidth=1.6).encode(
        x=alt.X('at:T', title=None,
                axis=alt.Axis(format='%a %-I%p', tickCount=8)),
        y=alt.Y('soc:Q', title='State of charge (%)', scale=alt.Scale(domain=[0, 100])),
        color=alt.Color('coach:N', title='Coach'),
        tooltip=[alt.Tooltip('coach:N', title='Coach'),
                 alt.Tooltip('soc:Q', title='SOC', format='.0f'),
                 alt.Tooltip('at:T', title='At', format='%a %-I:%M%p')],
    ).properties(height=260)

    reserve = alt.Chart(pd.DataFrame([{'v': 20}])).mark_rule(
        color='#B71C1C', strokeDash=[5, 4]).encode(y='v:Q')

    with st.container(border=True):
        st.markdown("**Charge through the plan**")
        st.caption("Dashed line is the 20% reserve the schedule keeps every bus above.")
        st.altair_chart(soc_chart + reserve, width='stretch')



@st.cache_data(show_spinner=False)
def _config_defaults():
    with open(os.path.join(os.getcwd(), 'chargeopt', 'config.yml')) as handle:
        return yaml.safe_load(handle)


def scenario_controls():
    """Depot parameters for this run only, so the answer to "what if we added
    two chargers" is a button rather than a file edit."""
    cfg = _config_defaults()
    with st.expander("Scenario - try a depot you do not have yet"):
        st.caption(
            "These override chargeopt/config.yml for this run only. Every run "
            "is kept in the comparison table with the results, so two depots "
            "can be put side by side."
        )
        c1, c2, c3 = st.columns(3)
        extra = c1.number_input("Extra chargers", 0, 50, 0, step=1,
                                help="Added to the chargers ticked above.")
        charger_kw = c2.number_input("Charger power (kW)", 5.0, 600.0,
                                     float(cfg['chargerPower']), step=5.0)
        grid_kw = c3.number_input("Grid limit (kW)", 50.0, 10000.0,
                                  float(cfg['gridMaxPower']), step=50.0)

        c4, c5 = st.columns(2)
        demand_kw = c4.number_input(
            "Demand charge ($/kW-month)", 0.0, 200.0,
            float(cfg.get('demandChargePerKw', 0.0)), step=1.0,
            help="Set to zero to see what the plan looks like when only "
                 "energy is priced.")
        basis = c5.selectbox(
            "Energy basis", ['interval', 'point', 'fixed'],
            format_func=lambda m: {
                'interval': 'Model, upper 90% interval (robust)',
                'point': 'Model, point prediction',
                'fixed': 'Flat 2.5 kWh/mile',
            }[m])

        st.caption("Time-of-use energy rates, $/kWh")
        t1, t2, t3 = st.columns(3)
        peak = t1.number_input("Peak (12:00-18:00)", 0.0, 5.0,
                               float(TARIFF['peak']), step=0.01, format="%.5f")
        partial = t2.number_input("Partial", 0.0, 5.0,
                                  float(TARIFF['partial']), step=0.01, format="%.5f")
        offpeak = t3.number_input("Off-peak", 0.0, 5.0,
                                  float(TARIFF['offpeak']), step=0.01, format="%.5f")

    return {
        'extra_chargers': int(extra),
        'chargerPower': charger_kw,
        'gridMaxPower': grid_kw,
        'demandChargePerKw': demand_kw,
        'consumption_mode': basis,
        'tariff': {'peak': peak, 'partial': partial, 'offpeak': offpeak},
    }


def record_run(summary):
    """Keep each solve so scenarios can be compared rather than remembered."""
    if not summary:
        return
    history = st.session_state.get('history') or []
    sc = summary['scenario']
    history.append({
        'Run': len(history) + 1,
        'Chargers': sc['chargers'],
        'Charger kW': round(float(sc['charger_kw'])),
        'Grid kW': round(float(sc['grid_kw'])),
        'Demand $/kW': round(float(sc['demand_per_kw']), 2),
        'Basis': sc['basis'],
        'Covered': f"{summary['covered']}/{summary['asked']}",
        'Peak kW': round(summary['optimized']['peak_kw']),
        'Monthly': round(summary['optimized']['monthly']),
        'vs unmanaged': f"{summary['monthly_saving_pct']:.0f}%",
    })
    st.session_state['history'] = history


def show_history():
    history = st.session_state.get('history') or []
    if len(history) < 2:
        return
    st.write("### Scenarios compared")
    st.caption("Every run this session. The depot you have is usually the first row.")
    st.dataframe(pd.DataFrame(history), hide_index=True, use_container_width=True)
    if st.button("Clear scenario history"):
        st.session_state['history'] = []
        st.rerun()



def demo_scenarios():
    """Saved runs that open instantly, for when a live five-minute solve is
    the wrong thing to do to a room."""
    ready = demo.available()
    if not ready:
        return

    st.write("### Start from a worked example")
    st.caption(
        "Saved runs on a fixed six-bus depot. They open instantly and are the "
        "same every time; the live solver stops on a tolerance, so it is not. "
        "Submit below to solve the real fleet."
    )
    columns = st.columns(len(ready))
    for column, spec in zip(columns, ready):
        with column:
            if st.button(spec['label'], use_container_width=True, key=f"demo_{spec['slug']}"):
                bundle = demo.load(spec['slug'])
                if not bundle:
                    st.warning("That saved run could not be read.")
                    continue
                st.session_state['results'] = bundle['results']
                st.session_state['startTimeNum'] = bundle['startTimeNum']
                st.session_state['buses'] = bundle['buses']
                st.session_state['blocks'] = bundle['blocks']
                st.session_state['chargers'] = bundle['chargers']
                st.session_state['summary'] = bundle['summary']
                st.session_state['artifacts'] = bundle['artifacts']
                record_run(bundle['summary'])
                st.rerun()
            st.caption(spec['blurb'])


def opt_form():

    keys = ['buses', 'blocks', 'chargers', 'results', 'startTimeNum', 'summary', 'history',
            'artifacts']
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None

    demo_scenarios()

    serving, charging, idle, offline, df = get_overview_df()

    if df is None or df.empty:
        st.error("No vehicle data available - the Supabase backend returned nothing.")
        return

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


        df = pd.read_csv('data_files/block_miles.csv', header=1, delimiter=';')
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

        # Offer every block. The optimizer decides which are worth running when
        # there are more blocks than buses to run them.
        blocks['Select'] = True
        
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
            chargers_df['Select'] = True
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

        scenario = scenario_controls()

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

            # init_routes rewrites the frame it is given, turning the block
            # clock times into quarter indices, so the display copies keep
            # their own.
            run_scenario = dict(scenario)
            run_scenario['numChargers'] = (len(selected_chargers)
                                           + run_scenario.pop('extra_chargers'))

            opt = ChargeOpt(selected_buses.copy(), selected_blocks.copy(),
                            selected_chargers.copy(), scenario=run_scenario)

            results, startTimeNum = opt.solve()
            record_run(opt.summary)

            st.toast("Complete")
            st.toast(results)
            
            # save results, selected buses, blocks, and chargers to session state
            st.session_state['results'] = results
            st.session_state['startTimeNum'] = startTimeNum
            st.session_state['summary'] = opt.summary
            st.session_state['artifacts'] = None
            st.session_state['buses'] = selected_buses
            st.session_state['blocks'] = selected_blocks
            st.session_state['chargers'] = selected_chargers





    # get df's from session state
    results = st.session_state['results']
    startTimeNum = st.session_state['startTimeNum']
    selected_buses = st.session_state['buses']
    selected_blocks = st.session_state['blocks']
    selected_chargers = st.session_state['chargers']

    show_results(selected_buses, selected_blocks, selected_chargers, results, startTimeNum,
                 st.session_state['summary'], st.session_state.get('artifacts'))


def show_savings(summary):
    """What the schedule is worth against charging on arrival."""
    if not summary:
        return

    opt = summary['optimized']
    base = summary['baseline']

    st.write("### What this schedule saves")
    st.caption(
        f"Against charge-on-arrival - every bus plugged in the moment it is "
        f"back on the yard, drawing rated power until full, on the same duties. "
        f"Demand charge taken at ${summary['demand_charge_per_kw']:.0f}/kW of "
        f"monthly peak. Block energy from the {summary.get('consumption', 'flat rate')}, "
        f"per bus."
    )

    a, b, c = st.columns(3)
    a.metric("Monthly bill", f"${opt['monthly']:,.0f}",
             f"-${summary['monthly_saving']:,.0f} ({summary['monthly_saving_pct']:.0f}%)",
             delta_color="inverse")
    b.metric("Peak demand", f"{opt['peak_kw']:,.0f} kW",
             f"{opt['peak_kw'] - base['peak_kw']:+,.0f} kW vs unmanaged",
             delta_color="inverse")
    c.metric("Rate paid", f"${opt['cost_per_kwh']:.3f}/kWh",
             f"{100 * (opt['cost_per_kwh'] / base['cost_per_kwh'] - 1):+.0f}% vs unmanaged"
             if base['cost_per_kwh'] else "",
             delta_color="inverse")

    st.dataframe(pd.DataFrame([
        {'': 'Charge on arrival',
         'Peak demand': f"{base['peak_kw']:,.0f} kW",
         'Energy bought': f"{base['energy_kwh']:,.0f} kWh",
         'Rate paid': f"${base['cost_per_kwh']:.3f}/kWh",
         'Energy cost/day': f"${base['energy_cost_day']:,.2f}",
         'Monthly bill': f"${base['monthly']:,.0f}"},
        {'': 'This schedule',
         'Peak demand': f"{opt['peak_kw']:,.0f} kW",
         'Energy bought': f"{opt['energy_kwh']:,.0f} kWh",
         'Rate paid': f"${opt['cost_per_kwh']:.3f}/kWh",
         'Energy cost/day': f"${opt['energy_cost_day']:,.2f}",
         'Monthly bill': f"${opt['monthly']:,.0f}"},
    ]), hide_index=True, use_container_width=True)

    if summary.get('proved'):
        st.caption(
            f"Solved to within {summary.get('gap', 0.03):.0%} of the best possible "
            f"plan, so the same scenario run twice can land a little apart."
        )
    else:
        st.caption(
            "Stopped at the time limit with the best plan found by then, so the "
            "same scenario run twice can land a little apart."
        )

    # Said plainly rather than left for someone to catch: the two rows do not
    # buy the same number of kWh, so the rate is the honest comparison.
    if base['energy_kwh'] > opt['energy_kwh'] * 1.02:
        st.caption(
            f"Charge-on-arrival fills every pack, so it buys "
            f"{base['energy_kwh'] - opt['energy_kwh']:,.0f} kWh more than the plan, "
            f"which only charges to its end-of-horizon target. Part of the gap is "
            f"that extra energy; the rate paid per kWh is what the time-of-use "
            f"shifting earns on its own."
        )


def show_results(selected_buses, selected_blocks, selected_chargers, results, startTimeNum,
                 summary=None, artifacts=None):
    """artifacts carries a pre-computed run's tables. A live solve leaves it
    None and the files written by the solver are read instead."""
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

        # The solver's settings are not exposed, so whatever it decided has to
        # be visible here rather than only in a toast that disappears.
        if not is_solved(results):
            st.error(results if results else "No schedule was produced.")
        elif is_partial(results):
            st.warning(results)
        else:
            st.success(results)

        if is_solved(results):
            show_savings(summary)
            show_history()

            if artifacts is not None:
                results_df = pd.Series(artifacts['results_row']).dropna()
            else:
                results_df = pd.read_csv(os.path.join(
                    os.getcwd(), 'chargeopt', 'outputs', 'results.csv')).iloc[-1]
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
            assignment_df = (artifacts['assignments'].copy() if artifacts is not None
                             else pd.read_csv(f'{path}/assignments_{filename}.csv'))
            raw_assignment_df = assignment_df.copy()
            coach_of = dict(enumerate(selected_buses.reset_index()['vehicle']))
            eb_max = float(results_df['ebMaxKwh'])

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


            # Rows are (time, bus) pairs, so slicing by position dropped an
            # uneven number of early hours from each bus.
            twodim_df = (artifacts['schedule'].copy() if artifacts is not None
                         else pd.read_csv(f'{path}/{filename}.csv'))
            twodim_df = twodim_df[twodim_df['time'] >= startTimeNum]

            show_schedule(twodim_df, raw_assignment_df, selected_blocks,
                          coach_of, eb_max)
