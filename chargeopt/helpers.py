#!/usr/bin/env python3
import pandas as pd
import math
import numpy as np
from numpy import cos, sin, arccos, arcsin, reshape, repeat


def initGridAvailability(fileName, numDays):
    # This function sets the power available from the grid. The output of this
    # function is normalized such that the maximum power available from the
    # grid is 1 kWh.
    #       time increment: 15 minutes
    #       time duration: 3 days

    # Get data from Excel Doc
    gridPowAvail = np.zeros(96)
    gridData = pd.read_excel(fileName, header=None, usecols="B:KC", skiprows=1)
    for i in range(96):
        gridPowAvail[i] = 1000 * gridData.iloc[0, 3 * i]

    # Normalize to 1kWh maximum available
    maxAvail = max(gridPowAvail)
    gridPowAvail = [p / maxAvail for p in gridPowAvail]

    # Extend list to proper number of days
    gridPow_init = gridPowAvail
    for d in range(numDays - 1):
        gridPowAvail = gridPowAvail + gridPow_init

    return gridPowAvail


def initGridPricing(numDays):
    # This function sets the price per kWh of grid electricity
    #       time increment: 15 minutes

    # Assume summer weekday pricing
    #   Peak:       .59002 dollars per kwh     12:00 - 18:00
    #   Partial:    . 29319 dollars per kwh     08:30 - 12:00;   18:00 - 21:30
    #   Off Peak:   .22161 dollars per kwh     00:00 - 8:30;    21:30 - 24:00

    # Create list of prices for single day
    grid_pow_price = [0] * 96
    for t in range(96):
        minutes = 15 * (t + 1)
        if (minutes > 12 * 60) and (minutes <= 18 * 60):
            grid_pow_price[t] = 0.59002
        elif (((minutes > 8.5 * 60) and (minutes <= 12 * 60)) or
              ((minutes > 18 * 60) and (minutes <= 21.5 * 60))):
            grid_pow_price[t] = 0.29319
        else:
            grid_pow_price[t] = 0.22161

    # Extend list to proper number of days
    grid_pow_init = grid_pow_price
    for d in range(1, numDays):
        grid_pow_price.extend(grid_pow_init)

    return grid_pow_price


