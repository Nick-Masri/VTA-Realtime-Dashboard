#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime
import math



def time_to_quarter(datetime_str):
    dt = datetime.strptime(datetime_str, '%I:%M %p')
    total_minutes = dt.hour * 60 + dt.minute
    quarter_hour = math.ceil(total_minutes / 15)
    return quarter_hour

def init_grid_pricing(numDays):
    # This function sets the price per kWh of grid electricity
    #       time increment: 15 minutes

    # Assume summer weekday pricing
    #   Peak:       .59002 dollars per kwh     12:00 - 18:00
    #   Partial:    . 29319 dollars per kwh     08:30 - 12:00;   18:00 - 21:30
    #   Off Peak:   .22161 dollars per kwh     00:00 - 8:30;    21:30 - 24:00
    # startTime = startTime.strftime('%I:%M %p')
    # startTimeNum = time_to_quarter(startTime)
    # startTimeNum = 0
    # Create list of prices for single day
    grid_pow_init = [0] * 96
    for t in range(96):
        # shift by start time
        minutes = 15 * (t + 1)
        if (minutes > 12 * 60) and (minutes <= 18 * 60):
            grid_pow_init[t] = 0.59002
        elif (((minutes > 8.5 * 60) and (minutes <= 12 * 60)) or
              ((minutes > 18 * 60) and (minutes <= 21.5 * 60))):
            grid_pow_init[t] = 0.29319
        else:
            grid_pow_init[t] = 0.22161

    # Extend list to proper number of days
    grid_pow_price = []
    for _ in range(numDays):
        grid_pow_price.extend(grid_pow_init)
        
    return grid_pow_price


def init_routes(routeDF, eB_range, pCB_max):

    # Determine the number of busses
    numRoutes = len(routeDF)

    kwhPerMile = 2.5
    
    routeDF['block_startTime'] = routeDF['block_startTime'].apply(time_to_quarter)
    routeDF['block_endTime'] = routeDF['block_endTime'].apply(time_to_quarter)
    print(routeDF[['block_startTime', 'block_endTime']])
    # make column int type
    routeDF['block_startTime'] = routeDF['block_startTime'].astype(int)
    routeDF['block_endTime'] = routeDF['block_endTime'].astype(int)
    
    departure = routeDF['block_startTime'].to_numpy()
    arrival = routeDF['block_endTime'].to_numpy()

    # Calculate energy of route
    eRoute = routeDF['Mileage'].to_numpy() * kwhPerMile

    # Check for route energy out of bounds, route returning too late
    routeOutOfRange = False
    routeLateReturn = False
    for i in range(numRoutes):
        if eRoute[i] >= eB_range:
            routeOutOfRange = True
        timeToCharge = (1 / .94) * 60 * eRoute[i] / pCB_max
        indicesToCharge = int(timeToCharge / 15 + 0.5)
        if indicesToCharge >= (arrival[i] + 96 - departure[i]):
            routeLateReturn = True

    # Return report on infeasible route
    report = 'All Clear'
    if routeLateReturn and routeOutOfRange:
        report = 'Multiple Route Issues'
        print('Multiple Route Issues')
    elif routeLateReturn:
        report = 'Route Returns Too Late'
        print('Route Returns Too Late')
    elif routeOutOfRange:
        report = 'Route Out Of Range'
        print('Route Out Of Range')

    return departure, arrival, eRoute, report
