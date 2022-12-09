import math
import gurobipy

import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from pgbm import PGBM
from scipy.stats import norm

from helper import solve, download, sidebar

# download the file
file = download()

# sidebar()

# setup the data
st.set_page_config(initial_sidebar_state="collapsed")
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
tab1, tab2, tab3, tab4= st.tabs(['Real Time Data and Predictions', 'Weekly Charging Optimization',
                                 'Weekly Summary', 'Explanations'])
                            # 'Historical'
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
    st.write("Red line is kwhs remaining in bus (reserving 20% for battery health")
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

                chart = alt.Chart(data).mark_bar(opacity=0.6).encode(
                    x='block',
                    y=alt.Y('pred_kwh', stack=None, sort='ascending',
                            scale=alt.Scale(domain=[0, 500])),
                    color=alt.Color('type', scale=alt.Scale(
                        domain=['high', 'low', 'mid'],
                        range=["#4878D0", "#EE854A", "#6ACC64"]))
                )

                current_soc = float(ebec_input[ebec_input['Vehicle'] == coach]['start_per'].values[0] / 100)
                val = 440 * (current_soc - 0.2)
                line = alt.Chart(pd.DataFrame({'y': [val]})).mark_rule(strokeDash=[5, 1], color="red").encode(y='y')
                st.altair_chart(chart + line, use_container_width=True)
                # st.write(norm.ppf())
                # st.write()

                mids = preds_df.query("type == 'mid' and coach == @coach")
                # st.dataframe(mids)

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
                # output = data.sort_values('block', ascending=True)
                # TODO: rewrite table
                # TODO: add in optimization predictions

    st.markdown("## Optimization Predictions")
    # st.write("To be added shortly")
    probabilities = prob_data[['coach', 'block', 'prob']]
    probabilities['coach'] = probabilities['coach'].astype(str)
    probabilities['block'] = probabilities['block'].astype(str)
    probabilities = probabilities.set_index(['coach', 'block'])

    st.markdown("### Assignments: ")
    st.markdown("Assuming probablility threshold of 95%")
    assignments = solve(probabilities, ebec_input, prob_data)
    # st.write(assignments)
    assignments = assignments.reset_index()
    assignments = assignments.merge(prob_data, left_on=['index', 'Block'], right_on=['coach', 'block'], how='left')
    st.dataframe(assignments.set_index('index')[['Block', 'Completion Prob.']].sort_index(),
                 use_container_width=True)

    # st.markdown("## Charging Assignments: ")
    # st.write("Make assignments for charging in order to the buses back on track")
    #

# tab2()