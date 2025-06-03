
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import altair as alt

st.set_page_config(page_title="Reverse DCF Tool", layout="wide")

# --- Sidebar Inputs ---
with st.sidebar.expander("📉 Stage 2"):
    use_stage2 = st.checkbox("Enable Stage 2 Calculations", value=True)
    if use_stage2:
        stage1_years = st.slider("Stage 1 Duration (Years)", 1, 10, 5)
        use_relative_growth = st.checkbox("Stage 2 Growth as % of Stage 1")
        if use_relative_growth:
            stage2_ratio = st.slider("Stage 2 / Stage 1 Ratio (%)", 0.0, 100.0, 40.0, 5.0) / 100
            stage2_growth = None
        else:
            stage2_growth = st.slider("Stage 2 Growth Rate (%)", 0.0, 10.0, 4.0, 0.1) / 100
        stage2_years = st.slider("Stage 2 Duration (Years)", 1, 10, 5)
    else:
        stage1_years = 10
        stage2_growth = 0.0
        stage2_years = 0

with st.sidebar.expander("⚙️ Other Settings"):
    discount_rate = st.slider("Discount Rate (%)", 5.0, 15.0, 10.0, 0.25) / 100
    terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 6.0, 2.5, 0.1) / 100

uploaded_file = st.file_uploader("Upload your portfolio CSV", type=["csv"])
if uploaded_file:
    portfolio_df = pd.read_csv(uploaded_file)
else:
    portfolio_df = pd.read_csv("sample_portfolio.csv")

def get_fcf(ticker):
    stock = yf.Ticker(ticker)
    cf = stock.cashflow
    if cf is None or cf.empty:
        return None
    def match_row(labels):
        for l in labels:
            for row in cf.index:
                if l.lower() in row.lower():
                    return cf.loc[row].iloc[0]
        return None
    ocf = match_row(["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = match_row(["Capital Expenditures"])
    if ocf is None or capex is None:
        return stock.info.get("freeCashflow", None)
    return ocf + capex

def reverse_dcf(fcf, market_price, shares_outstanding, discount_rate, stage1, term_growth, stage2_growth, stage2):
    if not fcf or not market_price or not shares_outstanding or fcf <= 0 or market_price <= 0:
        return None
    def npv_for_growth(g):
        npv1 = sum(fcf * (1 + g) ** i / (1 + discount_rate) ** i for i in range(1, stage1 + 1))
        last_fcf = fcf * (1 + g) ** stage1
        npv2 = sum(last_fcf * (1 + stage2_growth) ** (i - stage1) / (1 + discount_rate) ** i for i in range(stage1 + 1, stage1 + stage2 + 1))
        terminal = last_fcf * (1 + stage2_growth) ** stage2 * (1 + term_growth) / (discount_rate - term_growth)
        terminal_discounted = terminal / ((1 + discount_rate) ** (stage1 + stage2))
        return (npv1 + npv2 + terminal_discounted) / shares_outstanding
    low, high = -0.5, 1.0
    for _ in range(50):
        mid = (low + high) / 2
        val = npv_for_growth(mid)
        if val > market_price:
            high = mid
        else:
            low = mid
    return round(mid, 4)

# --- Analysis ---
results = []
for _, row in portfolio_df.iterrows():
    ticker = row["Ticker"]
    stock = yf.Ticker(ticker)
    fcf = get_fcf(ticker)
    price = stock.info.get("regularMarketPrice", None)
    shares = stock.info.get("sharesOutstanding", None)
    growth = reverse_dcf(fcf, price, shares, discount_rate, stage1_years, terminal_growth, stage2_growth or 0.04, stage2_years)
    if growth is None: continue
    if not use_stage2: stage2_growth = 0.0
    if use_stage2 and stage2_growth is None and growth:
        stage2_growth = growth * stage2_ratio
    mos_10 = reverse_dcf(fcf, price * 0.9, shares, discount_rate, stage1_years, terminal_growth, stage2_growth, stage2_years)
    mos_20 = reverse_dcf(fcf, price * 0.8, shares, discount_rate, stage1_years, terminal_growth, stage2_growth, stage2_years)
    realism = "🟦 Conservative" if growth < 0.05 else "🟨 Reasonable" if growth < 0.15 else "🔴 Aggressive"
    results.append({
        "Ticker": ticker,
        "Implied Growth (%)": round(growth * 100, 2),
        "10% MoS Growth (%)": round(mos_10 * 100, 2) if mos_10 else None,
        "20% MoS Growth (%)": round(mos_20 * 100, 2) if mos_20 else None,
        "Realism": realism
    })

results_df = pd.DataFrame(results)
st.title("📊 Reverse DCF Portfolio Analysis")
st.dataframe(results_df, use_container_width=True)

# Chart
st.subheader("Implied Growth by Ticker")
color_map = alt.Scale(domain=["🟦 Conservative", "🟨 Reasonable", "🔴 Aggressive"],
                      range=["#1f77b4", "#ffdd57", "#d62728"])
chart = alt.Chart(results_df).mark_bar().encode(
    x=alt.X("Ticker:N"),
    y=alt.Y("Implied Growth (%):Q"),
    color=alt.Color("Realism:N", scale=color_map),
    tooltip=["Ticker", "Implied Growth (%)", "Realism"]
).properties(height=400)

st.altair_chart(chart, use_container_width=True)
