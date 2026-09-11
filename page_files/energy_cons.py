import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import t

from calls.visual_crossing import weather_is_estimated
from components.consumption_model import (
    DEG_FREE, completion_probability, predict_batch, predict_detail,
)
from page_files.dashboard import get_overview_df

COACHES = [7501, 7502, 7503, 7504, 7505, 9501, 9502, 9503, 9504, 9505]
RESERVE_SOC = 20  # buses are not dispatched below this


@st.cache_data(show_spinner=False)
def load_blocks(approved_only=True):
    df = pd.read_csv('data_files/block_miles.csv', header=1, delimiter=';')
    df = df[['BLOCK', 'TOTAL MILES']]
    df = df[df['TOTAL MILES'] > 0]
    if approved_only:
        # the approved service blocks, 476 through 6081
        df = df.loc[50:79]
    return df.reset_index(drop=True)


def _live_soc():
    """Current SOC per coach, or None when the fleet feed has nothing."""
    serving, charging, idle, offline, df = get_overview_df()
    if df is None or df.empty:
        return None
    soc = df[['vehicle', 'soc']].copy()
    soc['vehicle'] = pd.to_numeric(soc['vehicle'], errors='coerce')
    soc['soc'] = pd.to_numeric(soc['soc'], errors='coerce')
    soc = soc.dropna()
    return dict(zip(soc['vehicle'].astype(int), soc['soc']))


def _weather_note():
    """Covered by the demonstration banner in main.py."""
    return


def show_energy_cons():
    single, fleet = st.tabs(["Vehicle & block", "Fleet overview"])
    with single:
        _single_view()
    with fleet:
        _fleet_view()


# --------------------------------------------------------------------------
# Vehicle & block
# --------------------------------------------------------------------------

def _single_view():
    controls = st.container(horizontal=True)
    coach = controls.selectbox('Vehicle', COACHES, key='v')
    approved = controls.toggle('Approved blocks only', value=True, key='approved_single')
    use_live = controls.toggle('Use realtime SOC', value=True, key='live_single')

    blocks = load_blocks(approved)
    miles_by_block = blocks.set_index('BLOCK')['TOTAL MILES'].to_dict()
    block = int(controls.selectbox('Block', blocks['BLOCK'].unique(), key='block'))
    miles = miles_by_block[block]

    start_soc = None
    if use_live:
        live = _live_soc()
        if live and coach in live:
            start_soc = float(live[coach])
        else:
            st.warning("Live SOC unavailable - enter the current SOC below.")

    if start_soc is None:
        start_soc = float(st.number_input(
            'Current SOC (%)', min_value=0.0, max_value=100.0, value=80.0, step=1.0,
            key='manual_soc',
        ))

    try:
        detail = predict_detail(coach, miles, start_soc)
    except Exception as exc:
        st.error(f"Energy prediction unavailable ({exc})")
        return

    if detail is None:
        st.warning('Please enter the number of miles.')
        return

    pred, low, high = detail['pred'], detail['low'], detail['high']
    left = start_soc - pred
    prob = detail['prob']

    row = st.container(horizontal=True)
    row.metric('Current SOC', f"{start_soc:.0f}%", border=True)
    row.metric('Block mileage', f"{miles:.1f} mi", border=True)
    row.metric('Energy needed', f"{pred:.0f}%", f"{low:.0f}-{high:.0f}% range",
               delta_color='off', border=True)
    row.metric('Charge left', f"{left:.0f}%", f"{left - RESERVE_SOC:+.0f}% vs reserve",
               border=True)
    row.metric('Completion prob.', f"{prob * 100:.0f}%", border=True)

    if prob >= 0.95:
        st.success(f"Coach {coach} can complete block {block} with charge to spare.")
    elif prob >= 0.75:
        st.warning(f"Coach {coach} should complete block {block}, but the margin is thin.")
    else:
        st.error(f"Coach {coach} is unlikely to finish block {block} on the current charge.")

    left_col, right_col = st.columns(2)
    with left_col:
        with st.container(border=True):
            st.markdown("**Charge budget**")
            st.altair_chart(_budget_chart(start_soc, pred, low, high), width='stretch')
    with right_col:
        with st.container(border=True):
            st.markdown("**Where the estimate sits**")
            st.altair_chart(_distribution_chart(pred, detail['sd'], start_soc), width='stretch')

    with st.container(border=True):
        st.markdown("**Charge needed across every block**")
        st.altair_chart(_curve_chart(coach, blocks, start_soc, block), width='stretch')

    _weather_note()


