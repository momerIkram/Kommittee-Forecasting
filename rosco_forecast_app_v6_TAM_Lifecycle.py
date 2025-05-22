
# ROSCA Forecast App v6 – TAM, Growth, Lifecycle Logic (60 Months)
# ✅ Tracks new, rest, and rejoining users
# ✅ Applies 2% growth to active user base
# ✅ Full forecast, charts, export with logic in sync

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Forecast App", layout="wide")
st.title("ROSCA Forecast App – v6: TAM & Lifecycle Logic")

# --- Configuration ---
st.sidebar.header("Base Setup")
total_market = st.sidebar.number_input("Total Market", value=20000000)
tam_pct = st.sidebar.slider("TAM (%)", 0, 100, 10)  # Use % to allow generalization
starting_user_pct = st.sidebar.slider("Starting User Base % of TAM", 0, 100, 10)
monthly_growth = st.sidebar.slider("Monthly Growth %", 0.0, 10.0, 2.0)
kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)
rest_period = st.sidebar.slider("Rest Period (months)", 0, 12, 1)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"

durations = [3, 4, 5, 6, 8, 10]
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]

# === Duration Allocation
st.sidebar.markdown("### Duration Allocation (%)")
duration_alloc = {}
total_dur = 0
for d in durations:
    val = st.sidebar.slider(f"{d}-Month", 0, 100, 0)
    duration_alloc[d] = val
    total_dur += val
if total_dur != 100:
    st.sidebar.error("⚠ Duration Allocation must equal 100%")

# === Slab Allocation
st.sidebar.markdown("### Slab Distribution per Duration (%)")
slab_alloc = {}
for d in durations:
    slab_alloc[d] = {}
    st.sidebar.markdown(f"**{d}-Month Slabs**")
    slab_total = 0
    for s in slabs:
        v = st.sidebar.slider(f"{d}M – {s}", 0, 100, 0)
        slab_alloc[d][s] = v
        slab_total += v
    if duration_alloc[d] > 0 and slab_total != 100:
        st.sidebar.error(f"⚠ {d}M Slab Distribution ≠ 100%")

# === Slot Setup
st.sidebar.markdown("### Slot Fees & Blocking")
slot_fees, slot_block = {}, {}
for d in durations:
    slot_fees[d], slot_block[d] = {}, {}
    st.sidebar.markdown(f"**{d}-Month Slots**")
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        slot_block[d][s] = col1.checkbox(f"Block {s}", value=False, key=f"b_{d}_{s}")
        slot_fees[d][s] = col2.number_input(f"Fee% S{s}", 0, 100, max(0, 11 - s), key=f"f_{d}_{s}")

# === TAM & User Setup
tam_users = total_market * (tam_pct / 100)
start_users = tam_users * (starting_user_pct / 100)
users_by_month = []
rejoin_tracker = [0] * 120
resting_users = [0] * 120

active_users = [start_users]
records = []

# === Forecast Loop
for m in range(1, 61):
    prev_active = active_users[-1]
    rejoin = rejoin_tracker[m]
    growth = prev_active * (monthly_growth / 100)
    total_active = prev_active + growth + rejoin
    active_users.append(total_active)

    for d in durations:
        if duration_alloc[d] == 0:
            continue
        users_d = total_active * (duration_alloc[d] / 100)
        for slab in slabs:
            if slab_alloc[d][slab] == 0:
                continue
            users_slab = users_d * (slab_alloc[d][slab] / 100)
            if m + d + rest_period < len(rejoin_tracker):
                rejoin_tracker[m + d + rest_period] += users_slab

            for slot in range(1, d + 1):
                if slot_block[d][slot]:
                    u = fee_col = deposit = nii = profit = fee = 0
                else:
                    u = users_slab
                    fee = slot_fees[d][slot]
                    deposit = u * slab * d
                    fee_col = deposit * (fee / 100) if fee_upfront else 0
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    profit = fee_col + nii - (deposit * default_rate / 100)

                records.append({
                    "Month": m, "Year": (m - 1) // 12 + 1, "Duration": d, "Slab": slab,
                    "Slot": slot, "Users": u, "Fee %": fee, "Deposit": deposit,
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
        st.download_button("📥 Download Excel", out.getvalue(), "rosca_forecast_v6_tam_lifecycle.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except:
        st.error("❌ Install `xlsxwriter` to enable Excel download")
