import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import math
import datetime
import sys
import yaml
from helpers import initGridPricing, initRoutes
import matlab.engine
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

#########################################
# Parameter Initialization
#########################################

# load config file
with open("config.yml", "r") as file:
    config = yaml.safe_load(file)

# load filename to save results to
filename = config["filename"]
# bus params
B = config["numBuses"]
eB_max = config["ebMaxKwh"]
eB_min = int(eB_max * .2)
eB_range = eB_max - eB_min

# charger params
numChargers = config["numChargers"]
pCB_ub = config["chargerPower"]
eff_CB = config["chargerEff"]

# main storage params
eM_max = config['emMaxKwh']
eM_min = int(eM_max * .2)
powerCM_ub = config['emChargePower']
powerDM_ub = config['emDischargePower']
eff_CM = config['emChargeEff']
eff_DM = config['emDischargeEff']

# powerbs
solarKWH = config['solarMaxPower']
gridKWH = config['gridMaxPower']

# time variables
D = 7
dt = 0.25
T = int(24 * (1 / dt) * D)

# routes setup
routes = config["routes"]
R = len(routes)

# Start a MATLAB engine session
eng = matlab.engine.start_matlab()

[departure, arrival, eRoute, report] = initRoutes(routes, D, eB_range, pCB_ub);
# for loop for tDep and tRet
tDep = np.zeros((R, D), dtype=int)
tRet = np.zeros((R, D), dtype=int)
for d in range(D):
    for r in range(R):
        # here we subtract one from the departure and arrival times
        # since the time is one less than the matlab time
        tDep[r, d] = int(departure[r] - 1 + d * 96)
        tRet[r, d] = int(arrival[r] - 1 + d * 96)

# creating tDay
tDay = np.zeros((D, 96))
for d in range(D):
    tDay[d, :] = np.arange(d * 96, (d + 1) * 96)

#########################################
# Input data generation
#########################################

# Generate Solar Generation Profile
season = 'summer'
mornings = ["sunny", "sunny", "sunny", "sunny", "sunny", "sunny", "sunny"]
noons = ["sunny", "sunny", "sunny", "sunny", "sunny", "sunny", "sunny"]
nights = ["sunny", "sunny", "sunny", "sunny", "sunny", "sunny", "sunny"]
solarPowAvail = solarKWH * np.array(eng.initSolarPowModel(season, D, mornings, noons, nights))
solarPowAvail = solarPowAvail.reshape(T)

# Generate Grid Availability Profile
gridPowAvail = np.array(eng.initGridAvailability('gridAvailData.xlsx', D))
gridPowAvail = 500 * gridPowAvail.reshape(T)

# Generate Grid Pricing Profile
gridPowPrice = np.array(eng.initGridPricingModel(D))
gridPowPrice = gridPowPrice.reshape(T)

# Close the MATLAB engine session
eng.quit()

# Create a new model
m = gp.Model("Charge opt")
m.setParam('solver', 'gurobi')

#########################################
# Defining Decision Vars
#########################################
# Main Storage
eM = m.addVars(T, lb=eM_min, ub=eM_max, vtype=gp.GRB.CONTINUOUS, name="eM")
solarPowToM = m.addVars(T, lb=0, ub=solarKWH, vtype=gp.GRB.CONTINUOUS, name="solarPowToM")
gridPowToM = m.addVars(T, lb=0, ub=gridKWH, vtype=gp.GRB.CONTINUOUS, name="gridPowToM")
powerCM = m.addVars(T, lb=0, ub=powerCM_ub, vtype=gp.GRB.CONTINUOUS, name="powerCM")
powerDM = m.addVars(T, lb=0, ub=powerDM_ub, vtype=gp.GRB.CONTINUOUS, name="powerDM")

# Buses
powerCB = m.addVars(B, T, lb=0, ub=pCB_ub, vtype=gp.GRB.CONTINUOUS, name="powerCB")
solarPowToB = m.addVars(B, T, lb=0, ub=solarKWH, vtype=gp.GRB.CONTINUOUS, name="solarPowToB")
gridPowToB = m.addVars(B, T, lb=0, ub=gridKWH, vtype=gp.GRB.CONTINUOUS, name="gridPowToB")
mainPowToB = m.addVars(B, T, lb=0, ub=powerCM_ub, vtype=gp.GRB.CONTINUOUS, name="mainPowToB")
eB = m.addVars(B, T, lb=eB_min, ub=eB_max, vtype=gp.GRB.CONTINUOUS, name="eB")

# Charging activities
chargerUse = m.addVars(B, T, vtype=gp.GRB.BINARY, name="chargerUse")
T1 = m.addVars(B, T, vtype=gp.GRB.BINARY, name="T1")
T2 = m.addVars(B, T, vtype=gp.GRB.BINARY, name="T2")
Change = m.addVars(B, T, vtype=gp.GRB.BINARY, name="Change")
charging = m.addVars(B, D, vtype=gp.GRB.BINARY, name="charging")
assignment = m.addVars(B, D, R, vtype=gp.GRB.BINARY, name="assignment")