def _budget_chart(start_soc, pred, low, high):
    segments = pd.DataFrame([
        {'part': 'Used by block', 'value': min(pred, start_soc), 'order': 0},
        {'part': 'Remaining', 'value': max(start_soc - pred, 0), 'order': 1},
    ])

    bars = alt.Chart(segments).mark_bar(size=46).encode(
        x=alt.X('value:Q', stack='zero', title='State of charge (%)',
                scale=alt.Scale(domain=[0, 100])),
        color=alt.Color('part:N', title=None,
                        scale=alt.Scale(domain=['Used by block', 'Remaining'],
                                        range=['#E4572E', '#009688'])),
        order=alt.Order('order:Q'),
        tooltip=[alt.Tooltip('part:N', title=''), alt.Tooltip('value:Q', format='.0f')],
    )

    span = alt.Chart(pd.DataFrame([{'low': low, 'high': high}])).mark_rule(
        strokeWidth=3, color='#37474F', opacity=0.8,
    ).encode(x='low:Q', x2='high:Q')

    reserve = alt.Chart(pd.DataFrame([{'v': RESERVE_SOC}])).mark_rule(
        color='#B71C1C', strokeDash=[5, 4],
    ).encode(x='v:Q')

    return (bars + span + reserve).properties(height=150)


def _distribution_chart(pred, sd, start_soc):
    sd = max(sd, 0.5)
    grid = np.linspace(pred - 4 * sd, pred + 4 * sd, 220)
    curve = pd.DataFrame({
        'energy': grid,
        'density': t.pdf((grid - pred) / sd, DEG_FREE) / sd,
    })
    curve['outcome'] = np.where(curve['energy'] <= start_soc, 'Completes', 'Runs short')

    area = alt.Chart(curve).mark_area(opacity=0.75).encode(
        x=alt.X('energy:Q', title='Charge the block needs (%)'),
        y=alt.Y('density:Q', title=None, axis=None),
        color=alt.Color('outcome:N', title=None,
                        scale=alt.Scale(domain=['Completes', 'Runs short'],
                                        range=['#009688', '#E4572E'])),
        tooltip=[alt.Tooltip('energy:Q', format='.0f', title='Needs')],
    )

    available = alt.Chart(pd.DataFrame([{'v': start_soc}])).mark_rule(
        color='#37474F', strokeWidth=2,
    ).encode(x='v:Q')

    label = alt.Chart(pd.DataFrame([{'v': start_soc, 'text': 'Available charge'}])).mark_text(
        align='left', dx=5, dy=-60, fontSize=11, color='#37474F',
    ).encode(x='v:Q', text='text:N')

    return (area + available + label).properties(height=150)


def _curve_chart(coach, blocks, start_soc, selected_block):
    grid = predict_batch([(coach, m) for m in blocks['TOTAL MILES']])
    grid['BLOCK'] = blocks['BLOCK'].values
    grid['feasible'] = np.where(grid['pred'] <= (start_soc - RESERVE_SOC), 'Yes', 'No')

    band = alt.Chart(grid).mark_area(opacity=0.18, color='#009688').encode(
        x=alt.X('miles:Q', title='Block distance (mi)'),
        y=alt.Y('low:Q', title='Charge needed (%)'),
        y2='high:Q',
    )
    line = alt.Chart(grid).mark_line(color='#009688', strokeWidth=2).encode(
        x='miles:Q', y='pred:Q',
    )
    points = alt.Chart(grid).mark_circle(size=70).encode(
        x='miles:Q', y='pred:Q',
        color=alt.Color('feasible:N', title='Within charge',
                        scale=alt.Scale(domain=['Yes', 'No'], range=['#009688', '#E4572E'])),
        tooltip=[alt.Tooltip('BLOCK:Q', title='Block'),
                 alt.Tooltip('miles:Q', title='Miles', format='.1f'),
                 alt.Tooltip('pred:Q', title='Needs %', format='.0f')],
    )
    usable = alt.Chart(pd.DataFrame([{'v': start_soc - RESERVE_SOC}])).mark_rule(
        color='#37474F', strokeDash=[5, 4],
    ).encode(y='v:Q')

    highlight = alt.Chart(grid[grid['BLOCK'] == selected_block]).mark_point(
        size=220, shape='diamond', color='#37474F', filled=True,
    ).encode(x='miles:Q', y='pred:Q')

    return (band + line + points + usable + highlight).properties(height=280)


