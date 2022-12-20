import math
import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from pgbm import PGBM
from scipy.stats import norm

from helper import solve, download, sidebar
from chargerealtime import chargeRealtime

# download the file
file = download()

# sidebar()

# setup the data
# st.set_page_config(initial_sidebar_state="collapsed")
# st.set_page_config(layout="wide")
st.markdown('<style>' + open('style.css').read() + '</style>', unsafe_allow_html=True)
st.title("E-BUS Data Portal")
mileages = {'7774': 105.9, '7773': 167.3, '7772': 145.9, '7771': 107.0, '7072': 112.1}

df = pd.read_pickle('df.pkl')
prob_data = pd.DataFrame(columns=['coach', 'block', 'Completion Prob.', 'prob'])
coaches = df.vehicle.value_counts()
ebec_input = pd.DataFrame(columns=['Date', 'Vehicle', 'start_per'])

for coach in coaches.index:
    # grab most recent data
    coach_df = df[df.vehicle == coach]
    row = coach_df[coach_df.Date == coach_df.Date.max()].iloc[0, :]
    ebec_input = ebec_input.append({'Date': row['Date'], 'Vehicle': row['vehicle'], 'start_per': row['soc']},
                                   ignore_index=True)

ebec_input['month'] = ebec_input['Date'].dt.month

# setup tabs for output
tab1, tab2, tab3 = st.tabs(['Current SOC', 'Energy Consumption Predictions', 'Assignment Optimization' ])

# Current SOC
with tab1:
    # write output to dashboard
    output = ebec_input
    output.start_per = (np.around(output.start_per.astype(float), 0)).astype(int)
    output.Date = output.Date.dt.strftime("%m/%d %I:%M %p PST")
    output = output.rename(columns={'start_per': "SOC %", "Date": "Last Online"})
    st.markdown("## Current SOC")
    cols = st.columns(2)
    with cols[0]:
        # st.bar_chart(data=output, y="Vehicle:N", x='SOC %:Q')

        bar = alt.Chart(output).mark_bar(color='green').encode(
            x='SOC %:Q',
            y=alt.Y('Vehicle:N', sort='ascending'),
        ).properties(
            height=alt.Step(40)  # controls width of bar.
        )

        st.altair_chart(bar, use_container_width=True)
    output.index = output.Vehicle
    with cols[1]:
        output['SOC %'] = output['SOC %'].astype(str) + '%'
        st.dataframe(output[['SOC %', "Last Online"]].sort_index(ascending=True), use_container_width=True)

