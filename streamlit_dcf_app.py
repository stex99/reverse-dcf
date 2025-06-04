
import streamlit as st
import pandas as pd

# Sample results_df to simulate data for the summary
results_df = pd.DataFrame({
    "Portfolio": ["A", "A", "A", "B", "B"],
    "Ticker": ["AAPL", "MSFT", "GOOGL", "JNJ", "NVDA"],
    "Implied Growth (%)": [8.5, 12.3, 5.7, 15.2, 9.1],
    "Realism": ["🟨 Reasonable", "🟨 Reasonable", "🟦 Conservative", "🔴 Aggressive", "🟨 Reasonable"]
})

st.title("📋 Portfolio Summary")

summary_table = results_df.groupby("Portfolio").agg(
    Avg_Growth=("Implied Growth (%)", "mean"),
    Conservative=("Realism", lambda x: (x == "🟦 Conservative").sum()),
    Reasonable=("Realism", lambda x: (x == "🟨 Reasonable").sum()),
    Aggressive=("Realism", lambda x: (x == "🔴 Aggressive").sum()),
    Ticker_Count=("Ticker", "count")
).reset_index()

st.dataframe(summary_table, use_container_width=True)