def initSolarPowModel(season, numDays, mornings, noons, nights):
    # SOLAR GENERATION PARAMETERS
    AZ_ANG_ARRAY = 180  # PV solar panel array azimuth angle                degrees
    TILT_ANG_ARRAY = 30  # PV solar panel array tilt angle                   degrees
    LAT = 37.385  # observer latitude                                 degrees
    LONG_SM = 120  # longitude of standard meridian time zone          degrees
    LONG_LOC = 121.8863  # observer local longitude                          degrees
    EFF_ARRAY = .15  # PV solar panel array efficiency                   percent
    DC_MW_rating = 3.75  # DC power rating of PV solar panel @ STC           MW
    STC_solar_irr = 1000  # Solar irradiation on PV solar panel @ STC         W / m^2
    SOIL_LOSS = .02  # Array system losses due to foriegn matter         %
    SHADING_LOSS = 0  # Array system losses due to shadows                %
    SNOW_LOSS = 0  # Array system losses due to snow                   %
    MISMATCH_LOSS = .02  # Array system losses due to imperfections          %
    WIRING_LOSS = .02  # Array system losses due to resistance             %
    CONNECTION_LOSS = .005  # Array system losses due to electric connectors    %
    DEGRADATION_LOSS = .015  # Array system losses due to light degradation      %
    NAMEPLATE_LOSS = .01  # Array system losses due to nameplate inaccuracy   %
    AGE_LOSS = 0  # Array system losses due to weathering             %
    AVAIL_LOSS = .03  # Array system losses due to system shutdowns       %
    INVERTER_EFF = .95  # DC to AC Inverter Efficiency                      %
    CLOUDY_EFF = .2  # Percent output on cloudy days                     %

    # AVAILABLE SOLAR POWER PER TIME STEP
    arrayArea = (DC_MW_rating * 10 ** 6) / (STC_solar_irr * EFF_ARRAY)  # m^2
    performanceRatio = (1 - SOIL_LOSS) * (1 - SHADING_LOSS) * (1 - SNOW_LOSS) * (1 - MISMATCH_LOSS)
    performanceRatio = performanceRatio * (1 - WIRING_LOSS) * (1 - CONNECTION_LOSS) * (1 - DEGRADATION_LOSS)
    performanceRatio = performanceRatio * (1 - NAMEPLATE_LOSS) * (1 - AGE_LOSS) * (1 - AVAIL_LOSS)

    # Open Excel file containing NSRD Data
    DN_solar_irr = pd.read_excel('DNI_data_2015.xlsx', sheet_name='DNI_data_2015', usecols=[6], skiprows=2)

    DN_solar_irr = DN_solar_irr.to_numpy()
    DH_solar_irr = pd.read_excel('DNI_data_2015.xlsx', sheet_name='DNI_data_2015', usecols=[5], skiprows=2)
    DH_solar_irr = DH_solar_irr.to_numpy()

    # Create list of days of year and times of day
    # Creates solar calculations dependent on the location of earth in orbit and earth's tilt
    daysinyear = 365
    day_YR = np.arange(start=1, stop=daysinyear+1)  # day of year #changed
    local_time = np.arange(0, 24, 0.5)  # time of day in 30 minute increments
    Eqt = np.zeros(daysinyear)
    solarTime = np.zeros((daysinyear, len(local_time)))

    # Calculate declination angle of sun on each day - Based on day of year only
    declinationAng = 23.45 * np.sin((360 / 365) * (284 + day_YR))

    # Calculate Equation of Time - "Eqt" - Based on day of year only
    for i in range(daysinyear):
        if day_YR[i] <= 106:
            Eqt[i] = -14.2 * np.sin((math.pi / 111) * (day_YR[i] + 7))
        elif day_YR[i] >= 107 and day_YR[i] <= 166:
            Eqt[i] = 4 * np.sin((math.pi / 59) * (day_YR[i] - 106))
        elif day_YR[i] >= 167 and day_YR[i] <= 246:
            Eqt[i] = -6.5 * np.sin((math.pi / 80) * (day_YR[i] - 166))
        else:
            Eqt[i] = 16.4 * np.sin((math.pi / 113) * (day_YR[i] - 247))

    # Calculate array irradiance angle for each half hour of each day
    hourAng = np.zeros((daysinyear, len(local_time)))
    solar_zenithAng = np.zeros((daysinyear, len(local_time)))
    solar_elevationAng = np.zeros((daysinyear, len(local_time)))
    arrayIrradiance_Ang_init = np.zeros((daysinyear, len(local_time)))
    solar_azimuthAng = np.zeros((daysinyear, len(local_time)))

    for i in range(daysinyear):
        for j in range(len(local_time)):
            # Calculate solar time
            solarTime[i, j] = local_time[j] + (Eqt[i] / 60) + ((LONG_SM - LONG_LOC) / 15)  # in hours
            # Calculate hour angle
            hourAng[i, j] = 15 * (solarTime[i, j] - 12)  # degrees
            # Calculate Solar Zenith Angle
            solar_zenithAng[i, j] = np.arccos(np.sin(np.deg2rad(LAT)) * np.sin(np.deg2rad(declinationAng[i])) + (
                    np.cos(np.deg2rad(LAT)) * np.cos(np.deg2rad(declinationAng[i])) * np.cos(
                np.deg2rad(hourAng[i, j]))))  # degrees
            solar_zenithAng[i, j] = np.rad2deg(solar_zenithAng[i, j])
            # Calculate Solar Elevation Angle
            solar_elevationAng[i, j] = np.arcsin(
                np.sin(np.deg2rad(declinationAng[i])) * np.sin(np.deg2rad(LAT)) + np.cos(
                    np.deg2rad(declinationAng[i])) * np.cos(np.deg2rad(hourAng[i, j])) * np.cos(
                    np.deg2rad(LAT)))  # degrees
            solar_elevationAng[i, j] = np.rad2deg(solar_elevationAng[i, j])
            # Calculate Solar Azimuth Angle
            solar_azimuthAng[i,j] = np.degrees(np.arccos((np.sin(np.deg2rad(declinationAng[i])) * np.cos(
                np.deg2rad(LAT)) - np.cos(np.deg2rad(declinationAng[i])) * np.cos(
                np.deg2rad(hourAng[i, j])) * np.sin(np.deg2rad(LAT))) / np.cos(np.deg2rad(solar_elevationAng[i, j]))))
            # Calculate Array Irradiance Angle (in 3 steps)
            arrayIrradiance_a = np.cos(np.deg2rad(solar_zenithAng[i, j])) * np.cos(np.deg2rad(TILT_ANG_ARRAY))
            arrayIrradiance_b = np.sin(np.deg2rad(solar_zenithAng[i, j])) * np.sin(np.deg2rad(TILT_ANG_ARRAY)) * np.cos(
                np.deg2rad(solar_azimuthAng[i, j] - AZ_ANG_ARRAY))
            arrayIrradiance_Ang_init[i,j] = np.degrees(np.arccos(arrayIrradiance_a + arrayIrradiance_b))

    # Reshape 2D matrix into 1D array in which columns all all the half hours of a year in consecutive order
    initVal = 0
    finVal = 17520
    arrayIrradiance_Ang_fin = np.reshape(np.transpose(arrayIrradiance_Ang_init), [1, finVal])

    # Solar Irradiance (DNI and DHI) that hits solar panel array normal to the surface of the solar panel in W/m^2
    arrayIrradiance_DN = DN_solar_irr * np.cos(np.deg2rad(arrayIrradiance_Ang_fin.T))
    arrayIrradiance_DH = DH_solar_irr * np.cos(np.deg2rad(arrayIrradiance_Ang_fin.T))
    arrayIrradiance_30 = arrayIrradiance_DN + arrayIrradiance_DH  # total irradiance incident upon solar panels

    # Modify Solar Irradiance Array to be every 30 minutes to every 15 minutes
    # to align with rest of optimization model
    arrayIrradiance = np.repeat(arrayIrradiance_30, 2)

    # Calculate PV Solar Array Power Generation every 15 minutes for one year
    # DC Power
    PV_kW = arrayArea * performanceRatio * EFF_ARRAY * arrayIrradiance * (1 / 1000)

    # AC Power Avaialable from solar panels
    PV_kW_avail = PV_kW * INVERTER_EFF

    # Replace negative AC Power Available from solar panels with 0
    ID = PV_kW_avail < 0  # binary value of 1 when alpha is greater than 0.3
    PV_kW_avail[ID] = 0  # replace negative values with zero

    # Normalize to 1kW solar generation profile
    maxGen = np.max(PV_kW_avail)
    PV_kW_avail = PV_kW_avail / maxGen

    timesteps = 96
    if season == 'summer':
        startDay = 196
        endDay = startDay + numDays - 1
    elif season == 'winter':
        startDay = 15
        endDay = startDay + numDays - 1

    startTime = (startDay - 1) * timesteps + 1
    endTime = endDay * timesteps
    PV_kW = PV_kW_avail[startTime: endTime+1] # changed
    PV_kW_max_reshape = PV_kW.reshape(timesteps, numDays)
    PV_kW_reshape = np.zeros((timesteps, numDays))

    morning = np.arange(0, 10 * 4)
    midday = np.arange(10 * 4 + 1, (14 * 4) + 1)
    afternoon = np.arange((14 * 4) + 2, 96)
    PV_kW_morning = np.zeros((timesteps, numDays))
    PV_kW_midday = np.zeros((timesteps, numDays))
    PV_kW_afternoon = np.zeros((timesteps, numDays))

    for i in range(numDays):
        if mornings[i] == 'cloudy':
            PV_kW_morning[morning, i] = PV_kW_max_reshape[morning, i] * CLOUDY_EFF
        else:
            PV_kW_morning[morning, i] = PV_kW_max_reshape[morning, i]

        if noons[i] == 'cloudy':
            PV_kW_midday[midday, i] = PV_kW_max_reshape[midday, i] * CLOUDY_EFF
        else:
            PV_kW_midday[midday, i] = PV_kW_max_reshape[midday, i]

        if nights[i] == 'cloudy':
            PV_kW_afternoon[afternoon, i] = PV_kW_max_reshape[afternoon, i] * CLOUDY_EFF
        else:
            PV_kW_afternoon[afternoon, i] = PV_kW_max_reshape[afternoon, i]

    PV_kW_addition = PV_kW_morning + PV_kW_midday + PV_kW_afternoon
    solarPowAvail = PV_kW_addition.reshape(1, numDays * timesteps)

    return solarPowAvail


