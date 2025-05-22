
# ROSCA Forecast App v7 – Full Lifecycle + Profit Logic
# Includes:
# ✅ Configurable TAM & growth
# ✅ Monthly & yearly expansion
# ✅ Active / Resting / Rejoining / Defaulted states
# ✅ Deposit, payout, default refund, platform profit
# ✅ MoM & YoY summaries, Excel export

import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="ROSCA Forecast App v7", layout="wide")
st.title("ROSCA Forecast App – v7: Lifecycle & Profit Logic")

# --- Config: TAM & Growth
st.sidebar.header("📊 Market & Growth Setup")
total_market = st.sidebar.number_input("Total Market Size", value=20000000)
tam = st.sidebar.number_input("TAM (Addressable Market)", value=2000000)
start_pct = st.sidebar.slider("Starting % of TAM (Month 1)", 0, 100, 10)
monthly_growth = st.sidebar.slider("Monthly Growth Rate (%)", 0.0, 10.0, 2.0)
yearly_growth = st.sidebar.slider("Annual TAM Growth Multiplier (%)", 0.0, 20.0, 5.0)

# --- Config: Platform Logic
rest_period = st.sidebar.slider("Rest Period (months)", 0, 12, 1)
default_fee_pct = st.sidebar.slider("Default Fee Deducted (%)", 0.0, 100.0, 10.0)
fee_upfront = st.sidebar.radio("Fee Collected Upfront?", ["Yes", "No"]) == "Yes"
kibor = st.sidebar.slider("KIBOR (%)", 0.0, 25.0, 11.0)
spread = st.sidebar.slider("Spread (%)", 0.0, 20.0, 5.0)
default_rate = st.sidebar.slider("Default Rate (%)", 0.0, 10.0, 1.0)

# --- Committee Setup
durations = list(range(2, 11))
slabs = [1000, 2000, 5000, 10000, 15000, 20000, 25000, 50000]
st.sidebar.header("⏱️ Committee Durations")
selected_durations = st.sidebar.multiselect("Select Durations", durations, default=[3, 4, 6])

# --- TAM Allocation
st.sidebar.markdown("### TAM Allocation by Duration (%)")
duration_alloc = {}
total_alloc = 0
for d in selected_durations:
    val = st.sidebar.slider(f"{d}-Month", 0, 100, 0)
    duration_alloc[d] = val
    total_alloc += val
if total_alloc != 100:
    st.sidebar.error("⚠ Allocation must total 100%")

# --- Slab Distribution
st.sidebar.markdown("### Slab Distribution per Duration (%)")
slab_alloc = {}
for d in selected_durations:
    slab_alloc[d] = {}
    st.sidebar.markdown(f"**{d}M Slabs**")
    slab_total = 0
    for s in slabs:
        v = st.sidebar.slider(f"{d}M – {s}", 0, 100, 0)
        slab_alloc[d][s] = v
        slab_total += v
    if slab_total != 100:
        st.sidebar.error(f"⚠ {d}M Slabs ≠ 100%")

# --- Slot Fee Setup
slot_fees, slot_blocked = {}, {}
st.sidebar.markdown("### Fee % and Slot Blocking")
for d in selected_durations:
    slot_fees[d], slot_blocked[d] = {}, {}
    st.sidebar.markdown(f"**{d}M Committee**")
    for s in range(1, d + 1):
        col1, col2 = st.sidebar.columns(2)
        slot_blocked[d][s] = col1.checkbox(f"Block S{s}", value=False, key=f"b_{d}_{s}")
        slot_fees[d][s] = col2.number_input(f"Fee% S{s}", 0, 100, max(0, 11 - s), key=f"f_{d}_{s}")

# --- Lifecycle Simulation
start_users = tam * (start_pct / 100)
records, rejoin_schedule = [], [0] * 120
current_users = start_users
total_users_used = start_users

for m in range(1, 61):
    year_bump = tam * (yearly_growth / 100) if m in [13, 25, 37, 49] else 0
    growth_users = current_users * (monthly_growth / 100)
    if total_users_used + growth_users + year_bump > tam:
        growth_users = max(0, tam - total_users_used)
    total_users_used += growth_users + year_bump

    rejoining = rejoin_schedule[m]
    active_users = growth_users + rejoining

    for d in selected_durations:
        if duration_alloc[d] == 0: continue
        users_d = active_users * (duration_alloc[d] / 100)
        for slab in slabs:
            if slab_alloc[d][slab] == 0: continue
            users_slab = users_d * (slab_alloc[d][slab] / 100)
            if m + d + rest_period < len(rejoin_schedule):
                rejoin_schedule[m + d + rest_period] += users_slab

            for slot in range(1, d + 1):
                if slot_blocked[d][slot]:
                    u = deposit = fee_col = nii = profit = payout = refund = fee = 0
                    state = "Blocked"
                else:
                    u = users_slab
                    fee = slot_fees[d][slot]
                    deposit = u * slab * d
                    payout = u * slab  # Assume lump sum at end
                    fee_col = deposit * (fee / 100) if fee_upfront else payout * (fee / 100)
                    nii = deposit * ((kibor + spread) / 100 / 12)
                    loss = (payout * default_rate / 100)
                    refund = deposit * (1 - default_fee_pct / 100) if m % d < 2 else 0
                    profit = fee_col + nii - loss
                    state = "Active"

                records.append({
                    "Month": m, "Year": (m - 1) // 12 + 1,
                    "Duration": d, "Slab": slab, "Slot": slot,
                    "New Users": growth_users if slot == 1 and slab == slabs[0] else 0,
                    "Rejoining Users": rejoining if slot == 1 and slab == slabs[0] else 0,
                    "State": state,
                    "Users": u, "Deposit": deposit,
                    "Payout": payout, "Fee %": fee,
                    "Fee Collected": fee_col, "NII": nii,
                    "Loss from Default": loss, "Refund": refund,
                    "Profit": profit
                })

df = pd.DataFrame(records)
monthly = df.groupby("Month")[["Users", "Deposit", "Payout", "Fee Collected", "NII", "Profit"]].sum().reset_index()
yearly = df.groupby("Year")[["Users", "Deposit", "Payout", "Fee Collected", "NII", "Profit"]].sum().reset_index()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Forecast", "Monthly Summary", "Yearly Summary", "Charts", "Export"])
with tab1: st.dataframe(df)
with tab2: st.dataframe(monthly)
with tab3: st.dataframe(yearly)
with tab4:
    if not df.empty:
        st.line_chart(monthly.set_index("Month")[["Fee Collected", "NII", "Profit"]])
with tab5:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Forecast")
        monthly.to_excel(writer, index=False, sheet_name="Monthly")
        yearly.to_excel(writer, index=False, sheet_name="Yearly")
    st.download_button("📥 Download Excel", out.getvalue(), "rosco_forecast_v7_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
