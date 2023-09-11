import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
from datetime import datetime
import yaml
from chargeopt.helpers import init_grid_pricing, init_routes, time_to_quarter
import os
import warnings
import streamlit as st
import sys

warnings.simplefilter(action='ignore', category=FutureWarning)

class ChargeOpt:
    def __init__(self, buses, routes, chargers):
        self.buses = buses
        self.routes = routes
        self.chargers = chargers
        self.startTime = datetime.now()

    def solve(self):

        #####################################
        # Init self variables
        #####################################
        # example buse
        # [{coach}]
        B = len(self.buses)

        routes = self.routes
        R = len(routes)

        #####################################
        # Config 
        #####################################
        # load config file
        config_path = os.path.join(os.getcwd(), "chargeopt/config.yml")
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

        # make filename based on date
        current_datetime = datetime.now().strftime("%m-%d-%Y_%H-%M-%S")
        filename = f'chargeopt_{current_datetime}'

        eB_max = config["ebMaxKwh"]
        eB_min = int(eB_max * .2)
        eB_range = eB_max - eB_min

        # charger params
        numChargers = len(self.chargers)
        pCB_ub = config["chargerPower"]

        # power
        gridKWH = config['gridMaxPower']

        # time variables
        D = 3
        dt = 0.25
        startTimeNum = time_to_quarter(self.startTime.strftime('%I:%M %p'))
        # TODO: Fix time so there is a start time and end time
        T = D * 96
        optimized_time = [t for t in range(startTimeNum, T)]
        print(T)
                
        #####################################
        # Init MATLAB engine for setup
        #####################################
        # Start a MATLAB engine session

        [departure, arrival, eRoute, report] = init_routes(routes, eB_range, pCB_ub);
        if report != 'All Clear':
            return None
            sys.exit(report)

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
        gridPowAvail = gridKWH

        # Generate Grid Pricing Profile
        gridPowPrice = init_grid_pricing(D)

        # Create a new model
        m = gp.Model("Charge opt")
        m.setParam('solver', 'gurobi')

        #########################################
        # Defining Decision Vars
        #########################################
      
        # Buses
        powerCB = m.addVars(B, T, lb=0, ub=pCB_ub, vtype=gp.GRB.CONTINUOUS, name="powerCB")
        gridPowToB = m.addVars(B, T, lb=0, ub=gridKWH, vtype=gp.GRB.CONTINUOUS, name="gridPowToB")
        eB = m.addVars(B, T, lb=eB_min, ub=eB_max, vtype=gp.GRB.CONTINUOUS, name="eB")

        # Charging activities
        chargerUse = m.addVars(B, T, vtype=gp.GRB.BINARY, name="chargerUse")
        T1 = m.addVars(B, T, vtype=gp.GRB.BINARY, name="T1")
        T2 = m.addVars(B, T, vtype=gp.GRB.BINARY, name="T2")
        change = m.addVars(B, T, vtype=gp.GRB.BINARY, name="change")
        charging = m.addVars(B, D, vtype=gp.GRB.BINARY, name="charging")
        tracker = m.addVars(B, T, vtype=gp.GRB.BINARY, name="tracker")
        tracker_b = m.addVars(B, T, vtype=gp.GRB.BINARY, name="tracker_b")
        assignment = m.addVars(B, D, R, vtype=gp.GRB.BINARY, name="assignment")
        m.update()

        #####################################
        # Constraints
        #####################################

        #####################################
        # Charging Constraints
        #####################################
        m.addConstrs((change[b, t] == T1[b, t] + T2[b, t] for b in range(B) for t in range(T)), "change link")

        m.addConstrs((T1[b, t] == 0 for b in range(B) for t in range(startTimeNum)), "T1 init")
        m.addConstrs((T2[b, t] == 0 for b in range(B) for t in range(startTimeNum)), "T2 init")

        m.addConstrs((T1[b, t] - T2[b, t] == chargerUse[b, t] - chargerUse[b, t - 1] for b in range(B) for t in range(1, T)),
                    "t chargeruse link 1")
        m.addConstrs((change[b, t] <= chargerUse[b, t - 1] + chargerUse[b, t] for b in range(B) for t in range(1, T)),
                    "t chargeruse link 2")
        m.addConstrs((change[b, t] <= 2 - chargerUse[b, t - 1] - chargerUse[b, t] for b in range(B) for t in range(1, T)),
                    "change chargeruse link")
        
        m.addConstrs(sum(change[b, t] for t in range(T)) <= 2 for b in range(B))
        m.addConstrs(sum(chargerUse[b, t] for t in tDay[d]) >= 6 * charging[b, d] for b in range(B) for d in range(D))
        m.addConstrs(sum(chargerUse[b, t] for t in tDay[d]) <= 96 * charging[b, d] for b in range(B) for d in range(D))

        # add constraint for powerCB
        m.addConstrs((powerCB[b, t] == (gridPowToB[b, t]) for t in range(T) for b in range(B)),
            "charger power limit")

        # add constraints to connect charger use to charger power
        m.addConstrs(powerCB[b, t] <= pCB_ub * chargerUse[b, t] for b in range(B) for t in range(T))
        m.addConstrs(powerCB[b, t] >= chargerUse[b, t] for b in range(B) for t in range(T))
        m.addConstrs(sum(chargerUse[b, t] for b in range(B)) <= numChargers for t in range(T))

        #####################################
        # Power Availability
        #####################################
        # Grid Constraints
        m.addConstrs((gridPowToB.sum('*', t) <= gridPowAvail for t in range(T)), "grid power total")

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
                        m.addConstr(eB[b, t] == eB[b, t - 1] + dt * powerCB[b, t - 1] - routeDepletion)

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
        for b in range(B):
            soc = self.buses.iloc[b, 1]
            print(soc)
            # remove % and convert to float
            soc = soc.replace('%', '')
            soc = float(soc) / 100
            m.addConstrs(eB[b, t] == eB_max * soc for t in range(startTimeNum))
            m.addConstrs(eB[b, t] == eB_max * soc for t in range(startTimeNum))

        m.addConstrs(eB[b, T - 1] >= eB_max * soc for b in range(B))

        #####################################
        # Route Coverage Constraints
        #####################################
        for b in range(B):
            for d in range(D):
                for r in range(R):
                    for t in range(tDep[r][d], tRet[r][d] + 1):
                        m.addConstr(chargerUse[b, t] + assignment[b, d, r] <= 1)

        m.addConstrs(assignment.sum('*', d, r) == 1 for r in range(R) for d in range(1, 2))
        m.addConstrs(assignment.sum(b, d, '*') <= 1 for b in range(B) for d in range(D))
                
        # time shift constrains
        m.addConstrs(powerCB[b, t] == 0 for b in range(B) for t in range(startTimeNum))
        m.addConstrs(gridPowToB[b, t] == 0 for b in range(B) for t in range(startTimeNum))
        m.addConstrs(chargerUse[b, t] == 0 for b in range(B) for t in range(startTimeNum))

        # make the model static
        # TODO: fix this so that the assignemnts use the heuristic
        # m.addConstrs(assignment[b, d, b] == 1 for b in range(B) for d in range(D))

        # charge tracking to avoid <49kwh when power is available
        # tracker_b = 1 if eB > 49*.25 = 12.25
        M = 1000

        m.addConstrs(((eB_max - eB[b, t]) + M*tracker[b, t] >= (pCB_ub*dt) ) for b in range(B) for t in optimized_time)
        m.addConstrs(((eB_max - eB[b, t]) <= (pCB_ub*dt) + M*tracker_b[b, t]) for b in range(B) for t in optimized_time)
        m.addConstrs((tracker[b, t] + tracker_b[b, t] == 1) for b in range(B) for t in optimized_time)
        # m.addConstrs(powerCB[b, t] >= pCB_ub * tracker_b[b, t]*chargerUse[b, t] for b in range(B) for t in optimized_time)
        # m.addConstrs(powerCB[b, t]*chargerUse[b, t] >= )
        # ###################################
        # Setting Objective and Solving
        ###################################
        sums_over_buses = [sum(gridPowToB[b, t] for b in range(B)) for t in range(T)]
        # check size
        assert len(sums_over_buses) == T

        obj_coeffs = np.array(sums_over_buses)
        obj_vals = obj_coeffs * gridPowPrice

        # Create a LinExpr object from the array using the quicksum method
        obj_expr = 0.25 * gp.quicksum(obj_vals)
        m.setObjective(obj_expr, gp.GRB.MINIMIZE)

        # Solve the model
        m.optimize()

        #####################################
        # Exporting Results
        #####################################
        
        # Checking if it is feasible
        if m.status != gp.GRB.INFEASIBLE:

            # create a dictionary of variable names and values
            variable_dict = {var.VarName: var.x for var in m.getVars()}

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
            chargerUse_df = genDF('chargerUse')
            # gridpowtoB_df = genDF('gridPowToB')
            eB_df = genDF('eB')

            dfs = [powerCB_df,  eB_df, chargerUse_df]
            twodim_df = pd.concat(dfs, axis=1, join='inner')
            path = os.path.join(os.getcwd(), "chargeopt")

            # export to csv
            twodim_df.to_csv(f'{path}/outputs/{filename}.csv')

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
            assignment_df.to_csv(f'{path}/outputs/assignments_{filename}.csv')

            # create the results DataFrame
            results_df = pd.DataFrame(columns=["case_name", "numBuses", "ebMaxKwh", "numChargers", "chargerPower", "chargerEff",
                                            "routes", "gridMaxPower", "obj_val", "sol_time", "date",
                                            "type"])
            results_file = f'{path}/outputs/results.csv'

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
            current_date = datetime.now().strftime("%m/%d/%Y")

            # append the results to the DataFrame
            results_df = results_df.append(
                {
                    "case_name": filename,
                    "numBuses": B,
                    "ebMaxKwh": eB_max,
                    "numChargers": numChargers,
                    "chargerPower": pCB_ub,
                    "routes": str(routes),
                    "gridMaxPower": gridKWH,
                    "obj_val": obj_val,
                    "sol_time": sol_time,
                    "date": current_date,
                    # "type": config['runType']
                },
                ignore_index=True,
            )

            # print charging[b, d]
            # print(chargerUse[b, t])
             # two-dimensional
            def genCharging(varName):
                df = pd.DataFrame(columns=['day', 'bus', 'value'])
                data = []

                for d in range(D):
                    for b in range(B):
                        value = variable_dict[f'{varName}[{b},{d}]']
                        data.append({'day': d, 'bus': b, f'{varName}': value})

                df = pd.DataFrame(data)
                df = df.set_index(['bus', 'day'])

            # chargeUse = genDF('chargerUse')
            # chargeUse = chargeUse.sort_values(by=['bus', 'time'])
            # st.write(chargeUse)

            # chargeDaily = genCharging('charging')
            # st.write(chargeDaily)

            # change = genDF('change')
            # st.write(change)
            
            # sum of change for each day and bus
            # a day is 96 time steps
            # for d in range(D):
            #     for b in range(B):
            #         changeSum = change.iloc[b, d*96:(d+1)*96].sum()
            #         st.write(changeSum)
            # changeSum = change.groupby(['bus', 'time']).sum()
            # st.write(changeSum)

            

            # write the results to the results.csv file
            results_df.to_csv(results_file, index=False)

        if m.status == gp.GRB.INFEASIBLE:
           status = "Model is infeasible"
        elif m.status == gp.GRB.OPTIMAL:
            status = "Optimal solution found"
        else:
            status = "Model Error"

        return status 