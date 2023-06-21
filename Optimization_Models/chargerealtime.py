import pandas as pd
from operationalGraph import operationalGraph
import gurobipy as gp
from gurobipy import GRB
import numpy as np
from gridPowPrice import initGridPricingModel
from routes import initRoutesDynamically
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import math
import warnings
import matplotlib.pyplot as plt
warnings.simplefilter(action='ignore', category=FutureWarning)

def chargeRealtime(buses):
    ###########################################
    # Setting up Model
    ###########################################
    model = gp.Model('chargeopt')
    # st.write(buses)
    ###########################################
    # Params
    ###########################################
    # number of days
    D = 2
    # numer of timesteps in a day
    _d = 24 * 4
    # length of timestep in hours
    dt = .25

    assignment_day = [1]  # days we assign buses
    initial_day = [0]  # days when assignments have already been made

    start_time = 18 * 4  # 6 pm
    end_time = start_time + _d - 1  # 5:45pm next day
    T = end_time - start_time + 1

    # B = len(buses)
    B = buses.shape[0] # get from df
    numChargers = 5
    eB_max = 440
    eB_min = 440 * .2
    pCB = 50
    eff_CB = .94

    routes = [7771, 7772, 7072, 7773, 7774]
    R = len(routes)
    eB_range = eB_max - eB_min
    [departure, arrival, eRoute, report] = initRoutesDynamically(routes, D, eB_range, pCB)

    tDep = np.zeros((R, D))
    tRet = np.zeros((R, D))

    for d in range(D):
        for r in range(R):
            tDep[r][d] = departure[r] + (_d*d-start_time)
            tRet[r][d] = arrival[r] + (_d*d-start_time)

    solarPowAvail = 0
    gridPowAvail = 500
    # gridPowPrice = initGridPricingModel(D)
    gridPowPrice = 0.6

    ###########################################
    # Variables
    ###########################################

    solarPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="solarPowToB")
    gridPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="gridPowToB")
    chargerUse = model.addVars(B, T, vtype=GRB.BINARY, name="chargerUse")
    assignment = model.addVars(B, D, R, vtype=GRB.BINARY, name="assignment")
    powerCB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="powerCB")
    eB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="eB")
    T_one = model.addVars(B, T, vtype=GRB.BINARY, name="t1")
    T_two = model.addVars(B, T, vtype=GRB.BINARY, name="t2")
    Change = model.addVars(B, T, vtype=GRB.BINARY, name="change")
    charging = model.addVars(B, D, vtype=GRB.BINARY, name="charging")
    prob = model.addVars(B, vtype=GRB.CONTINUOUS, name="prob")

    ###########################################
    # Constraints
    ###########################################


    model.addConstrs(Change[b,t] == T_one[b,t] + T_two[b,t] for b in range(B) for t in range(T))
    # Charging Activities
    for t in range(T):
        for b in range(B):
            if t == 0:
                model.addConstr(T_one[b, t] == 0)
                model.addConstr(T_two[b, t] == 0)
            else:
                model.addConstr(T_one[b, t] - T_two[b, t] - chargerUse[b, t] + chargerUse[b, t - 1] == 0)
                model.addConstr(Change[b, t] <= chargerUse[b, t - 1] + chargerUse[b, t])
                model.addConstr(Change[b, t] <= 2 - chargerUse[b, t - 1] - chargerUse[b, t])

    model.addConstrs(Change.sum(b, '*') <= 2.0 for b in range(B))

    # probablilities
    # define the prob
    # set the prob threshold
    # remove other constraint (for assignments on the second day)
    for t in range(T):
        d = 0 if math.floor(t / (_d-start_time)) == 0 else 1
        for b in range(B):
            model.addConstr(chargerUse[b, t] <= _d * charging[b, d])


    model.addConstrs(chargerUse.sum(b, '*') >= 2 * charging.sum(b, '*') for b in range(B))

    # grid and solar power
    model.addConstrs(gridPowToB.sum('*', t) <= gridPowAvail for t in range(T))
    model.addConstrs(solarPowToB.sum('*', t) <= solarPowAvail for t in range(T))

    # charging power
    model.addConstrs(powerCB[b, t] == solarPowToB[b, t] + gridPowToB[b, t] for b in range(B) for t in range(T))
    model.addConstrs(powerCB[b, t] <= pCB * chargerUse[b, t] for t in range(T) for b in range(B))
    model.addConstrs(chargerUse.sum('*', t) <= numChargers for t in range(T))

    # assignments
    # on assignment day, every bus is assigned a route
    model.addConstrs(assignment.sum(b, d, '*') == 1 for d in assignment_day for b in range(B))
    # on assignment day, every route has at most one bus assigned to it
    model.addConstrs(assignment.sum('*', d, r) <= 1 for d in assignment_day for r in range(R))
    # on initial day there are no assignments
    model.addConstrs(assignment[b, d, r] == 0 for b in range(B) for d in initial_day for r in range(R))

    # Bus Battery Operation
    for b in range(B):
        for t in range(1, T-1):
            d = 0 if math.floor(t / (_d-start_time)) == 0 else 1
            routeDepletion = 0
            # if the route is returning at this time
            for r in range(R):
                if t == tRet[r, d]:
                    routeDepletion += gp.quicksum(eRoute[r] * assignment[b, d, r])
            model.addConstr(eB[b, t] == eB[b, t-1] + dt * powerCB[b, t-1] * eff_CB - routeDepletion)

    # route constraints
    model.addConstrs(eB[b, t] >= eB_min for b in range(B) for t in range(T))

    for b in range(B):
        for t in range(T):
            d = 0 if math.floor(t / (_d-start_time)) == 0 else 1
            routeRequirement = 0
            for r in range(R):
                # if the route is departing at this time on this day
                if t == tDep[r, d]:
                    # add it to the route requirements
                    routeRequirement += gp.quicksum(eRoute[r] * assignment[b, d, r])
            model.addConstr(eB[b, t] >= eB_min + routeRequirement)

    # bus battery
    model.addConstrs(eB[b, 0] == 440*.6 for b in range(B))
    # model.addConstrs(eB[b, T-1] == 420 for b in range(B))

    model.addConstrs(eB_min <= eB[b, t] for b in range(B) for t in range(T))
    model.addConstrs(eB[b, t] <= eB_max for b in range(B) for t in range(T))

    # charging

    # for the duration of the route, no charging allowed
    for t in range(T):
        d = 0 if math.floor(t / (_d-start_time)) == 0 else 1
        for r in range(R):
            if t in range(int(tDep[r, d]), int(tRet[r, d])):
                model.addConstrs(chargerUse[b, t] + assignment[b, d, r] <= 1 for b in range(B))

    # Objective Function to Minimize Operational Costs
    # cost = .25 * gp.quicksum(gridPowToB) * gp.quicksum(gridPowPrice)
    cost = .25 * gp.quicksum(gridPowToB) * gridPowPrice

    model.setObjective(cost, GRB.MINIMIZE)
    model.optimize()

    # Iterate over the list of variables
    data = pd.DataFrame(columns=['Block', 'Day', 'Coach'])

    for v in assignment.values():
        if v.x == 1:
            dat = v.VarName.split('[')[1]
            dat = dat.replace(']', '')
            dat = dat.split(',')
            row = {"Coach": dat[0], "Day": dat[1], "Block": dat[2]}
            data = data.append(row, ignore_index=True)

    current_time = datetime.now().strftime('%m/%d')
    tommorow = (datetime.now() + timedelta(days=1)).strftime('%m/%d')
    data.Coach = data.Coach.astype(int)
    data = data.replace(({
        'Block': {str(k):str(v) for k, v in enumerate(routes)},
        "Coach": buses.reset_index()[['Vehicle']].to_dict()['Vehicle'],
        'Day': {'0':current_time, '1':tommorow},
                          }))

    st.dataframe(data[['Block', 'Coach']], use_container_width=True)

    eB_values = []
    for b in range(B):
        eB_values.append([eB[b, t].x for t in range(T)])

    # Create a figure with a subplot for each element b in B
    fig, axs = plt.subplots(B, 1, sharex=True)

    # Plot the values of eB for each element b in B
    for i, b in enumerate(range(B)):
        axs[i].plot(range(T), eB_values[i])
        axs[i].set_ylabel(f"eB[{b}]")
        axs[i].set_ylim((0,440))

    # Set the x-axis label and show the plot
    plt.xlabel("Time period (t)")
    st.pyplot(fig)

    realtime_data = {}
    realtime_data['B'] = B
    charger_use_values = np.zeros((B,T))
    for b in range(B):
        charger_use_values[b, :] = [chargerUse[b,t].x for t in range(T)]

    realtime_data['cu'] = charger_use_values

    def get_tomorrow():
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        return tomorrow.strftime('%m/%d')

    data = data[data.Day == get_tomorrow()] # TODO: replaced with tomorows data
    a_matrix = np.zeros((B, 1))

    data_matrix = data.melt(id_vars=['Coach', 'Day'], value_vars=['Block'])
    data_matrix.Coach = data_matrix.Coach.astype(int)

    a_matrix[:, :]= data_matrix[['Coach', 'value']].set_index('Coach')
    realtime_data['A'] = a_matrix

    operationalGraph(realtime_data, start_time, end_time)
