
# ROSCA Forecast App v10 – With Dynamic Slot/Block Fee Matrix

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import xlsxwriter

# -----------------------------
# Configuration Inputs
# -----------------------------
st.title("ROSCA Forecast App v10")

durations = st.multiselect("Select Committee Durations", [3, 4, 5, 6, 8, 10], default=[3, 4, 6])
slot_fees = {}
slot_blocks = {}

for d in durations:
    st.markdown(f"### Duration: {d} Months")
    slot_fees[d] = {}
    slot_blocks[d] = {}
    for s in range(1, d + 1):
        col1, col2 = st.columns(2)
        with col1:
            slot_fees[d][s] = st.number_input(f"Fee % for Slot {s} (Duration {d}M)", 0.0, 100.0, 2.0, step=0.1, key=f"fee_{d}_{s}")
        with col2:
            slot_blocks[d][s] = st.checkbox(f"Block Slot {s} (Duration {d}M)", False, key=f"block_{d}_{s}")

# -----------------------------
# Forecast Generation
# -----------------------------
@st.cache_data
def generate_forecast(slot_fees, slot_blocks):
    months = pd.date_range("2025-01-01", periods=60, freq='MS')
    forecast_data = []

    base_users = 200000
    growth_rate = 0.02
    kibor = 0.14
    spread = 0.03
    default_rate = 0.05

    active_users = base_users

    for i, month in enumerate(months):
        for duration in slot_fees:
            for slot in slot_fees[duration]:
                if slot_blocks[duration][slot]:
                    continue

                new_users = int(active_users * growth_rate / len(slot_fees[duration]))
                rejoining_users = int(active_users * 0.01 / len(slot_fees[duration])) if i >= 4 else 0
                total_active = new_users + rejoining_users
                deposit_per_user = 1000 * duration
                fee_percent = slot_fees[duration][slot] / 100
                deposits = total_active * deposit_per_user
                fee_collected = deposits * fee_percent
                nii = deposits * ((kibor + spread) / 12)
                profit = fee_collected + nii - (default_rate * deposits)

                forecast_data.append({
                    "Month": month.strftime("%b %Y"),
                    "Duration": duration,
                    "Slot": slot,
                    "New Users": new_users,
                    "Rejoining Users": rejoining_users,
                    "Active Users": total_active,
                    "Deposit/User": deposit_per_user,
                    "Fee %": fee_percent * 100,
                    "Fee Collected": fee_collected,
                    "NII": nii,
                    "Profit": profit
                })

        active_users = int(active_users * (1 + growth_rate))

    return pd.DataFrame(forecast_data)

df = generate_forecast(slot_fees, slot_blocks)

# -----------------------------
# Display and Charts
# -----------------------------
st.subheader("📊 Forecast Table")
st.dataframe(df)

st.subheader("📈 Forecast Charts")
metric = st.selectbox("Select Metric for Chart", ["Fee Collected", "NII", "Profit"])
chart_df = df.groupby("Month")[metric].sum().reset_index()

fig, ax = plt.subplots()
ax.plot(chart_df["Month"], chart_df[metric], label=metric)
plt.xticks(rotation=45)
plt.ylabel(metric)
plt.title(f"{metric} Over Time")
st.pyplot(fig)

# -----------------------------
# Excel Export
# -----------------------------
def export_forecast_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Forecast', index=False)
    output.seek(0)
    return output

if st.button("📥 Export to Excel"):
    st.download_button(
        label="Download Excel File",
        data=export_forecast_excel(df),
        file_name="rosca_forecast_v10.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
