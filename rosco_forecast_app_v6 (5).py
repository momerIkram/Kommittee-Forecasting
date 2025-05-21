
# ROSCA Forecast App v6 - FINAL COMPLETE VERSION
# Includes full lifecycle logic, TAM/user growth, block/unblock UI, Excel export, chart scaling, and all UI features

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Forecast App", layout="wide")
st.title("ROSCA Forecast App - v6")

# === Global Inputs ===
st.sidebar.header("Configuration")
total_market = st.sidebar.number_input("Total Market", value=20000000)
tam_percent = st.sidebar.slider("TAM (%)", 0, 100, 10)
start_user_percent = st.sidebar.slider("Starting User % of TAM", 0, 100, 10)
monthly_growth = st.sidebar.slider("Monthly Growth %", 0.0, 10.0, 2.0)

initial_tam = total_market * (tam_percent / 100)
starting_users = initial_tam * (start_user_percent / 100)

kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)
rest_period = st.sidebar.slider("Rest Period (months)", 0, 12, 1)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"

# === Participation Caps ===
durations = [3, 4, 5, 6, 8, 10]
st.sidebar.markdown("### Participation Caps")
participation_caps = {d: st.sidebar.number_input(f"{d}M", 1, 12, default) for d, default in zip(durations, [3, 2, 1, 1, 1, 1])}

# === Duration Allocation by Month ===
st.sidebar.markdown("### Duration Allocation Per Month")
months = list(range(1, 61))
selected_months = st.sidebar.multiselect("Select Months", months, default=[1])
duration_allocations = {}
for m in selected_months:
    st.sidebar.markdown(f"Month {m}")
    alloc = {}
    total = 0
    for d in durations:
        alloc[d] = st.sidebar.slider(f"{d}M - Month {m}", 0, 100, 0)
        total += alloc[d]
    duration_allocations[m] = alloc
    if total != 100:
        st.sidebar.warning(f"Month {m} allocation ≠ 100%")

# === Slab + Toggle-Based Slot Blocking ===
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
st.sidebar.markdown("### Fee & Slot Blocking (Toggle)")

slot_fees = {}
slot_block = {}

for d in durations:
    st.sidebar.markdown(f"**{d}-Month Committee**")
    slot_fees[d] = {}
    slot_block[d] = {}
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        with col1:
            block = st.checkbox(f"Block Slot {s}", key=f"block_{d}_{s}")
        with col2:
            fee = st.number_input(f"Fee % (S{s})", 0, 100, max(0, 11 - s), key=f"fee_{d}_{s}")
        slot_block[d][s] = block
        slot_fees[d][s] = fee

# === Forecast Engine ===
forecast_months = 60
user_base = [starting_users]
rejoin_track = [0] * (forecast_months + 24)
records = []

for m in range(1, forecast_months + 1):
    prev_users = user_base[-1]
    new_users = prev_users * (1 + monthly_growth / 100)
    rejoining = rejoin_track[m] if m < len(rejoin_track) else 0
    total_users = new_users + rejoining
    user_base.append(total_users)

    alloc = duration_allocations.get(m, None)
    if not alloc:
        continue

    for d in durations:
        if alloc[d] == 0:
            continue

        users_d = total_users * (alloc[d] / 100)
        users_per_slab = users_d / len(slabs)

        if m + d + rest_period < len(rejoin_track):
            rejoin_track[m + d + rest_period] += users_d

        for slab in slabs:
            for slot in range(1, d + 1):
                if slot_block[d][slot]:
                    deposit = fee_collected = nii = profit = users = 0
                else:
                    users = users_per_slab
                    deposit = users * slab * d
                    fee_pct = slot_fees[d][slot]
                    fee_collected = deposit * (fee_pct / 100) if fee_upfront else 0
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    profit = fee_collected + nii - (deposit * default_rate / 100)

                records.append({
                    "Month": m,
                    "Year": (m - 1) // 12 + 1,
                    "Duration": d,
                    "Slab": slab,
                    "Slot": slot,
                    "Users": users,
                    "Blocked": slot_block[d][slot],
                    "Fee %": slot_fees[d][slot],
                    "Deposit": deposit,
                    "Fee Collected": fee_collected,
                    "NII": nii,
                    "Profit": profit,
                    "Rejoining Customers": rejoining if slot == 1 and slab == slabs[0] else 0
                })

df = pd.DataFrame(records)
summary = df.groupby("Year")[["Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index()

# === UI Tabs ===
tab1, tab2, tab3, tab4 = st.tabs(["Forecast", "Summary", "Charts", "Export"])
with tab1:
    st.dataframe(df)
with tab2:
    st.dataframe(summary)
with tab3:
    st.line_chart(df.groupby("Month")[["Fee Collected", "NII", "Profit"]].sum())
with tab4:
    excel = io.BytesIO()
    with pd.ExcelWriter(excel, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Forecast")
        summary.to_excel(writer, index=False, sheet_name="Summary")
    st.download_button("Download Excel", excel.getvalue(), "rosca_forecast_v6.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
