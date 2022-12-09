import gurobipy as gp
from gurobipy import GRB
import numpy as np
from gridPowPrice import initGridPricingModel
from routes import initRoutesDynamically

# gp.reset()

model = gp.Model('chargeopt')
#############
# params
#############
D = 7
T = 24*D
dt = .25
time = [15*(t+1)/60 for t in range(T)]
# 15*(1:T)/60

B = 10
numChargers = 3

eB_max = 675
eB_min = 135

pCB = 75
pCB_min = 75
eff_CB = .94

eM_max = 1000
eM_min = 200

pCM_max = 500
pDM_max = 500
eff_CM = .90
eff_DM = .90

routes = [7771, 7772, 7072,7773, 7774]

R = len(routes)

eB_range = eB_max - eB_min

[departure, arrival, eRoute, report] = initRoutesDynamically(routes, D, eB_range, pCB_min)

tDep = np.zeros((R, D))
tRet = np.zeros((R, D))

for d in range(1,D+1):
    for r in range(1,R+1):
        tDep[r-1][d-1] = departure[r-1]+(d-1)*96
        tRet[r-1][d-1] = arrival[r-1]+(d-1)*96

tDay = np.zeros((D, 96))
for d in range(1,D+1):
    tDay[d-1][:] = range((d-1)*96+1,d*96)

season = 'summer'
mornings = ["sunny","sunny","sunny","sunny","sunny","sunny","sunny"]
noons = ["sunny","sunny","sunny","sunny","sunny","sunny","sunny"]
nights = ["sunny","sunny","sunny","sunny","sunny","sunny","sunny"]

# solarPowAvail = 250*initSolarPowModel(season, D, mornings, noons, nights)
solarPowAvail = 250

# Generate Grid Availability Profile
# gridPowAvail = 500*initGridAvailability('gridAvailData.xlsx', D)
gridPowAvail = 500

# Generate Grid Pricing Profile
gridPowPrice = initGridPricingModel(D)

# Mathematical Model %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

# Decision Variables
# Create variables
eM = model.addVar(1, T, vtype=GRB.CONTINUOUS, name="eM")
solarPowToM = model.addVar(1, T, vtype=GRB.CONTINUOUS, name="solarPowToM")
gridPowToM = model.addVar(1, T, vtype=GRB.CONTINUOUS, name="gridPowToM")
solarPowToB = model.addVar(B, T, vtype=GRB.CONTINUOUS, name="solarPowToB")
gridPowToB = model.addVar(B, T, vtype=GRB.CONTINUOUS, name="gridPowToB")
mainPowToB = model.addVar(B, T, vtype=GRB.CONTINUOUS, name="mainPowToB")
chargerUse = model.addVar(B, T, vtype=GRB.BINARY, name="chargerUse")
assignment = model.addVar(B, D, R, vtype=GRB.BINARY, name="assignment")
powerCB = model.addVar(B, T, vtype=GRB.CONTINUOUS, name="powerCB")
powerCM = model.addVar(1, T, vtype=GRB.CONTINUOUS, name="powerCM")
powerDM = model.addVar(1, T, vtype=GRB.CONTINUOUS, name="powerDM")
eB = model.addVar(B, T, vtype=GRB.CONTINUOUS, name="eB")

# Update model to incorporate new variables
model.update()

busLevel = 0.66
reserveLevel = 1

# charging activities
T1 = model.addVars(B, T, vtype=GRB.BINARY)
T2 = model.addVars(B, T, vtype=GRB.BINARY)
Change = model.addVars(B, T, vtype=GRB.BINARY)
charging = model.addVars(B, D, vtype=GRB.BINARY)

for t in range(1,T+1):
    for b in range(1,B+1):
        if t == 1:
            model.addConstr(T1[b,t] == 0)
            model.addConstr(T2[b,t] == 0)
        else:
            model.addConstr(T1[b,t] - T2[b,t] == chargerUse[b,t] - chargerUse[b,t-1])
            model.addConstr(Change[b,t] <= chargerUse[b,t-1] + chargerUse[b,t])
            model.addConstr(Change[b,t] <= 2 - chargerUse[b,t-1] - chargerUse[b,t])

for b in range(1,B+1):
    for d in range(1,D+1):
        model.addConstr(gp.quicksum(Change[b,t] for t in range(tDay[d-1][0],tDay[d-1][96])) <= 2)
        model.addConstr(gp.quicksum(chargerUse[b,t] for t in range(tDay[d-1][0],tDay[d-1][96])) >= 6*charging[b,d])
        model.addConstr(gp.quicksum(chargerUse[b,t] for t in range(tDay[d-1][0],tDay[d-1][96])) <= 96*charging[b,d])

# Constraints
## power availability
gridPowTotal = np.sum(gridPowToB,1) + gridPowToM
model.addConstr(0 <= gridPowTotal <= gridPowAvail)

# Solar Power Constraints
solarPowTotal = np.sum(solarPowToB,1) + solarPowToM
model.addConstr(0 <= solarPowTotal <= solarPowAvail)

# Main Storage Constraints
model.addConstr(powerCM == (solarPowToM + gridPowToM))
model.addConstr(powerDM ==  np.sum(mainPowToB,1))

for t in range(1, T):
    model.addConstr(eM[t+1] == eM[t] + dt * (eff_CM * powerCM[t] - (1/eff_DM) * powerDM[t]))

model.addConstr(eM_min <= eM <= eM_max)
model.addConstr(eM[1] == eM_max * reserveLevel)
model.addConstr(eM[T] >= eM_max * reserveLevel)
model.addConstr(0 <= powerCM <= pCM_max)
model.addConstr(0 <= powerDM <= pDM_max)

# Bus Battery Operation

for b in range(1, B+1):
    for d in range(1, D+1):
        for i in range(1, 97):
            routeDepletion = 0
            if not (d == 1 and i == 1):
                t = tDay[d][i]
                for r in range(1, R+1):
                    if t == tRet[r][d]: # if the route is returning at this time
                        routeDepletion = routeDepletion + eRoute[r] * assignment[b][d][r]
                model.addConstr(eB[b][t] == eB[b][t-1] + dt * powerCB[b][t-1] * eff_CB - routeDepletion)

for b in range(1, B+1):
    for d in range(1, D+1):
        for i in range(1, 97):
            t = tDay[d][i]
            routeRequirement = 0
            for r in range(1, R+1):
                if t == tDep[r][d]:
                    routeRequirement = eRoute[r] * assignment[b][d][r] + routeRequirement
            model.addConstr(eB(b,t) >=  eB_min + routeRequirement)

model.addConstr(solarPowToB + gridPowToB + mainPowToB)


model.addConstr(eB_min <= eB <= eB_max)

for t in range(T):
    for b in range(B):
        model.addConstr(0 <= powerCB[b,t] <= pCB*chargerUse[b,t])

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
model.addConstr(mainPowToB >= 0)
model.addConstr(gridPowToM >= 0)
model.addConstr(gridPowToB >= 0)
model.addConstr(solarPowToM >= 0)
model.addConstr(solarPowToB >= 0)
model.addConstr(eB >= 0)
model.addConstr(eM >= 0)

# Objective Function to Minimize Operational Costs
cost = .25 * gridPowTotal * np.transpose(gridPowPrice)