if config['runType'] == 'static':
    # making the model static
    m.addConstrs(assignment[b, d, b] == 1 for b in range(B) for d in range(D))
elif config['runType'] != 'dynamic':
    print("Invalid run type. Choose either static or dynamic ")
    sys.exit()

busLevel = 0.66
reserveLevel = 1

m.update()
#####################################
# Constraints
#####################################

#####################################
# Charging Constraints
#####################################
m.addConstrs((Change[b, t] == T1[b, t] + T2[b, t] for b in range(B) for t in range(T)), "Change link")

m.addConstrs((T1[b, 0] == 0 for b in range(B)), "T1 init")
m.addConstrs((T2[b, 0] == 0 for b in range(B)), "T2 init")

m.addConstrs((T1[b, t] - T2[b, t] == chargerUse[b, t] - chargerUse[b, t - 1] for b in range(B) for t in range(1, T)),
             "t chargeruse link 1")
m.addConstrs((Change[b, t] <= chargerUse[b, t - 1] + chargerUse[b, t] for b in range(B) for t in range(1, T)),
             "t chargeruse link 2")
m.addConstrs((Change[b, t] <= 2 - chargerUse[b, t - 1] - chargerUse[b, t] for b in range(B) for t in range(1, T)),
             "change chargeruse link")

m.addConstrs(sum(Change[b, t] for t in tDay[d]) <= 2 for b in range(B) for d in range(D))
m.addConstrs(sum(chargerUse[b, t] for t in tDay[d]) >= 6 * charging[b, d] for b in range(B) for d in range(D))
m.addConstrs(sum(chargerUse[b, t] for t in tDay[d]) <= 96 * charging[b, d] for b in range(B) for d in range(D))

# add constraint for powerCB
m.addConstrs(
    (powerCB[b, t] == (solarPowToB[b, t] + gridPowToB[b, t] + mainPowToB[b, t]) for t in range(T) for b in range(B)),
    "charger power limit")

# add constraints to connect charger use to charger power
m.addConstrs(powerCB[b, t] <= pCB_ub * chargerUse[b, t] for b in range(B) for t in range(T))
m.addConstrs(sum(chargerUse[b, t] for b in range(B)) <= numChargers for t in range(T))

#####################################
# Power Availability
#####################################
# Grid Constraints
m.addConstrs((gridPowToB.sum('*', t) + gridPowToM[t] <= gridPowAvail[t] for t in range(T)), "grid power total")

# Solar Power Constraints
m.addConstrs((solarPowToB.sum('*', t) + solarPowToM[t] <= solarPowAvail[t] for t in range(T)), "solar power total")

#####################################
# Main Storage Constraints
#####################################
m.addConstrs(powerCM[t] == (solarPowToM[t] + gridPowToM[t]) for t in range(T))
m.addConstrs(powerDM[t] == mainPowToB.sum('*', t) for t in range(T))
m.addConstrs(eM[t + 1] == eM[t] + dt * (eff_CM * powerCM[t] - (1 / eff_DM) * powerDM[t]) for t in range(T - 1))

m.addConstr(eM[0] == eM_max * reserveLevel)
m.addConstr(eM[T - 1] >= eM_max * reserveLevel)

#####################################
# Bus Battery operation
#####################################
# add constraints for route depletion
for b in range(B):
    for d in range(D):
        for i in range(96):
            routeDepletion = 0
            if not (d == 0 and i == 0):
                t = tDay[d][i]
                for r in range(R):
                    if t == tRet[r][d]:
                        routeDepletion += eRoute[r] * assignment[b, d, r]
                m.addConstr(eB[b, t] == eB[b, t - 1] + dt * powerCB[b, t - 1] * eff_CB - routeDepletion)

# add constraints for route requirement
for b in range(B):
    for d in range(D):
        for i in range(96):
            t = tDay[d][i]
            routeRequirement = 0
            for r in range(R):
                if t == tDep[r][d]:
                    routeRequirement += eRoute[r] * assignment[b, d, r]
            m.addConstr(eB[b, t] >= eB_min + routeRequirement)

# add constraints for initial and final state of battery energy
m.addConstrs(eB[b, 0] == eB_max * busLevel for b in range(B))
m.addConstrs(eB[b, T - 1] == eB_max * busLevel for b in range(B))

#####################################
# Route Coverage Constraints
#####################################
for b in range(B):
    for d in range(D):
        for r in range(R):
            for t in range(tDep[r][d], tRet[r][d] + 1):
                m.addConstr(chargerUse[b, t] + assignment[b, d, r] <= 1)

m.addConstrs(assignment.sum('*', d, r) == 1 for r in range(R) for d in range(D))
m.addConstrs(assignment.sum(b, d, '*') <= 1 for b in range(B) for d in range(D))

###################################
# Setting Objective and Solving
###################################
sums_over_buses = [sum(gridPowToB[b, t] for b in range(B)) + gridPowToM[t] for t in range(T)]

