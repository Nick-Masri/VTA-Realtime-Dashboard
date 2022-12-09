import numpy as np
import pandas as pd
from math import ceil

def initRoutesDynamically(routeNums, numDays, eB_max, pCB_max):
# Read in all the data
    routeData = pd.read_excel('allRoutes.xlsx', header=1)
    # Determine the number of busses 
    numRoutes = len(routeNums)

    # Intialize arrays for bus scheduling
    nRoutes = np.zeros((numRoutes,1)) + numDays
    eRoute = np.zeros((numRoutes,1))
    routeReturn = np.zeros((numRoutes,1))
    nRunning = np.zeros((1,4*24))

    departure = np.zeros((numRoutes,1))
    arrival = np.zeros((numRoutes,1))

    # For each route we have selected:
    #   set the bus as unavailable for the duration of the route
    #   determine how much to discharge the bus by when it returns
    for i in range(1, numRoutes):
        # Get route information
        # r = routeNums[i]
        r = i # fix this asap, should correlate to the route number (1st column) in the dataframe. Make this the index
        tDepart = routeData.iloc[r, 1]
        tReturn = routeData.iloc[r, 2]
        distance = routeData.iloc[r, 3]
        # tRoute = range(tDepart, tReturn)
        routeReturn[i] = tReturn

        departure[i] = tDepart
        arrival[i] = tReturn

        # Calculate energy of route
        kwhPerMile = 2 # top 10 occuring operators
        routeEnergy = distance * kwhPerMile
        eRoute[i] = routeEnergy


        # Track how many routes run at each time
        nRunning[tDepart:tReturn] = nRunning[tDepart:tReturn] + 1

    # Check for route energy out of bounds, route returning too late
    routeOutOfRange = False
    routeLateReturn = False
    for i in range(1, numRoutes):
        if eRoute[i] >= eB_max:
            routeOutOfRange = True

    timeToCharge = (1/.94)*60*eRoute[i]/pCB_max
    indicesToCharge = ceil(timeToCharge/15)
    if indicesToCharge >= (arrival[i]+96 - departure[i]):
        routeLateReturn = True

    # Return report on infesible route
    report = 'All Clear'
    if routeLateReturn & routeOutOfRange:
        report = 'Multiple Route Issues'
    elif routeLateReturn:
        report = 'Route Returns Too Late'
    elif routeOutOfRange:
        report = 'Route Out Of Range'

    return departure, arrival, eRoute, report