
# ROSCA Forecast App v6 – FIXED VERSION
# ✅ Fixes:
# - NameError: fee now defined when slot is blocked
# - Excel Export: Use xlsxwriter and handle engine loading safely

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Forecast App v6", layout="wide")
st.title("ROSCA Forecast App – v6 (Fixed)")

# --- Configuration ---
st.sidebar.header("Global Configuration")
total_market = st.sidebar.number_input("Total Market", value=20000000)
tam_pct = st.sidebar.slider("TAM %", 0, 100, 10)
start_user_pct = st.sidebar.slider("Initial Users (% of TAM)", 0, 100, 10)
growth_rate = st.sidebar.slider("Monthly Growth %", 0.0, 10.0, 2.0)
kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)
rest_period = st.sidebar.slider("Rest Period (months)", 0, 12, 1)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"

durations = [3, 4, 5, 6, 8, 10]
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]

# --- Duration Allocation ---
st.sidebar.markdown("### Committee Duration Allocation (%)")
duration_alloc = {}
total_alloc = 0
for d in durations:
    val = st.sidebar.slider(f"{d}-Month", 0, 100, 0)
    duration_alloc[d] = val
    total_alloc += val
if total_alloc != 100:
    st.sidebar.error("⚠ Duration Allocation must total 100%")

# --- Slab Allocation ---
st.sidebar.markdown("### Slab Distribution (%) by Duration")
slab_alloc = {}
for d in durations:
    slab_alloc[d] = {}
    st.sidebar.markdown(f"**{d}-Month Committee**")
    slab_total = 0
    for s in slabs:
        v = st.sidebar.slider(f"{d}M – {s}", 0, 100, 0)
        slab_alloc[d][s] = v
        slab_total += v
    if duration_alloc[d] > 0 and slab_total != 100:
        st.sidebar.error(f"⚠ Slab % for {d}M ≠ 100%")

# --- Slot Fees & Blocking ---
st.sidebar.markdown("### Slot Fees & Blocking")
slot_fees, slot_block = {}, {}
for d in durations:
    slot_fees[d], slot_block[d] = {}, {}
    st.sidebar.markdown(f"**{d}-Month Slots**")
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        slot_block[d][s] = col1.checkbox(f"Block Slot {s}", value=False, key=f"b_{d}_{s}")
        slot_fees[d][s] = col2.number_input(f"Fee% S{s}", 0, 100, max(0, 11 - s), key=f"f_{d}_{s}")

# --- Forecast Logic ---
initial_users = total_market * (tam_pct / 100) * (start_user_pct / 100)
users_series = [initial_users]
rejoin_schedule = [0] * 100
records = []

for m in range(1, 61):
    base = users_series[-1]
    growth = base * (growth_rate / 100)
    rejoin = rejoin_schedule[m]
    total_users = base + growth + rejoin
    users_series.append(total_users)

    for d in durations:
        if duration_alloc[d] == 0:
            continue
        users_d = total_users * (duration_alloc[d] / 100)
        for slab in slabs:
            if slab_alloc[d][slab] == 0:
                continue
            slab_users = users_d * (slab_alloc[d][slab] / 100)
            users_per_slot = slab_users
            if m + d + rest_period < len(rejoin_schedule):
                rejoin_schedule[m + d + rest_period] += slab_users

            for slot in range(1, d + 1):
                if slot_block[d][slot]:
                    users = deposit = fee_col = nii = profit = fee = 0
                else:
                    users = users_per_slot
                    deposit = users * slab * d
                    fee = slot_fees[d][slot]
                    fee_col = deposit * (fee / 100) if fee_upfront else 0
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    profit = fee_col + nii - (deposit * default_rate / 100)

                records.append({
                    "Month": m, "Year": (m - 1) // 12 + 1, "Duration": d, "Slab": slab,
                    "Slot": slot, "Users": users, "Deposit": deposit, "Fee %": fee,
                    "Fee Collected": fee_col, "NII": nii, "Profit": profit,
                    "Blocked": slot_block[d][slot],
                    "Rejoining Customers": rejoin if slot == 1 and slab == slabs[0] else 0
                })

df = pd.DataFrame(records)
monthly = df.groupby("Month")[["Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index()
yearly = df.groupby("Year")[["Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Forecast", "Monthly Summary", "Yearly Summary", "Charts", "Export"])
with tab1: st.dataframe(df)
with tab2: st.dataframe(monthly)
with tab3: st.dataframe(yearly)
with tab4:
    if not df.empty:
        st.line_chart(monthly.set_index("Month")[["Fee Collected", "NII", "Profit"]])
with tab5:
    try:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Forecast")
            monthly.to_excel(writer, index=False, sheet_name="Monthly")
            yearly.to_excel(writer, index=False, sheet_name="Yearly")
        st.download_button("Download Excel", out.getvalue(), "rosca_forecast_v6.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ModuleNotFoundError:
        st.error("📦 Install 'xlsxwriter' to enable Excel export. Run: pip install xlsxwriter")
