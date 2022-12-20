import gurobipy as gp
from gurobipy import GRB
import numpy as np
from gridPowPrice import initGridPricingModel
from routes import initRoutesDynamically
import pandas as pd
import math

def solve_charge_daily(dataframe):

    model = gp.Model('chargeopt')

    # number of days
    D = 2 
    # numer of timesteps in a day
    _d = 24*4
    # length of timestep in hours
    dt = .25

    assignment_day = [1]  # days we assign buses
    initial_day = [0] # days where assignments have already been made


    start_time = 17*4
    end_time = start_time+_d+1
    T = end_time-start_time+1
    time = [t for t in range(T)]

    B = 5 # get from df
    numChargers = 5
    eB_max = 440
    eB_min = 440*.8
    pCB = 50
    pCB_min = 50
    eff_CB = .94

    routes = [7771, 7772, 7072, 7773, 7774]
    R = len(routes)
    eB_range = eB_max - eB_min
    [departure, arrival, eRoute, report] = initRoutesDynamically(routes, D, eB_range, pCB_min)

    tDep = np.zeros((R, D))
    tRet = np.zeros((R, D))

    for d in range(D):
        for r in range(R):
            tDep[r-1][d] = departure[r-1]+(d)*_d
            tRet[r-1][d] = arrival[r-1]+(d)*_d

    
    tDay = np.zeros((D, 96))
    for d in range(D):
        # print(range((d)*96,(d+1)*96))
        tDay[d][:] = range((d)*96,(d+1)*96)

    tDay
    # solarPowAvail = 250*initSolarPowModel(season, D, mornings, noons, nights)
    solarPowAvail = 250
    # Generate Grid Availability Profile
    gridPowAvail = 500
    # Generate Grid Pricing Profile
    gridPowPrice = initGridPricingModel(D)
    

    # Decision Variables
    solarPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="solarPowToB")
    gridPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="gridPowToB")
    chargerUse = model.addVars(B, T, vtype=GRB.BINARY, name="chargerUse")
    assignment = model.addVars(B, D, R, vtype=GRB.BINARY, name="assignment")
    powerCB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="powerCB")
    eB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="eB")

     # charging activities
    T_one = model.addVars(B, T, vtype=GRB.BINARY, name="t1")
    T_two = model.addVars(B, T, vtype=GRB.BINARY, name="t2")
    Change = model.addVars(B, T, vtype=GRB.BINARY, name="change")
    charging = model.addVars(B, D, vtype=GRB.BINARY, name="charging")

    # print(eRoute[0][0])
    model.update()

    for t in time:
        for b in range(B):
            if t == start_time:
                model.addConstr(T_one[b,t] == 0)
                model.addConstr(T_two[b,t] == 0)
            else:
                if t >= start_time:
                    model.addConstr(T_one[b,t] - T_two[b,t] - chargerUse[b,t] + chargerUse[b,t-1] == 0)
                    model.addConstr(Change[b,t] <= chargerUse[b,t-1] + chargerUse[b,t])
                    model.addConstr(Change[b,t] <= 2 - chargerUse[b,t-1] - chargerUse[b,t])

    for b in range(B):
        for d in range(D):
            model.addConstr(gp.quicksum([Change[b,t] for t in time]) <= 2.0)
            model.addConstr(gp.quicksum([chargerUse[b,t] for t in time]) >= 6*charging[b,d])
            model.addConstr(gp.quicksum([chargerUse[b,t] for t in time]) <= _d*charging[b,d])

    # Constraints
    ## power availability
    gridPowTotal = gp.quicksum(gridPowToB)

    # + gridPowToM
    model.addConstr(0 <= gp.quicksum(gridPowToB))
    model.addConstr(gp.quicksum(gridPowToB) <= gridPowAvail)

    # Solar Power Constraints
    solarPowTotal = gp.quicksum([solarPowToB.sum('*', t) for t in range(T)])

    # solarPowToM
    model.addConstr(solarPowTotal <= solarPowAvail)
    model.addConstr(0 <= solarPowTotal)
    
    # # Bus Battery Operation
    # for b in range(B):
    #     for t in range(T):
    #         d = 0 if math.floor(t/96) == 0 else 1
    #         routeDepletion = 0
    #         if not (d == 0 and t == 1):
    #             for r in range(R):
    #                 if t == tRet[r][d]: # if the route is returning at this time
    #                     # print(routeDepletion)
    #                     # print(eRoute)
    #                     # print(assignment[b,d,r])
    #                     routeDepletion = routeDepletion + eRoute[r] * assignment[b,d,r]
    #             model.addConstr(eB[b,t+1] == eB[b,t] + dt * powerCB[b,t] * eff_CB - routeDepletion)

    # for b in range(B):
    #     for d in range(D):
    #         for i in range(_d):
    #             t = tDay[d][i]
    #             routeRequirement = 0
    #             for r in range(R):
    #                 if t == tDep[r,d]:
    #                     routeRequirement = eRoute[r] * assignment[b,d,r] + routeRequirement
    #             model.addConstr((eB[b,t] >=  eB_min + routeRequirement))

    # model.addConstr(solarPowToB + gridPowToB)
    model.addConstrs((eB_min <= eB[b,t] for b in range(B) for t in range(T)))
    model.addConstrs((eB[b,t] <= eB_max for b in range(B) for t in range(T)))

    for t in time:
        for b in range(B):
            model.addConstr(0 <= powerCB[b,t]) 
            model.addConstr(powerCB[b,t] <= pCB*chargerUse[b,t])


    # model.addConstr(eB[:,start_time] == input_socs)

    # Charging Constraints
    for t in range(T):
        model.addConstr(chargerUse.sum('*', t) <= numChargers)

    # Route Coverage Constraints
    for d in assignment_day:
        for r in range(R):
            model.addConstr(assignment.sum('*', d, r) == 1)

    model.addConstr(assignment.sum('*', initial_day, '*') == 0)

    # for b in range(B):
    #     for d in range(D):
    #         for r in range(R):
    #             for t in range(tDep[r,d], tRet[r,d]):
    #                 model.addConstr(chargerUse[b,t] + assignment[b,d,r] <= 1)

    for b in range(B):
        for d in range(D):
            model.addConstr(assignment.sum(b,d,'*') <= 1)

    model.addConstrs((gridPowToB[b,t] >= 0 for b in range(B) for t in range(T)))
    model.addConstrs((solarPowToB[b,t] >= 0 for b in range(B) for t in range(T)))

    # model.addConstr(eB.LB == 0)

    # Objective Function to Minimize Operational Costs
    cost = .25 * gridPowTotal * np.transpose(gridPowPrice)

solve_charge_daily(pd.DataFrame())