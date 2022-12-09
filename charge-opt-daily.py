import gurobipy as gp
from gurobipy import GRB
import numpy as np
from gridPowPrice import initGridPricingModel
from routes import initRoutesDynamically
import pandas as pd

# gp.reset()
def solve_charge_daily(dataframe):
    model = gp.Model('chargeopt')
    #############
    # params
    #############
    D = 1
    T = 24*D*4
    dt = .25
    time = [15*(t+1)/60 for t in range(T)]

    B = 10 # get from df
    numChargers = 5

    eB_max = 440
    eB_min = 440*.2

    pCB = 50
    pCB_min = 50
    eff_CB = .94

    # eM_max = 1000
    # eM_min = 200

    # pCM_max = 500
    # pDM_max = 500
    # eff_CM = .90
    # eff_DM = .90

    routes = [7771, 7772, 7072,7773, 7774]

    R = len(routes)

    eB_range = eB_max - eB_min

    [departure, arrival, eRoute, report] = initRoutesDynamically(routes, D, eB_range, pCB_min)

    tDep = np.zeros((R, D))
    tRet = np.zeros((R, D))

    for d in range(D):
        for r in range(1,R+1):
            tDep[r-1][d] = departure[r-1]+(d)*96
            tRet[r-1][d] = arrival[r-1]+(d)*96

    tDay = np.zeros((D, 96))
    for d in range(D):
        tDay[d][:] = range(d*96,(d+1)*96)

    # solarPowAvail = 250*initSolarPowModel(season, D, mornings, noons, nights)
    solarPowAvail = 250

    # Generate Grid Availability Profile
    # gridPowAvail = 500*initGridAvailability('gridAvailData.xlsx', D)
    gridPowAvail = 500

    # Generate Grid Pricing Profile
    gridPowPrice = initGridPricingModel(D)

    # Mathematical Model 

    # Decision Variables
    # eM = model.addVars(1, T, vtype=GRB.CONTINUOUS, name="eM")
    # solarPowToM = model.addVars(1, T, vtype=GRB.CONTINUOUS, name="solarPowToM")
    # gridPowToM = model.addVars(1, T, vtype=GRB.CONTINUOUS, name="gridPowToM")
    solarPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="solarPowToB")
    gridPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="gridPowToB")
    # mainPowToB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="mainPowToB")
    chargerUse = model.addVars(B, T, vtype=GRB.BINARY, name="chargerUse")
    assignment = model.addVars(B, D, R, vtype=GRB.BINARY, name="assignment")
    powerCB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="powerCB")
    powerCM = model.addVars(1, T, vtype=GRB.CONTINUOUS, name="powerCM")
    powerDM = model.addVars(1, T, vtype=GRB.CONTINUOUS, name="powerDM")
    eB = model.addVars(B, T, vtype=GRB.CONTINUOUS, name="eB")
     # charging activities
    T_one = model.addVars(B, T, vtype=GRB.BINARY, name="t1")
    T_two = model.addVars(B, T, vtype=GRB.BINARY, name="t2")
    Change = model.addVars(B, T, vtype=GRB.BINARY, name="change")
    charging = model.addVars(B, D, vtype=GRB.BINARY, name="charging")

    # Update model to incorporate new variables
    model.update()

    busLevel = 0.66
    reserveLevel = 1
        
    for t in range(T):
        for b in range(B):
            if t == 1:
                model.addConstr(T_one[b,t] == 0)
                model.addConstr(T_two[b,t] == 0)
            else:
                if t >= 1:
                    model.addConstr(T_one[b,t] - T_two[b,t] - chargerUse[b,t] + chargerUse[b,t-1] == 0)
                    model.addConstr(Change[b,t] <= chargerUse[b,t-1] + chargerUse[b,t])
                    model.addConstr(Change[b,t] <= 2 - chargerUse[b,t-1] - chargerUse[b,t])

    for b in range(B):
        for d in range(D):
            model.addConstr(gp.quicksum([Change[b,t] for t in range(95)]) <= 2.0)
            model.addConstr(gp.quicksum([chargerUse[b,t] for t in range(95)]) >= 6*charging[b,d])
            model.addConstr(gp.quicksum([chargerUse[b,t] for t in range(95)]) <= 96*charging[b,d])

    # Constraints
    ## power availability
    gridPowTotal = gp.quicksum(gridPowToB)
    # + gridPowToM
    model.addConstr(0 <= gp.quicksum(gridPowToB))
    model.addConstr(gp.quicksum(gridPowToB) <= gridPowAvail)
    # Solar Power Constraints
    solarPowTotal = gp.quicksum(solarPowToB['*', t] for t in range(T))
    # + solarPowToM
    model.addConstr(solarPowTotal <= solarPowAvail)
    model.addConstr(0 <= solarPowTotal)
    # # Main Storage Constraints
    # model.addConstr(powerCM == (solarPowToM + gridPowToM))
    # model.addConstr(powerDM ==  np.sum(mainPowToB,1))

    # for t in range(1, T):
    #     model.addConstr(eM[t+1] == eM[t] + dt * (eff_CM * powerCM[t] - (1/eff_DM) * powerDM[t]))

    # model.addConstr(eM_min <= eM <= eM_max)
    # model.addConstr(eM[1] == eM_max * reserveLevel)
    # model.addConstr(eM[T] >= eM_max * reserveLevel)
    # model.addConstr(0 <= powerCM <= pCM_max)
    # model.addConstr(0 <= powerDM <= pDM_max)

    # Bus Battery Operation

    for b in range(1, B):
        for d in range(D):
            for i in range(1, 97):
                routeDepletion = 0
                if not (d == 1 and i == 1):
                    t = tDay[d][i]
                    for r in range(1, R+1):
                        if t == tRet[r][d]: # if the route is returning at this time
                            routeDepletion = routeDepletion + eRoute[r] * assignment[b][d][r]
                    model.addConstr(eB[b][t] == eB[b][t-1] + dt * powerCB[b][t-1] * eff_CB - routeDepletion)

    for b in range(B):
        for d in range(D):
            for i in range(1, 97):
                t = tDay[d][i]
                routeRequirement = 0
                for r in range(1, R+1):
                    if t == tDep[r][d]:
                        routeRequirement = eRoute[r] * assignment[b][d][r] + routeRequirement
                model.addConstr(eB(b,t) >=  eB_min + routeRequirement)

    model.addConstr(solarPowToB + gridPowToB)
    # +  mainPowToB)


    model.addConstr(eB_min <= eB <= eB_max)

    for t in range(T):
        for b in range(B):
            model.addConstr(0 <= powerCB[b,t]) 
            model.addConstr(powerCB[b,t] <= pCB*chargerUse[b,t])


    model.addConstr(eB[:,0] == eB_max*busLevel)
    model.addConstr(eB[:,T-1] == eB_max*busLevel)

    # Charging Constraints
    for t in range(T):
        model.addConstr(np.sum(chargerUse[:,t], 1) <= numChargers)

    # Route Coverage Constraints
    for d in range(D):
        for r in range(R):
            model.addConstr(np.sum(assignment[:,d,r], 1) == 1)

    for b in range(B):
        for d in range(D):
            for r in range(R):
                for t in range(tDep[r,d], tRet[r,d]):
                    model.addConstr(chargerUse[b,t] + assignment[b,d,r] <= 1)

    for b in range(B):
        for d in range(D):
            model.addConstr(np.sum(assignment[b,d,:]) <= 1)

    # Non Negativity Constraints
    # model.addConstr(mainPowToB >= 0)
    # model.addConstr(gridPowToM >= 0)
    # model.addConstr(solarPowToM >= 0)
    # model.addConstr(eM >= 0)

    model.addConstr(gridPowToB >= 0)
    model.addConstr(solarPowToB >= 0)
    model.addConstr(eB >= 0)

    # Objective Function to Minimize Operational Costs
    cost = .25 * gridPowTotal * np.transpose(gridPowPrice)

solve_charge_daily(pd.DataFrame())