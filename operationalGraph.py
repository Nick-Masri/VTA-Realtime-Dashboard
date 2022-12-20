import matplotlib.pyplot as plt
import streamlit as st
import datetime
import pandas as pd
import numpy as np
import seaborn as sns

sns.set_style("whitegrid")
sns.set_theme()

def convertHours(hours, minutes):
    if hours >= 12:
        marker = "PM"
    else:
        marker = "AM"

    if hours == 0:
        hours = 12

    if hours >= 13:
        hours -= 12

    if minutes == 0:
        minutes = '00'
    return hours, minutes, marker

def convertRealtimeHours(hours, minutes):
    _d = 96
    if hours >= _d  and hours <= (_d+48):
        hours -= 96
        marker = " AM"
    elif hours >= 48 and hours < _d:
        hours -= 48
        marker = " PM"
    elif hours >= _d+48:
        hours -= 96 + 48
        marker= " PM"
    else:
        marker = " PM"

    if minutes == 0:
        minutes = '00'
    return hours, minutes, marker

def convert_timedelta(duration):
    days, seconds = duration.days, duration.seconds
    hours = days * 24 + seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = (seconds % 60)
    return hours, minutes, seconds

def operationalGraph(input_data, start_time, end_time):
    A = input_data['A']
    # st.write(A)
    _d = 96
    B = input_data['B']
    z = input_data['cu'] # chargerUse(b,t)

    # times the routes get back
    # TODO: fill in with the correct times for each of the blocks (blocks and routes are used
    # interchangeably but should be consistent and sa6y route)
    routeTimes = {
        7072: [24, 70],
        7771: [23, 69],
        7772: [22, 68],
        7773: [21, 67],
        7774: [20, 66],
    }

    # subtract the start time from the time in a day (_d)
    # to get the adjusted time of the route
    for block in routeTimes.keys():
        routeTimes[block][0] += _d - start_time
        routeTimes[block][1] += _d - start_time

    day = 0 # here we only want to print from the one day

    plt.clf()
    # fig, axs = plt.subplots(5, 2, sharex=True, sharey=True, figsize=(10,10))
    fig, axs = plt.subplots(nrows=1, ncols=1, figsize=(13, 9))

    # axis
    a = axs.bar(['Bus {}'.format(i + 1) for i in range(B)], [96], label='Idle',
                edgecolor=None, linewidth=0)

    axs.invert_yaxis()
    axs.set_yticks(ticks=[(96 / 8) * i for i in reversed(range(9))])

    # labels
    labelList = []
    for i in reversed(range(8)):
        labelHours = (96 / 8) * i + start_time
        # marker = " AM" if labelHours >= (_d) and labelhours <= (_d+48) else " PM"

        if labelHours >= _d  and labelHours <= (_d+48):
             labelHours -= 96
             marker = " AM"
        elif labelHours >= 48 and labelHours < _d:
            labelHours -= 48
            marker = " PM"
        elif labelHours >= _d+48:
            labelHours -= 96 + 48
            marker= " PM"
        else:
             marker = " PM"

        labelList.append(str(datetime.timedelta(hours=labelHours / 4))[0:2].replace(':', '') + marker)

    # labelList[-1] = "12 AM"
    labelList.insert(0, "6 PM")
    # labelList[4] = "12 PM"
    axs.set_yticklabels(labels=labelList)
    axs.tick_params(axis="y", pad=-5)

    count = 0
    count2 = 0

    for bus in range(B):

        cT = pd.DataFrame(z[bus, :])
        cT = cT.loc[(cT != 0).any(axis=1)]
        cT_startEnd = [cT.iloc[0].name, cT.iloc[-1].name]

        for idx, row in cT.iterrows():
            b = axs.bar(x='Bus {}'.format((bus+1)), height=1, bottom=idx, color='orange',
                        label='Charging' if count == 0 else '', edgecolor=None, linewidth=0)
            count += 1

        for i, v in enumerate(cT_startEnd):
            plugStart = v / 4
            plugTime = datetime.timedelta(hours=plugStart)
            hours, minutes, seconds = convert_timedelta(plugTime)
            hours, minutes, marker = convertRealtimeHours(hours, minutes)

            axs.text('Bus {}'.format(bus + 1), v+2.5, "{}:{} {}".format(hours,minutes,marker),
                    color='w', fontsize=10, fontweight='bold', ha='center', va='baseline')

        block = A[bus, day]
        rt = routeTimes[block] # A[bus, day] gives the block it served

        # add label for driving
        c = axs.bar(x='Bus {}'.format(bus+1), height=(rt[1]-- rt[0]),
                    bottom=rt[0], color='r', label='Driving' if count2 == 0 else '',
                    edgecolor=None, linewidth=0)

        # drive times
        driveStart = rt[0]
        driveEnd = rt[1]
        driveSTime = datetime.timedelta(hours=driveStart/4)
        driveETime = datetime.timedelta(hours=driveEnd/4)

        # convert start time
        hours, minutes, seconds = convert_timedelta(driveSTime)
        hours, minutes, marker = convertRealtimeHours(hours, minutes)

        # add start time to axs
        axs.text('Bus {}'.format(bus + 1), rt[1]-1, "{}:{} {}".format(hours, minutes, marker),
                    color='w', fontsize=10, fontweight='bold', ha='center', va='baseline')

        # convert end time
        hours, minutes, seconds = convert_timedelta(driveETime)
        hours, minutes, marker = convertRealtimeHours(hours, minutes)

        # add end time to axsk
        axs.text('Bus {}'.format(bus + 1), rt[0]+2.5, "{}:{} {}".format(hours, minutes, marker),
                    color='w', fontsize=10, fontweight='bold', ha='center', va='baseline')

        # add route times
        routeLength= rt[0] + (rt[1] - rt[0])/2

        axs.text('Bus {}'.format(bus + 1), routeLength+.5, " Block #{}".format(block),
        color='b', fontsize=10, fontweight='bold', ha='center', va='baseline', backgroundcolor='lightgray')

        count2 += 1

    for day in range(1):
        # print("###########################")
        # print("Day: {}".format(day + 1))
        # print("###########################")

        for bus in range(B):
            # print("------------")
            # print("Bus: {}".format(bus + 1))
            cT = pd.DataFrame(z[bus, 96 * day:96 * (day + 1)])
            cT = cT.loc[(cT != 0).any(axis=1)]
            block = A[bus, day]
            rt = routeTimes[block]

            # print("Assignment: Route {}".format(block))

            dHours = rt[0] / 4
            if dHours <= 11:
                dayPeriod = 'AM'
            else:
                dayPeriod = 'PM'
                dHours -= 12

            dTime = datetime.timedelta(hours=dHours)
            # print("Departure Time: {} {}".format(str(dTime)[:4], dayPeriod))

            rHours = rt[1] / 4
            if rHours <= 11:
                dayPeriod = 'AM'
            else:
                dayPeriod = 'PM'
                rHours -= 12

            rTime = datetime.timedelta(hours=rHours)
            # print("Return Time: {} {}".format(str(rTime)[:4], dayPeriod))

            if len(cT) > 0:
                plugStart = cT.iloc[0].name / 4
                plugTime = datetime.timedelta(hours=plugStart)
                # print("Plug in: " + (str(plugTime) + " AM" if plugStart <= 11 else str(

                    # datetime.timedelta(hours=plugStart - 12)) + " PM"))

                plugEnd = cT.iloc[-1].name / 4
                plugTime = datetime.timedelta(hours=plugEnd)
                # print("Unplug: " + (
                #     str(plugTime) + " AM" if plugEnd <= 11 else str(datetime.timedelta(hours=plugEnd - 12)) + " PM"))

    fig.legend([a[0], b[0], c[0]], ['Idle', 'Charging', 'Driving'], loc='lower right', bbox_to_anchor=(1, 0.05))

    axs.set_title("Dynamic Assignment Operational Summary Day 1", fontsize=20, pad=20)

    fig.tight_layout(pad=1.5)
    fig.subplots_adjust(top=.90)
    fig.show()
    st.pyplot(fig)
    # fig.savefig("operationalsummaryday{}.png".format(day))

# operationalGraph(input_data)