# Convert the list to a numpy array and multiply it element-wise with gridPowPrice
obj_coeffs = np.array(sums_over_buses)
obj_vals = obj_coeffs * gridPowPrice

# Create a LinExpr object from the array using the quicksum method
obj_expr = 0.25 * gp.quicksum(obj_vals)
m.setObjective(obj_expr, gp.GRB.MINIMIZE)

# Set the objective gap to 0.5% (only for flexibility tests)
m.setParam('MIPGap', 0.005)

# Solve the model
m.optimize()

#####################################
# Exporting Results
#####################################

# Checking if it is feasible
if m.status != gp.GRB.INFEASIBLE:

    # create a dictionary of variable names and values
    variable_dict = {var.VarName: var.x for var in m.getVars()}

    # one dimensional
    eM_df = pd.DataFrame({'time': range(T), 'eM': [variable_dict[f'eM[{i}]'] for i in range(T)]}).set_index(['time'])
    solarpowtoM_df = pd.DataFrame(
        {'time': range(T), 'solarpowtoM': [variable_dict[f'solarPowToM[{i}]'] for i in range(T)]}).set_index(['time'])
    gridpowtom_df = pd.DataFrame(
        {'time': range(T), 'gridpowtom': [variable_dict[f'gridPowToM[{i}]'] for i in range(T)]}).set_index(['time'])
    powerCM_df = pd.DataFrame(
        {'time': range(T), 'powerCM': [variable_dict[f'powerCM[{i}]'] for i in range(T)]}).set_index(
        ['time'])
    powerDM_df = pd.DataFrame(
        {'time': range(T), 'powerDM': [variable_dict[f'powerDM[{i}]'] for i in range(T)]}).set_index(
        ['time'])

    onedim_df = pd.concat([eM_df, solarpowtoM_df, gridpowtom_df, powerCM_df, powerDM_df], axis=1)


    # two-dimensional
    def genDF(varName):
        df = pd.DataFrame(columns=['time', 'bus', 'value'])
        data = []

        for t in range(T):
            for b in range(B):
                value = variable_dict[f'{varName}[{b},{t}]']
                data.append({'time': t, 'bus': b, f'{varName}': value})

        df = pd.DataFrame(data)
        df = df.set_index(['bus', 'time'])

        return df


    powerCB_df = genDF('powerCB')
    solarpowtoB_df = genDF('solarPowToB')
    gridpowtoB_df = genDF('gridPowToB')
    mainpowtoB_df = genDF('mainPowToB')
    eB_df = genDF('eB')

    dfs = [powerCB_df, solarpowtoB_df, gridpowtoB_df, mainpowtoB_df, eB_df]
    twodim_df = pd.concat(dfs, axis=1, join='inner')

    onedim_df.to_csv(f'outputs/1d_{filename}.csv')
    twodim_df.to_csv(f'outputs/2d_{filename}.csv')

    ## Gen assignments
    data = []
    varName = 'assignment'
    for d in range(D):
        for b in range(B):
            for r in range(R):
                value = variable_dict[f'{varName}[{b},{d},{r}]']
                data.append({'day': d, 'bus': b, 'route': r, f'{varName}': value})

    assignment_df = pd.DataFrame(data)
    assignment_df = assignment_df.set_index(['bus', 'day', 'route'])
    assignment_df.to_csv(f'outputs/assignments_{filename}.csv')

    # create the results DataFrame
    results_df = pd.DataFrame(columns=["case_name", "numBuses", "ebMaxKwh", "numChargers", "chargerPower", "chargerEff",
                                       "routes", "emMaxKwh", "emChargePower", "emDischargePower", "emChargeEff",
                                       "emDischargeEff", "solarMaxPower", "gridMaxPower", "obj_val", "sol_time", "date",
                                       "type"])
    results_file = 'results.csv'

    # try to read in the current results file (if it exists)
    try:
        current_results = pd.read_csv(results_file)
        results_df = pd.concat([current_results, results_df], ignore_index=True)
    except FileNotFoundError:
        pass

    # get the objective value and solution time
    obj_val = m.objVal
    sol_time = m.Runtime

    # get current date in month/day/year format
    current_date = datetime.datetime.now().strftime("%m/%d/%Y")

    # append the results to the DataFrame
    results_df = results_df.append(
        {
            "case_name": filename,
            "numBuses": B,
            "ebMaxKwh": eB_max,
            "numChargers": numChargers,
            "chargerPower": pCB_ub,
            "chargerEff": eff_CB,
            "routes": str(routes),
            "emMaxKwh": eM_max,
            "emChargePower": powerCM_ub,
            "emDischargePower": powerDM_ub,
            "emChargeEff": eff_CM,
            "emDischargeEff": eff_DM,
            "solarMaxPower": solarKWH,
            "gridMaxPower": gridKWH,
            "obj_val": obj_val,
            "sol_time": sol_time,
            "date": current_date,
            "type": config['runType']
        },
        ignore_index=True,
    )

    # write the results to the results.csv file
    results_df.to_csv(results_file, index=False)
# TODO: clean up and add visualization scripts to folder
