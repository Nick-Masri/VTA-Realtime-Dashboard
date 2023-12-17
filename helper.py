# from gurobipy import Model, quicksum
# from gurobipy import GRB
import numpy as np
import pandas as pd
from datetime import time, timedelta, datetime, date


def convert_time_index(time_index):
    base_time = time(0, 0)  # Start with midnight as the base time
    increment = timedelta(minutes=15)  # Each index represents a 15-minute increment
    delta = increment * time_index
    return (datetime.combine(date.today(), base_time) + delta).time()

# converts block time from block csv
def convert_block_time(time):
    time_str = str(time)
    # Extract hour and minute parts
    if time_str[-1] in ['A', 'P', 'X']:
        hour_minute = time_str[:-1]
        am_pm = time_str[-1]
    else:
        return None  # Invalid format

    # Convert 'X' to 'A' for AM
    if am_pm == 'X':
        am_pm = 'A'

    # Create 24-hour format string
    time_24 = hour_minute + ('PM' if am_pm == 'P' else 'AM')

    # Parse and format the time
    try:
        time_obj = datetime.strptime(time_24, '%I%M%p')
        return time_obj
        # return time_obj.strftime('%H:%M')
    except ValueError:
        print('Invalid time format', time)
        return None  # Invalid time