# Energy consumption predictions
with tab2:
    # prepare data
    ebec_final = ebec_input[['start_per', 'month']]
    ebec_final['start_per'] = ebec_final['start_per'].astype(float)

    model_new = PGBM()
    model_new.load('model1.pt')

    # Point and probabilistic predictions
    yhat_point = model_new.predict(ebec_final.values)
    yhat_dist = model_new.predict_dist(ebec_final.values, output_sample_statistics=True)

    means = yhat_dist[1]
    variance = yhat_dist[2]

    predictions = []
    for coaches in range(ebec_final.shape[0]):
        min = yhat_dist[0][:, coaches].min().item()
        max = yhat_dist[0][:, coaches].max().item()
        predictions.append((min, max))

    coaches = list(ebec_input.Vehicle.values)

    preds_df = pd.DataFrame(columns=['coach', 'block', 'pred_eff', 'pred_kwh', 'type'])

    for idx, coach in enumerate(coaches):
        pred = predictions[idx]

        low = pred[0]
        mid = yhat_point[idx].item()
        mean = means[idx].item()
        var = variance[idx].item()
        high = pred[1]
        preds = [low, mid, high]

        for block in mileages.keys():
            miles = mileages[block]
            for idx, pred in enumerate(preds):
                if idx == 0:
                    type = 'low'
                elif idx == 1:
                    type = 'mid'
                else:
                    type = 'high'

                preds_df = preds_df.append(
                    {'coach': coach, 'block': block, 'pred_eff': pred, 'pred_kwh': pred * miles, 'type': type,
                     'mean': mean, 'var': var},
                    ignore_index=True)

    fig, ax = plt.subplots(1, len(coaches), figsize=(10, 40))
    N_series = 3
    coaches = sorted(coaches)

    st.markdown("## Energy Consumption Predictions")
    with st.expander("See explanation"):
        st.write("### Energy Remaining")
        st.write("Red line is kwhs remaining in bus (reserving 20% for battery health) = ")
        st.latex(r'''
        440 * ( SOC - 0.2)
        ''')
        st.write("SOC = state of charge of the bus (0 - 100%)")
        st.write("### High, mid, and low predictions")
        st.write("Predictions were made using the pgbm library - Probabilistic Gradient Boosting Machines (https://github.com/elephaint/pgbm). \
            This library provides probablistic predictions instead of just point estimates by fitting a distribution to the data. \
            The model outputs 100 samples from the distribution given the inputs. \
            The high is the highest of the sample, the low is the lowest, and the mid. This captures the uncertainty in the data pretty well. \
            Below I included a demo of the model and how it performs on a test dataset with data it hasn't seen before. It does a good job of capturing the uncertainity, \
            and the point predictions are typically close, though there are a lot of factors in determining energy consumption(traffic, temperature, operator) that are not currently being accounted for. ")
        st.image("pgbm-demo.png")
        st.write("### Probablity of Completion")
        code = ''' miles = mileages[block]
kwhs_to_go = 440 * (current_soc - 0.2)  # kwhs left in tank
eff = kwhs_to_go / miles  # eff
prob = norm.cdf(eff, val['pred_eff'], val['var'] ** 0.5)'''
        st.code(code)
        st.write("This code calculates the probability that an electric bus will have a certain efficiency level given the distance it needs to travel and its current state of charge (SOC). It does this by first looking up the distance the bus needs to travel in a dictionary, then calculating the number of kilowatt-hours (kWh) the bus has left in its battery. The efficiency of the bus is calculated by dividing the number of kWh it has left by the distance it needs to travel. Finally, the code uses a normal cumulative distribution function to calculate the probability that the bus will have an efficiency level equal to or greater than the value calculated earlier, based on the predicted efficiency and variance of the bus's efficiency.")


    n_coaches = ebec_final.shape[0]

    preds_df.type = pd.Categorical(preds_df.type,
                                   categories=["high", "mid", "low"],
                                   ordered=True)
    nrows = math.ceil(n_coaches / 2)
    preds_df = preds_df.sort_values('type')



    for j in range(nrows):
        cols = st.columns(2)
        for idx, col in enumerate(cols):
            with col:
                try:
                    coach = coaches[idx + j * 2]
                except IndexError:
                    break
                data = preds_df[preds_df["coach"] == coach]
                st.markdown("## Coach: {}".format(coach))

                colors = list(sns.color_palette())

                # point chart for mid
                chart = alt.Chart(data[data.type == 'mid']).mark_point(filled=True, size=75, color='black').encode(
                    x = alt.X('block', scale=alt.Scale(paddingOuter=0.2, paddingInner=0.2),
                              ),
                    y = alt.Y('pred_kwh', stack=None, sort='ascending',
                              scale=alt.Scale(domain=[0, 600]),
                              axis=alt.Axis(),
                              title='Predicted Energy Consumption (kWh)'),
                )

                pivoted = preds_df.pivot(index=['coach', 'block'], columns= 'type', values='pred_kwh').reset_index()
                pivoted['y2'] = pivoted.high - pivoted.low

                # error bars
                chart2 = alt.Chart(pivoted.query("coach == @coach")).mark_errorbar(ticks=True).encode(
                    x = alt.X('block:N'),
                    y = alt.Y('low', stack=None, sort='ascending',
                              scale=alt.Scale(domain=[0, 600]), title=''),
                    y2 = alt.Y2('high')
                )

                current_soc = float(ebec_input[ebec_input['Vehicle'] == coach]['start_per'].values[0] / 100)
                safe = 440 * (current_soc - 0.2)
                # line = alt.Chart(pd.DataFrame({'y': [safe]})).mark_rule(color="yellow").encode(y='y')
                max_amt = 440 * (current_soc)
                # line2 = alt.Chart(pd.DataFrame({'y': [max_amt]})).mark_rule(color="red").encode(y='y')

                cutoff = pd.DataFrame({
                    'start': [0, safe, max_amt],
                    'stop': [safe, max_amt, 600],
                })

                cutoff_new = pd.DataFrame(columns=['start', 'stop', 'block'])
                for idx, row in cutoff.iterrows():
                    for block in data.block.unique():
                        row['block'] = block
                        cutoff_new = cutoff_new.append(row, ignore_index=True)

                cutoff = cutoff_new

                # Create the rectangles to shade the regions
                rect1 = alt.Chart(cutoff[cutoff['stop'] == safe]).mark_rect(color='green', opacity=0.03).encode(
                    y='start:Q',
                    y2='stop:Q',

                )

                rect2 = alt.Chart(cutoff[(cutoff['start'] >= safe) & (cutoff['stop'] <= max_amt)]).mark_rect(color='yellow', opacity=0.05).encode(
                    y='start:Q',
                    y2='stop:Q'
                )

                rect3 = alt.Chart(cutoff[cutoff['start'] >= max_amt]).mark_rect(color='red', opacity=0.05).encode(
                    y='start:Q',
                    y2='stop:Q'
                )

                final_chart = alt.layer(rect1, rect2, rect3, chart, chart2).configure_axis()
                st.altair_chart(final_chart, use_container_width=True)

                mids = preds_df.query("type == 'mid' and coach == @coach")

                for idx, val in mids.iterrows():
                    block = val['block']
                    miles = mileages[block]
                    kwhs_to_go = 440 * (current_soc - 0.2)  # kwhs left in tank
                    eff = kwhs_to_go / miles  # eff
                    prob = norm.cdf(eff, val['pred_eff'], val['var'] ** 0.5)
                    prob_data = prob_data.append(
                        {'coach': coach, 'block': block,
                         'Completion Prob.': "{}%".format(int(prob * 100)), 'prob': prob},
                        ignore_index=True)
                prob_data = prob_data.sort_values('block', ascending=True)


                def highlight_cells(val, color_if_true, color_if_false):
                    color = color_if_true if val >= 0.95 else color_if_false


                # prob_data.prob = prob_data.style.applymap(highlight_cells, color_if_true='green',
                # color_if_false='red', subset=['prob']) st.dataframe(prob_data['Probability of Block Completion'],
                # use_container_width=True)
                coach_prop_data = prob_data[prob_data['coach'] == coach]
                coach_prop_data = coach_prop_data[['block', 'Completion Prob.']].set_index('block')
                st.dataframe(coach_prop_data.T, use_container_width=True)

                # TODO: rewrite table
                # TODO: add in optimization predictions
    j = 0
    cols = st.columns(2)

    for idx, col in enumerate(cols):
        with col:
            try:
                coach = coaches[idx + j * 2]
            except IndexError:
                break
            data = preds_df[preds_df["coach"] == coach]
            st.markdown("## Legend")

            current_soc = float(ebec_input[ebec_input['Vehicle'] == coach]['start_per'].values[0] / 100)
            safe = 440 * (current_soc - 0.2)
            max_amt = 440 * (current_soc)

            cutoff = pd.DataFrame({
                'start': [0, safe, max_amt],
                'stop': [safe, max_amt, 600],
            })

            cutoff_new = pd.DataFrame(columns=['start', 'stop', 'block'])
            for idx, row in cutoff.iterrows():
                for block in data.block.unique():
                    row['block'] = block
                    cutoff_new = cutoff_new.append(row, ignore_index=True)

            cutoff = cutoff_new

            # Create the rectangles to shade the regions
            rect1 = alt.Chart(cutoff[cutoff['stop'] == safe]).mark_rect(color='green', opacity=0.03).encode(
                y=alt.Y('start:Q', title='Predicted Energy Consumption (kWh)'),
                y2='stop:Q',

            )

            rect1_text = rect1.mark_text(
                opacity=0.4,
                align='center',
                baseline='top',
                dy=-80,
                fontSize = 10,
                text= "Energy in Bus without using reserve",
                fontWeight = 100,
                lineBreak='\n'
            )

            rect2 = alt.Chart(cutoff[(cutoff['start'] >= safe) & (cutoff['stop'] <= max_amt)]).mark_rect(color='yellow', opacity=0.05).encode(
                y='start:Q',
                y2='stop:Q'
            )

            rect2_text = rect2.mark_text(
                opacity=0.4,
                align='center',
                baseline='top',
                dy=-30,
                fontSize = 10,
                text= "Energy in Bus + reserve",
                fontWeight = 100
            )

            rect3 = alt.Chart(cutoff[cutoff['start'] >= max_amt]).mark_rect(color='red', opacity=0.05).encode(
                y='start:Q',
                y2='stop:Q'

            )

            rect3_text = rect3.mark_text(
                opacity=0.4,
                align='center',
                baseline='top',
                dy=-40,
                fontSize = 10,
                text= "Exceeds Bus Energy",
                fontWeight = 100
            )

            final_chart = alt.layer(rect1_text, rect1, rect2_text, rect2, rect3_text, rect3).configure_axis()
            st.altair_chart(final_chart, use_container_width=True)
            break