def initRoutes(routeNums, numDays, eB_max, pCB_max):
    # Read in all the data
    routeData = pd.read_excel('allRoutes.xlsx', usecols=[0, 1, 2, 3], index_col=0)

    # Determine the number of busses
    numRoutes = len(routeNums)

    # Initialize arrays for bus scheduling
    nRoutes = [numDays] * numRoutes
    eRoute = np.zeros(numRoutes)
    routeReturn = np.zeros(numRoutes)
    nRunning = np.zeros(4 * 24)

    departure = np.zeros(numRoutes)
    arrival = np.zeros(numRoutes)

    # For each route we have selected:
    # set the bus as unavailable for the duration of the route
    # determine how much to discharge the bus by when it returns
    for i in range(numRoutes):
        # Get route information
        r = routeNums[i]
        routeInfo = routeData.loc[[r]].values[0]
        tDepart = int(routeInfo[0])
        tReturn = int(routeInfo[1])
        distance = routeInfo[2]
        tRoute = range(tDepart, tReturn + 1)
        routeReturn[i] = tReturn

        departure[i] = tDepart
        arrival[i] = tReturn

        # Calculate energy of route
        kwhPerMile = 2
        routeEnergy = distance * kwhPerMile
        eRoute[i] = routeEnergy

        # Track how many routes run at each time
        for j in range(tDepart, tReturn + 1):
            nRunning[j] += 1

    # Check for route energy out of bounds, route returning too late
    routeOutOfRange = False
    routeLateReturn = False
    for i in range(numRoutes):
        if eRoute[i] >= eB_max:
            routeOutOfRange = True
        timeToCharge = (1 / .94) * 60 * eRoute[i] / pCB_max
        indicesToCharge = int(timeToCharge / 15 + 0.5)
        if indicesToCharge >= (arrival[i] + 96 - departure[i]):
            routeLateReturn = True

    # Return report on infeasible route
    report = 'All Clear'
    if routeLateReturn and routeOutOfRange:
        report = 'Multiple Route Issues'
    elif routeLateReturn:
        report = 'Route Returns Too Late'
    elif routeOutOfRange:
        report = 'Route Out Of Range'

    return departure, arrival, eRoute, report
