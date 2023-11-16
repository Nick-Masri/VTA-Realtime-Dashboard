import math
import yaml
import json
import altair as alt
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
from page_files.dashboard import get_overview_df
# from pgbm.torch import PGBM
from pgbm import PGBM
from scipy.stats import norm

##########################################################
# Setup
##########################################################

# hide append warning
# TODO: fix append and other warning's it's bringing up
import warnings

# currently unused but functions for predicting energy consumption
def energy_predictions():
    warnings.simplefilter(action="ignore", category=FutureWarning)

    # get config settings from YAML
    with open("chargeopt/config.yml", "r") as f:
        config = yaml.safe_load(f)

    # Convert the data to a JSON string
    config_json = json.dumps(config)

    # Mileage Data
    mileages = {"7774": 105.9, "7773": 167.3, "7772": 145.9, "7771": 107.0, "7072": 112.1}
    serving, charging, idle, offline, df = get_overview_df()
    ebec_input = df
    ebec_input = ebec_input.rename(columns={"soc": "start_per", "vehicle": "Vehicle"})
    ebec_input = ebec_input[["Vehicle", "start_per", "created_at"]]
    ebec_input['month'] = ebec_input['created_at'].dt.month
    ebec_input['start_per'] = ebec_input['start_per'].astype(float).round(2)
    ebec_input.drop(columns=['created_at'], inplace=True)
    # ebec_input = pd.read_csv("output.csv", index_col=0)
    # ebec_input = ebec_input.rename(columns={"SOC (%)": "start_per"})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("# Input Data")
        st.dataframe(ebec_input, use_container_width=True, hide_index=True)

    # st.markdown("## Energy Consumption Predictions")
    # prepare data
    prob_data = pd.DataFrame(
        columns=["coach", "block", "Safe Prob.", "safe_prob", "Overall Prob.", "prob"]
    )

    ebec_final = ebec_input[["start_per", "month"]]
    ebec_final["start_per"] = ebec_final["start_per"].astype(float)
    model_new = PGBM()
    model_new.load("ML_models/model2.pt")

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
    preds_df = pd.DataFrame(columns=["coach", "block", "pred_eff", "pred_kwh", "type"])
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
                    type = "low"
                elif idx == 1:
                    type = "mid"
                else:
                    type = "high"

                temp = pd.DataFrame(
                    {
                        "coach": coach,
                        "block": block,
                        "pred_eff": round(pred, 3),
                        "pred_kwh": round(pred * miles, 3),
                        "type": type,
                        "mean": mean,
                        "var": var,
                    }, index=[0])

                preds_df = pd.concat([preds_df, temp], ignore_index=True)

    with col2:
        st.write("# Predictions")
        st.info("TODO: have low, mid and high all in one row")
        st.dataframe(preds_df, use_container_width=True, hide_index=True)

    fig, ax = plt.subplots(1, len(coaches), figsize=(10, 40))
    N_series = 3
    coaches = sorted(coaches)
    n_coaches = ebec_final.shape[0]
    preds_df.type = pd.Categorical(
        preds_df.type, categories=["high", "mid", "low"], ordered=True
    )
    nrows = math.ceil(n_coaches / 2)
    preds_df = preds_df.sort_values("type")
    preds_df.coach = preds_df.coach.astype(int)
    ebec_input.Vehicle = ebec_input.Vehicle.astype(int)

    # generate data
    for j in range(nrows):
        cols = st.columns(2)
        for idx, col in enumerate(cols):
            with col:
                try:
                    coach = int(coaches[idx + j * 2])
                except IndexError:
                    break
                data = preds_df[preds_df["coach"] == coach]
                colors = list(sns.color_palette())
                pivoted = preds_df.pivot(
                    index=["coach", "block"], columns="type", values="pred_kwh"
                ).reset_index()
                pivoted["y2"] = pivoted.high - pivoted.low
                pivoted_eff = preds_df.pivot(
                    index=["coach", "block"], columns="type", values="pred_eff"
                ).reset_index()
                pivoted_eff["y2"] = pivoted.high - pivoted.low

                # ebec_input['Vehicle'] = ebec_input['Vehicle'].astype(str)
                current_soc = float(
                    ebec_input[ebec_input["Vehicle"] == coach]["start_per"].values[0] / 100
                )
                # st.write(current_soc)
                safe = 440 * (current_soc - 0.2)
                max_amt = 440 * current_soc
                mids = preds_df.query("type == 'mid' and coach == @coach")

                for _, val in mids.iterrows():
                    block = val["block"]
                    miles = mileages[block]

                    safe_kwhs_to_go = 440 * (current_soc - 0.2)  # kwhs left in tank
                    safe_eff = safe_kwhs_to_go / miles  # eff
                    safe_prob = norm.cdf(safe_eff, val["pred_eff"], val["var"] ** 0.5)

                    kwhs_to_go = 440 * current_soc  # kwhs left in tank
                    eff = kwhs_to_go / miles  # eff
                    prob = norm.cdf(eff, val["pred_eff"], val["var"] ** 0.5)
                    temp = pd.DataFrame({
                        "coach": coach,
                        "block": block,
                        "Safe Prob.": "{}%".format(int(safe_prob * 100)),
                        "safe_prob": safe_prob,
                        "Overall Prob.": "{}%".format(int(prob * 100)),
                        "prob": prob,
                    }, index=[0])
                    prob_data = pd.concat([prob_data, temp], ignore_index=True)
                prob_data = prob_data.sort_values("block", ascending=True)

                # TODO: rewrite table
                # TODO: add in optimization predictions

    with col3:
        st.write("# Probabilities")
        st.info("TODO: column config to look better (for all 3 cols)")
        st.dataframe(prob_data[['coach', 'block', 'Safe Prob.', 'Overall Prob.']].sort_values(by=['coach', 'block'], ascending=[True, True]), 
                     use_container_width=True, hide_index=True)

    # Energy efficiency by bus on different routes
    for j in range(nrows):
        cols = st.columns(2)
        for idx, col in enumerate(cols):
            with col:
                try:
                    coach = int(coaches[idx + j * 2])
                except IndexError:
                    break
                data = preds_df[preds_df["coach"] == coach]
                st.markdown("## Coach: {}".format(coach))
                colors = list(sns.color_palette())

                # point chart for mid
                chart = (
                    alt.Chart(data[data.type == "mid"])
                    .mark_point(filled=True, size=75, color="black")
                    .encode(
                        x=alt.X(
                            "block",
                            scale=alt.Scale(paddingOuter=0.2, paddingInner=0.2),
                        ),
                        y=alt.Y(
                            "pred_kwh",
                            stack=None,
                            sort="ascending",
                            scale=alt.Scale(domain=[0, 600]),
                            axis=alt.Axis(),
                            title="Predicted Energy Consumption (kWh)",
                        ),
                    )
                )

                pivoted = preds_df.pivot(
                    index=["coach", "block"], columns="type", values="pred_kwh"
                ).reset_index()
                pivoted["y2"] = pivoted.high - pivoted.low

                # error bars
                chart2 = (
                    alt.Chart(pivoted.query("coach == @coach"))
                    .mark_errorbar(ticks=True)
                    .encode(
                        x=alt.X("block:N"),
                        y=alt.Y(
                            "low",
                            stack=None,
                            sort="ascending",
                            scale=alt.Scale(domain=[0, 600]),
                            title="",
                        ),
                        y2=alt.Y2("high"),
                    )
                )
                # st.write(pivoted.query("coach == @coach"))
                current_soc = float(
                    ebec_input[ebec_input["Vehicle"] == coach]["start_per"].values[0] / 100
                )
                safe = 440 * (current_soc - 0.2)
                max_amt = 440 * current_soc

                cutoff = pd.DataFrame(
                    {
                        "start": [0, safe, max_amt],
                        "stop": [safe, max_amt, 600],
                    }
                )
                cutoff_new = pd.DataFrame(columns=["start", "stop", "block"])
                for idx, row in cutoff.iterrows():
                    for block in data.block.unique():
                        row_dict = row.to_dict()  # Convert row to a dictionary
                        row_dict["block"] = block  # Update the "block" value
                        cutoff_new = cutoff_new.append(row_dict, ignore_index=True)  # Append to DataFrame

                cutoff = cutoff_new

                # Create the rectangles to shade the regions
                rect1 = (
                    alt.Chart(cutoff[cutoff["stop"] == safe])
                    .mark_rect(color="green", opacity=0.03)
                    .encode(
                        y="start:Q",
                        y2="stop:Q",
                    )
                )
                rect2 = (
                    alt.Chart(
                        cutoff[(cutoff["start"] >= safe) & (cutoff["stop"] <= max_amt)]
                    )
                    .mark_rect(color="yellow", opacity=0.05)
                    .encode(y="start:Q", y2="stop:Q")
                )

                rect3 = (
                    alt.Chart(cutoff[cutoff["start"] >= max_amt])
                    .mark_rect(color="red", opacity=0.05)
                    .encode(y="start:Q", y2="stop:Q")
                )

                final_chart = alt.layer(rect1, rect2, rect3, chart, chart2).configure_axis()
                st.altair_chart(final_chart, use_container_width=True)
                mids = preds_df.query("type == 'mid' and coach == @coach")

    # legend
    j = 0
    cols = st.columns(2)

    for idx, col in enumerate(cols):
        with col:
            try:
                coach = int(coaches[idx + j * 2])
            except IndexError:
                break
            data = preds_df[preds_df["coach"] == coach]
            st.markdown("## Legend")

            current_soc = float(
                ebec_input[ebec_input["Vehicle"] == coach]["start_per"].values[0] / 100
            )
            safe = 440 * (current_soc - 0.2)
            max_amt = 440 * current_soc

            cutoff = pd.DataFrame(
                {
                    "start": [0, safe, max_amt],
                    "stop": [safe, max_amt, 600],
                }
            )
            
            cutoff_new = pd.DataFrame(columns=["start", "stop", "block"])
            for idx, row in cutoff.iterrows():
                for block in data.block.unique():
                    row_dict = row.to_dict()  # Convert row to a dictionary
                    row_dict["block"] = block  # Update the "block" value
                    cutoff_new = cutoff_new.append(row_dict, ignore_index=True)  # Append to DataFrame

            cutoff = cutoff_new

            # Create the rectangles to shade the regions
            rect1 = (
                alt.Chart(cutoff[cutoff["stop"] == safe])
                .mark_rect(color="green", opacity=0.03)
                .encode(
                    y=alt.Y("start:Q", title="Predicted Energy Consumption (kWh)"),
                    y2="stop:Q",
                )
            )

            rect1_text = rect1.mark_text(
                opacity=0.4,
                align="center",
                baseline="top",
                dy=-80,
                fontSize=10,
                text="Energy in Bus without using reserve",
                fontWeight=100,
                lineBreak="\n",
            )

            rect2 = (
                alt.Chart(cutoff[(cutoff["start"] >= safe) & (cutoff["stop"] <= max_amt)])
                .mark_rect(color="yellow", opacity=0.05)
                .encode(y="start:Q", y2="stop:Q")
            )

            rect2_text = rect2.mark_text(
                opacity=0.4,
                align="center",
                baseline="top",
                dy=-30,
                fontSize=10,
                text="Energy in Bus + reserve",
                fontWeight=100,
            )

            rect3 = (
                alt.Chart(cutoff[cutoff["start"] >= max_amt])
                .mark_rect(color="red", opacity=0.05)
                .encode(y="start:Q", y2="stop:Q")
            )

            rect3_text = rect3.mark_text(
                opacity=0.4,
                align="center",
                baseline="top",
                dy=-40,
                fontSize=10,
                text="Exceeds Bus Energy",
                fontWeight=100,
            )

            final_chart = alt.layer(
                rect1_text, rect1, rect2_text, rect2, rect3_text, rect3
            ).configure_axis()
            st.altair_chart(final_chart, use_container_width=True)
            break

    # horizontal line
    st.markdown(
        """<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True
    )

    # efficiency by bus
    st.subheader("Predicted Energy Efficiency By Bus")
    kwhs_chart1 = (
        alt.Chart(preds_df[preds_df.type == "mid"])
        .mark_point(filled=True, size=130, color="black")
        .encode(
            x=alt.X(
                "pred_eff",
                stack=None,
                sort="ascending",
                scale=alt.Scale(domain=[0, 3.5]),
                axis=alt.Axis(labelPadding=0),
                title="Predicted Efficiency (kWh/mile)",
            ),
            y=alt.Y("coach:N", scale=alt.Scale(padding=5)),
        )
    )

    kwhs_chart2 = (
        alt.Chart(pivoted_eff)
        .mark_errorbar(ticks=True)
        .encode(
            x=alt.X(
                "low",
                stack=None,
                sort="ascending",
                scale=alt.Scale(domain=[0, 3.5]),
                axis=alt.Axis(labelPadding=0),
                title="",
            ),
            x2=alt.X2("high"),
            y=alt.Y("coach:N", scale=alt.Scale(padding=5)),
        )
    )

    kwhs_chart = alt.layer(kwhs_chart1, kwhs_chart2).configure(padding=1)
    st.altair_chart(kwhs_chart, use_container_width=True)

    # print overall summary
    st.markdown(
        """<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True
    )
    st.subheader("Completition Probabillty of Bus-Block Pairs")
    st.write(
        "Safe Prob: probability bus completes block with at least 20% remaining (for battery health)"
    )
    st.write("Overall Prob: probability bus completes block")
    option = st.selectbox("Probability completion method", ("Safe Prob.", "Overall Prob."))

    # prob_data.rename("block_{}".format, inplace=True)
    # prob_data.rename("coach_{}".format, inplace=True, axis=1)
    st.write(
        "{} of completion of all coach/block pairings given current SOC".format(option)
    )
    st.dataframe(
        prob_data.sort_values(by=["coach", "block"], ascending=[True, True])[
            ["coach", "block", option]
        ].pivot(index="block", columns="coach", values=option),
        use_container_width=True,
    )