# --------------------------------------------------------------------------
# Fleet overview
# --------------------------------------------------------------------------

def _fleet_view():
    controls = st.container(horizontal=True)
    approved = controls.toggle('Approved blocks only', value=True, key='approved_fleet')
    use_live = controls.toggle('Use realtime SOC', value=True, key='live_fleet')

    blocks = load_blocks(approved)
    live = _live_soc() if use_live else None

    if live:
        soc_by_coach = {c: float(live[c]) for c in COACHES if c in live}
    else:
        if use_live:
            st.warning("Live SOC unavailable - assuming a uniform charge below.")
        assumed = st.slider('Assumed SOC (%)', 0, 100, 80, key='fleet_soc')
        soc_by_coach = {c: float(assumed) for c in COACHES}

    if not soc_by_coach:
        st.info("No vehicles to report on.")
        return

    try:
        grid = predict_batch(
            [(coach, miles) for coach in soc_by_coach for miles in blocks['TOTAL MILES']]
        )
    except Exception as exc:
        st.error(f"Energy prediction unavailable ({exc})")
        return

    block_of = dict(zip(blocks['TOTAL MILES'], blocks['BLOCK']))
    grid['BLOCK'] = grid['miles'].map(block_of)
    grid['soc'] = grid['coach'].map(soc_by_coach)
    grid['prob'] = [
        completion_probability(r.pred, r.low, r.high, r.soc)
        for r in grid.itertuples()
    ]
    grid['ready'] = grid['prob'] >= 0.95

    per_coach = grid.groupby('coach').agg(
        soc=('soc', 'first'),
        blocks_ready=('ready', 'sum'),
        longest=('miles', lambda s: s[grid.loc[s.index, 'ready']].max()),
    ).reset_index()
    per_coach['longest'] = per_coach['longest'].fillna(0)

    row = st.container(horizontal=True)
    row.metric('Buses', len(soc_by_coach), border=True)
    row.metric('Average SOC', f"{np.mean(list(soc_by_coach.values())):.0f}%", border=True)
    row.metric('Blocks assessed', len(blocks), border=True)
    row.metric('Fully covered blocks',
               int(grid.groupby('BLOCK')['ready'].any().sum()), border=True)

    _weather_note()

    with st.container(border=True):
        st.markdown("**Which bus can cover which block**")
        st.caption("Probability the coach finishes the block on its current charge.")
        st.altair_chart(_heatmap(grid), width='stretch')

    left_col, right_col = st.columns(2)
    with left_col:
        with st.container(border=True):
            st.markdown("**Blocks each bus can cover**")
            st.altair_chart(_readiness_chart(per_coach), width='stretch')
    with right_col:
        with st.container(border=True):
            st.markdown("**Fleet readiness**")
            st.dataframe(
                per_coach.rename(columns={
                    'coach': 'Coach', 'soc': 'SOC (%)',
                    'blocks_ready': 'Blocks ready', 'longest': 'Longest block (mi)',
                }),
                hide_index=True, width='stretch',
                column_config={
                    'SOC (%)': st.column_config.ProgressColumn(
                        'SOC', format='%d%%', min_value=0, max_value=100),
                },
            )


def _heatmap(grid):
    return alt.Chart(grid).mark_rect().encode(
        x=alt.X('BLOCK:O', title='Block', axis=alt.Axis(labelAngle=-60)),
        y=alt.Y('coach:O', title='Coach'),
        color=alt.Color('prob:Q', title='Completion',
                        scale=alt.Scale(scheme='redyellowgreen', domain=[0, 1])),
        tooltip=[alt.Tooltip('coach:O', title='Coach'),
                 alt.Tooltip('BLOCK:O', title='Block'),
                 alt.Tooltip('miles:Q', title='Miles', format='.1f'),
                 alt.Tooltip('pred:Q', title='Needs %', format='.0f'),
                 alt.Tooltip('prob:Q', title='Completion', format='.0%')],
    ).properties(height=290)


def _readiness_chart(per_coach):
    return alt.Chart(per_coach).mark_bar(color='#009688').encode(
        x=alt.X('blocks_ready:Q', title='Blocks the bus can finish'),
        y=alt.Y('coach:O', title=None, sort='-x'),
        tooltip=[alt.Tooltip('coach:O', title='Coach'),
                 alt.Tooltip('soc:Q', title='SOC', format='.0f'),
                 alt.Tooltip('blocks_ready:Q', title='Blocks ready')],
    ).properties(height=290)
