import streamlit as st
#from scipy.stats import dgamma, laplace_asymmetric
import pandas as pd
import random

class Bus:
    def __init__(self, charge, r_dist):
        self.charge = charge
        self.r_dist = r_dist

busList = []
i = 0
mean = 2
std = 0.005

def run_simulation():
    busList=[]
    i =0
    while(i<11):
        battery = 440
        miles = random.randint(50, 150)
        # select random value from the probability distribution
        # needs some sort of division or percentage function, 
        # otherwise, battery percentage ends up negative
        energy_cons_val = random.normalvariate(mean, std)
        #calculate the random amount of energy used 
        #energy is in kW*hrs
        #battery is 440
        energy = miles * energy_cons_val
        #gives percetage out of 440
        battery = ((battery - energy)/440) *100
        #print('Bus %d returning with %d percent battery' %(i , battery))
        busList.append(Bus(battery,miles))
        i=i+1
    start_list = []
    ret_list = []
    eret_list =[]
    list_pairs = []
    raw_ret_list=[]
    raw_eret_list=[]
    result =""
    #schedule for the buses starts at time 0, expected route duration is 2hrs (120 min)
    scheduled_start = 240
    for j in range(0,10): 
        #bus leaves at a cheduled time (every 120 minutes)
        leave_hr = scheduled_start/60
        leave_12 = "pm"
        if leave_hr < 12:
            leave_12 = "am"
        if(leave_hr ==0):
            leave_hr = 12
        leave_min = scheduled_start%60
        if leave_hr > 12:
            leave_hr = leave_hr -12
        leave_time = "%02d:%02d" % (leave_hr, leave_min) 
        leave_time = leave_time + leave_12
        result += ('Bus %d leaving at time %s\n' % (j+1, leave_time))

        start_list.append(leave_time)
        #the duration of the drive will vary, lets call average of 120 minutes and std of 20 minutes
        drive_dur = random.normalvariate(120, 20)
        #calculate return time
        return_time = drive_dur + scheduled_start
        raw_ret_list.append(return_time)
        return_hr = return_time/60
        return_12 = "am"
        if return_hr > 12 and return_hr <24:
            return_12 = "pm"
        return_min = return_time%60
        if return_hr > 13:
            return_hr = return_hr -12
        if return_hr == 0:
            return_hr = return_hr + 12
        ## i have a bug in here going from am to pm 
        freturn_time = "%02d:%02d" % (return_hr, return_min) 
        freturn_time = freturn_time + return_12
        result+= ('Bus %d returning at time %s\n' % (j+1, freturn_time))
        
        ret_list.append(freturn_time)
        bat = busList[j].charge
        mil = busList[j].route_len
        result+=('Bus %d returning with %d percent charge after %d miles\n'% (j+1, bat, mil))
        #print('Bus %d returning with %d percent charge after %d miles'% (i+1, bat, mil))
        #est ret time
        ereturn_time = scheduled_start +120
        raw_eret_list.append(ereturn_time)
        ereturn_hr = ereturn_time/60
        ereturn_12 = "pm"
        if ereturn_hr < 12:
            ereturn_12 = "am"
        if(ereturn_hr ==0):
            ereturn_hr = 12
        ereturn_min = ereturn_time%60
        if ereturn_hr > 12:
            ereturn_hr = ereturn_hr -12
        if ereturn_hr == 12:
            ereturn_12 = "am"
    
        efreturn_time = "%02d:%02d" % (ereturn_hr, ereturn_min) 
        efreturn_time = efreturn_time + ereturn_12
        list_pairs.append((scheduled_start, freturn_time))
        list_pairs.append((scheduled_start, efreturn_time))
        result+=('Expected return %s\n\n' % efreturn_time)
        
        eret_list.append(efreturn_time)
        #increment the scheduled start time for the next bus
        scheduled_start = scheduled_start + 120
    return result




def show_simulation():
    st.write(run_simulation())