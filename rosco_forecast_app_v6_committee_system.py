
# ROSCA Forecast App v6 - Committee Forecasting System Implementation
# ✅ Supports TAM, monthly + yearly growth, rejoining, rest, slot blocking, UI config, 60-month forecast, and Excel export

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Committee Forecast", layout="wide")
st.title("ROSCA Committee Forecast App – v6")

# --- 1. Configurable TAM and Growth Inputs ---
st.sidebar.header("📊 Market & TAM Setup")
total_market = st.sidebar.number_input("Total Market Size", value=20000000)
tam = st.sidebar.number_input("TAM (Total Addressable Market)", value=2000000)
start_pct = st.sidebar.slider("Starting % of TAM (Month 1)", 0, 100, 10)
monthly_growth = st.sidebar.slider("Monthly Growth Rate (%)", 0.0, 10.0, 2.0)
yearly_growth = st.sidebar.slider("Yearly Growth Rate (%)", 0.0, 20.0, 5.0)

start_users = tam * (start_pct / 100)
rest_period = st.sidebar.slider("Rest Period After Committee (months)", 0, 12, 1)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"

kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)

# --- 2. Committee Duration Setup ---
durations_all = [3, 4, 5, 6, 8, 10]
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
st.sidebar.header("⏱️ Committee Durations")
selected_durations = st.sidebar.multiselect("Select Available Durations", durations_all, default=[3, 4, 6])

# TAM Allocation across selected durations
st.sidebar.markdown("### TAM Allocation Across Durations (%)")
duration_alloc = {}
total_dur_alloc = 0
for d in selected_durations:
    val = st.sidebar.slider(f"{d}-Month", 0, 100, 0)
    duration_alloc[d] = val
    total_dur_alloc += val
if total_dur_alloc != 100:
    st.sidebar.error("⚠ Total allocation must equal 100%")

# Slab Allocation per Duration
st.sidebar.markdown("### Slab Distribution per Duration (%)")
slab_alloc = {}
for d in selected_durations:
    slab_alloc[d] = {}
    st.sidebar.markdown(f"**{d}-Month Slabs**")
    slab_total = 0
    for s in slabs:
        v = st.sidebar.slider(f"{d}M – {s}", 0, 100, 0)
        slab_alloc[d][s] = v
        slab_total += v
    if slab_total != 100:
        st.sidebar.error(f"⚠ {d}M Slab total ≠ 100%")

# Slot Fee and Blocking
st.sidebar.markdown("### 🎯 Slot Fee % and Blocking")
slot_fees, slot_blocked = {}, {}
for d in selected_durations:
    slot_fees[d], slot_blocked[d] = {}, {}
    st.sidebar.markdown(f"**{d}-Month Slots**")
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        slot_blocked[d][s] = col1.checkbox(f"Block S{s}", value=False, key=f"block_{d}_{s}")
        slot_fees[d][s] = col2.number_input(f"Fee% S{s}", 0, 100, max(0, 11 - s), key=f"fee_{d}_{s}")

# --- Forecast Engine Variables ---
monthly_users = []
rejoin_schedule = [0] * 120
records = []

total_users = start_users
current_users = start_users
tam_cap = tam
used_users = 0

# --- 60-Month Forecast Loop ---
for m in range(1, 61):
    rejoining = rejoin_schedule[m]
    growth_users = current_users * (monthly_growth / 100)

    if m in [13, 25, 37, 49]:
        growth_users += tam * (yearly_growth / 100)

    # Avoid exceeding TAM cap
    if used_users + growth_users > tam:
        growth_users = max(0, tam - used_users)

    current_users = growth_users + rejoining
    used_users += growth_users
    if current_users < 0:
        current_users = 0

    for d in selected_durations:
        if duration_alloc[d] == 0: continue
        users_d = current_users * (duration_alloc[d] / 100)

        for slab in slabs:
            if slab_alloc[d][slab] == 0: continue
            slab_users = users_d * (slab_alloc[d][slab] / 100)
            users_per_slot = slab_users

            if m + d + rest_period < len(rejoin_schedule):
                rejoin_schedule[m + d + rest_period] += slab_users

            for slot in range(1, d + 1):
                if slot_blocked[d][slot]:
                    users = deposit = fee_col = nii = profit = fee = 0
                else:
                    users = users_per_slot
                    deposit = users * slab * d
                    fee = slot_fees[d][slot]
                    fee_col = deposit * (fee / 100) if fee_upfront else 0
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    profit = fee_col + nii - (deposit * default_rate / 100)

                records.append({
                    "Month": m, "Year": (m - 1) // 12 + 1,
                    "Duration": d, "Slab": slab, "Slot": slot,
                    "New Users": growth_users if slot == 1 and slab == slabs[0] else 0,
                    "Rejoining Users": rejoining if slot == 1 and slab == slabs[0] else 0,
                    "Active Users": users,
                    "Deposit": deposit, "Fee %": fee,
                    "Fee Collected": fee_col, "NII": nii, "Profit": profit,
                    "Blocked": slot_blocked[d][slot]
                })

df = pd.DataFrame(records)
monthly = df.groupby("Month")[["Active Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index()
yearly = df.groupby("Year")[["Active Users", "Deposit", "Fee Collected", "NII", "Profit"]].sum().reset_index()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Forecast", "Monthly Summary", "Yearly Summary", "Charts", "Export"])
with tab1: st.dataframe(df)
with tab2: st.dataframe(monthly)
with tab3: st.dataframe(yearly)
with tab4:
    if not df.empty:
        st.line_chart(monthly.set_index("Month")[["Fee Collected", "NII", "Profit"]])
with tab5:
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Forecast", index=False)
            monthly.to_excel(writer, sheet_name="Monthly", index=False)
            yearly.to_excel(writer, sheet_name="Yearly", index=False)
        st.download_button("📥 Download Excel", output.getvalue(), "rosco_forecast_committee_v6.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except:
        st.error("❌ Install 'xlsxwriter' to enable export.")
