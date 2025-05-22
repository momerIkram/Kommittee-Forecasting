
# ROSCA Forecast App v6 - Final Full Version
# ✅ Includes:
# - Dynamic TAM/User Growth
# - Duration selection and allocation
# - Slot blocking toggles
# - Full lifecycle + rejoining logic
# - Forecast + Summary + Chart + Export
# - Full 60-month forecast

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Forecast App", layout="wide")
st.title("ROSCA Forecast App – v6")

# === Sidebar Config ===
st.sidebar.header("Global Setup")
total_market = st.sidebar.number_input("Total Market", value=20000000)
tam_percent = st.sidebar.slider("TAM (%)", 0, 100, 10)
start_user_percent = st.sidebar.slider("Starting User Base % of TAM", 0, 100, 10)
monthly_growth = st.sidebar.slider("Monthly Growth (%)", 0.0, 10.0, 2.0)
kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)
rest_period = st.sidebar.slider("Rest Period (months)", 0, 12, 1)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"

# === Committee Durations ===
durations_all = [3, 4, 5, 6, 8, 10]
selected_durations = st.sidebar.multiselect("Select Committee Durations", durations_all, default=[3, 4])

# === TAM Allocation ===
st.sidebar.markdown("### TAM Allocation by Duration")
duration_alloc = {}
total_alloc = 0
for d in selected_durations:
    val = st.sidebar.slider(f"{d}M", 0, 100, 0)
    duration_alloc[d] = val
    total_alloc += val

if total_alloc != 100:
    st.sidebar.error("⚠ Total allocation must equal 100%")

# === Participation Cap ===
st.sidebar.markdown("### Participation Cap Per Year")
participation_caps = {d: st.sidebar.number_input(f"{d}M Cap", 1, 12, 3 if d == 3 else 1) for d in selected_durations}

# === Slabs and Slot Fees ===
st.sidebar.markdown("### Slot Fees & Blocking")
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
slot_fees, slot_blocks = {}, {}
for d in selected_durations:
    st.sidebar.markdown(f"**{d}-Month Committee**")
    slot_fees[d], slot_blocks[d] = {}, {}
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        slot_blocks[d][s] = col1.checkbox(f"Block Slot {s}", key=f"b_{d}_{s}")
        slot_fees[d][s] = col2.number_input(f"Fee% S{s}", 0, 100, max(0, 11 - s), key=f"f_{d}_{s}")

# === Calculations ===
start_users = total_market * (tam_percent / 100) * (start_user_percent / 100)
users_list = [start_users]
rejoin_tracker = [0] * 100
rows = []

for m in range(1, 61):
    prev_users = users_list[-1]
    new_users = prev_users * (1 + monthly_growth / 100)
    rejoining = rejoin_tracker[m]
    total_users = new_users + rejoining
    users_list.append(total_users)

    for d in selected_durations:
        if duration_alloc[d] == 0:
            continue
        users_d = total_users * (duration_alloc[d] / 100)
        users_per_slab = users_d / len(slabs)

        if m + d + rest_period < len(rejoin_tracker):
            rejoin_tracker[m + d + rest_period] += users_d

        for slab in slabs:
            for slot in range(1, d + 1):
                if slot_blocks[d][slot]:
                    users = deposit = fee_collected = nii = profit = 0
                else:
                    users = users_per_slab
                    deposit = users * slab * d
                    fee = slot_fees[d][slot]
                    fee_collected = deposit * (fee / 100) if fee_upfront else 0
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    profit = fee_collected + nii - (deposit * default_rate / 100)

                rows.append({
                    "Month": m, "Year": (m - 1) // 12 + 1, "Duration": d, "Slab": slab,
                    "Slot": slot, "Users": users, "Blocked": slot_blocks[d][slot],
                    "Fee %": slot_fees[d][slot], "Deposit": deposit,
                    "Fee Collected": fee_collected, "NII": nii, "Profit": profit,
                    "Rejoining Customers": rejoining if slot == 1 and slab == slabs[0] else 0
                })

df = pd.DataFrame(rows)
summary = df.groupby("Year")[["Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index() if not df.empty else pd.DataFrame()

# === Display ===
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
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Forecast")
            summary.to_excel(writer, index=False, sheet_name="Summary")
        st.download_button("Download Excel", out.getvalue(), "rosca_forecast_v6.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
