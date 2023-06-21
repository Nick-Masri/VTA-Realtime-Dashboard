#!/usr/bin/env python3
import pandas as pd
import streamlit as st

def explain_predictions():

    df = pd.read_pickle('../df.pkl')
    coaches = df.vehicle.value_counts()
    with st.expander("See explanation"):
        st.write("### Predictions")
        st.write("Predictions were made using the pgbm library - Probabilistic Gradient Boosting Machines (https://github.com/elephaint/pgbm). \
            This library provides probablistic predictions instead of just point estimates by fitting a distribution to the data. \
            The model outputs 100 samples from the distribution given the inputs. \
            The high is the highest of the sample, the low is the lowest, and the mid. This captures the uncertainty in the data pretty well. \
            Below I included a demo of the model and how it performs on a test dataset with data it hasn't seen before. It does a good job of capturing the uncertainity, \
            and the point predictions are typically close, though there are a lot of factors in determining energy consumption(traffic, temperature, operator) that are not currently being accounted for. ")
        st.image("pgbm-demo.png")
        st.write("### Probablity of Completion")
        code = ''' miles = mileages[block]
kwhs_to_go = 440 * current_soc  # kwhs left in vehicle
        # safe_kwhs_to_go = 440 * (current_soc - 0.2)
eff = kwhs_to_go / miles  # eff
prob = norm.cdf(eff, val['pred_eff'], val['var'] ** 0.5)'''
        st.code(code)
        st.write("Red line is kwhs remaining in bus (reserving 20% for battery health) = ")
        st.latex(r'''
        440 * ( SOC - 0.2)
        ''')
        st.write("SOC = state of charge of the bus (0 - 100%)")

        st.write("Safe Probability = Probability bus completes block without using its reserve (prob. in green). \n\n ")
        st.write("Overall Probability = Probablility bus completes block including using the reserve (prob. not in red).")

        j = 0
        cols = st.columns(2)

        for idx, col in enumerate(cols):
            with col:
                try:
                    coach = coaches[idx + j * 2]
                except IndexError:
                    break
                data = preds_df[preds_df["coach"] == coach]
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
                    text= "Energy in Bus without using reserve (80% SOC)",
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
                    text= "Energy in Bus reserve (20% SOC)",
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