# Assignment Optimization
with tab3:
    with st.expander("See explanation"):
        # st.write("### Energy Remaining")
        st.write("This code solves an optimization problem to determine the best assignment of electric buses to different blocks, based on the distance each bus needs to travel and the probability that each bus will have a certain efficiency level. It does this by creating a mathematical model and adding constraints to ensure that each bus and block is assigned to only one coach or block, respectively. The code then solves the optimization problem and returns the solutions as a table of values.")


    probabilities = prob_data[['coach', 'block', 'prob']]
    probabilities['coach'] = probabilities['coach'].astype(str)
    probabilities['block'] = probabilities['block'].astype(str)
    probabilities = probabilities.set_index(['coach', 'block'])

    with st.form("Config"):
        st.write("Probability of completion of all coach/block pairings")
        st.dataframe(prob_data.sort_values(by=['coach', 'block'],  ascending = [True, True])\
            [['coach', 'block', 'Completion Prob.']]\
                .pivot(index="coach", columns="block", values="Completion Prob.")\
                .reset_index(), use_container_width=True)
                   
        st.markdown("### Recommended Assignments (for current SOC): ")

        values = st.slider(
        'Probability threshold needed to be assigned (default of 95%)',
        0.0, 99.0, (95.0))
        submitted = st.form_submit_button("Submit")
        if submitted:
            values = values *.01
            assignments = solve(probabilities, ebec_input, prob_data, threshold=values)
        else:
            assignments = solve(probabilities, ebec_input, prob_data)
            
        assignments = assignments.reset_index()
        assignments = assignments.merge(prob_data, left_on=['index', 'Block'], right_on=['coach', 'block'], how='left')
        assignments = assignments.set_index('index')[['Block', 'Completion Prob.']].sort_index()
        if assignments.shape[0] > 0:
            st.dataframe(assignments, use_container_width=True)
        else:
            st.write("No blocks meet the threshold")


        # TODO: add probability slider
        # TODO: add checkbox to select which buses
        # TODO: update to include distances as well
        # TODO: Highlight input and output based on probability
        # TODO: Reformat input code to tell a better story


# Charging Optimization
# with tab4:
#     with st.form("Charging Optimization"):
#         st.write("Make assignments and charging decisions")
#         st.form_submit_button("Submit")
#         realtime_input = output[['SOC %']]
#         chargeRealtime(realtime_input)

        # TODO: add probability slider
        # TODO: add checkbox to select which buses
        # TODO: output probability of final solution
        # TODO: update to include distances as well
