
# ROSCA Forecast App - v6 (Final Fixed Version)
# ✅ Includes:
# - Dynamic TAM/User Growth
# - Rejoining Customer Lifecycle
# - Block/Unblock Slot Toggles
# - Monthly Duration Config
# - Grouped UI
# - Excel Export
# - Chart Scaling Fix
# - GroupBy KeyError Safeguard

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Forecast App", layout="wide")
st.title("ROSCA Forecast App - v6")

# Sidebar: Configuration
st.sidebar.header("Configuration")
total_market = st.sidebar.number_input("Total Market", value=20000000)
tam_percent = st.sidebar.slider("TAM (%)", 0, 100, 10)
start_user_percent = st.sidebar.slider("Starting User % of TAM", 0, 100, 10)
monthly_growth = st.sidebar.slider("Monthly Growth %", 0.0, 10.0, 2.0)
kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)
rest_period = st.sidebar.slider("Rest Period (months)", 0, 12, 1)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"

# Initial user calculations
initial_tam = total_market * (tam_percent / 100)
starting_users = initial_tam * (start_user_percent / 100)

# Participation Caps
durations = [3, 4, 5, 6, 8, 10]
st.sidebar.markdown("### Participation Caps")
participation_caps = {d: st.sidebar.number_input(f"{d}M", 1, 12, default) for d, default in zip(durations, [3, 2, 1, 1, 1, 1])}

# Monthly Duration Allocations
st.sidebar.markdown("### Duration Allocation by Month")
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
        st.sidebar.warning(f"Month {m} allocations ≠ 100%")

# Slabs and Slot Toggles
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
st.sidebar.markdown("### Slot Fees and Blocking")
slot_fees, slot_block = {}, {}
for d in durations:
    st.sidebar.markdown(f"**{d}M Committee**")
    slot_fees[d], slot_block[d] = {}, {}
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        slot_block[d][s] = col1.checkbox(f"Block S{s}", value=False, key=f"block_{d}_{s}")
        slot_fees[d][s] = col2.number_input(f"Fee S{s}", 0, 100, max(0, 11 - s), key=f"fee_{d}_{s}")

# Forecast Logic
user_pool = [starting_users]
rejoin_schedule = [0] * 100
records = []

for m in range(1, 61):
    prev = user_pool[-1]
    new = prev * (1 + monthly_growth / 100)
    rejoin = rejoin_schedule[m]
    total = new + rejoin
    user_pool.append(total)

    alloc = duration_allocations.get(m)
    if not alloc:
        continue

    for d in durations:
        if alloc[d] == 0:
            continue
        users_d = total * (alloc[d] / 100)
        users_per_slab = users_d / len(slabs)

        if m + d + rest_period < len(rejoin_schedule):
            rejoin_schedule[m + d + rest_period] += users_d

        for slab in slabs:
            for slot in range(1, d + 1):
                if slot_block[d][slot]:
                    deposit = fee_collected = nii = profit = users = 0
                else:
                    users = users_per_slab
                    deposit = users * slab * d
                    fee = slot_fees[d][slot]
                    fee_collected = deposit * (fee / 100) if fee_upfront else 0
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    profit = fee_collected + nii - (deposit * default_rate / 100)
                records.append({
                    "Month": m, "Year": (m - 1) // 12 + 1, "Duration": d, "Slab": slab,
                    "Slot": slot, "Users": users, "Blocked": slot_block[d][slot],
                    "Fee %": slot_fees[d][slot], "Deposit": deposit,
                    "Fee Collected": fee_collected, "NII": nii,
                    "Profit": profit, "Rejoining Customers": rejoin if slot == 1 and slab == slabs[0] else 0
                })

df = pd.DataFrame(records)

# Summary View Fix
if not df.empty and "Year" in df.columns:
    summary = df.groupby("Year")[["Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index()
else:
    summary = pd.DataFrame(columns=["Year", "Users", "Deposit", "Fee Collected", "NII", "Profit"])
    st.warning("No forecast data. Please configure allocations for at least one month.")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Forecast", "Summary", "Charts", "Export"])
with tab1:
    st.dataframe(df)
with tab2:
    st.dataframe(summary)
with tab3:
    if not df.empty:
        st.line_chart(df.groupby("Month")[["Fee Collected", "NII", "Profit"]].sum())
with tab4:
    if not df.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Forecast", index=False)
            summary.to_excel(writer, sheet_name="Summary", index=False)
        st.download_button("Download Excel", buffer.getvalue(), "rosca_forecast_v6.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
