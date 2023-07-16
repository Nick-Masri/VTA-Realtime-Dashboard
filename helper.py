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
