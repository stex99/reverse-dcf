
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import altair as alt
from io import StringIO

st.set_page_config(page_title="Reverse DCF Analyzer", layout="wide")

def get_fcf(ticker):
    stock = yf.Ticker(ticker)
    cf = stock.cashflow
    if cf is None or cf.empty:
        return None
    def find_label(possible_labels):
        for label in possible_labels:
            for idx in cf.index:
                if label.lower() in idx.lower():
                    return cf.loc[idx].iloc[0]
        return None
    ocf = find_label(['Total Cash From Operating Activities', 'Operating Cash Flow'])
    capex = find_label(['Capital Expenditures', 'Capital Expenditures - Fixed Assets'])
    if ocf is None or capex is None:
        return stock.info.get("freeCashflow", None)
    return ocf + capex


def reverse_dcf(fcf, market_price, shares_outstanding, discount_rate=0.10, projection_years=5, terminal_growth=0.025, stage2_growth=0.04, stage2_years=5):
    if fcf is None or fcf <= 0 or market_price is None or market_price <= 0 or shares_outstanding is None or shares_outstanding <= 0:
        return None

    def npv_given_growth(growth_rate):
        # Stage 1
        npv1 = sum(
            fcf * (1 + growth_rate) ** year / (1 + discount_rate) ** year
            for year in range(1, projection_years + 1)
        )
        # Stage 2
        last_fcf = fcf * (1 + growth_rate) ** projection_years
        npv2 = sum(
            last_fcf * (1 + stage2_growth) ** (year - projection_years) / (1 + discount_rate) ** year
            for year in range(projection_years + 1, projection_years + stage2_years + 1)
        )
        # Terminal
        terminal = (last_fcf * (1 + stage2_growth) ** stage2_years) * (1 + terminal_growth) / (discount_rate - terminal_growth)
        terminal_discounted = terminal / ((1 + discount_rate) ** (projection_years + stage2_years))
        total_value = npv1 + npv2 + terminal_discounted
        return total_value / shares_outstanding

    low, high = -0.5, 1.0
    for _ in range(100):
        mid = (low + high) / 2
        npv = npv_given_growth(mid)
        if npv > market_price:
            high = mid
        else:
            low = mid
    return round(mid, 4)

    if fcf is None or fcf <= 0 or market_price is None or market_price <= 0 or shares_outstanding is None or shares_outstanding <= 0:
        return None
    def npv_given_growth(growth_rate):
        npv = sum(
            fcf * (1 + growth_rate) ** year / (1 + discount_rate) ** year
            for year in range(1, projection_years + 1)
        )
        terminal = (fcf * (1 + growth_rate) ** projection_years) * (1 + terminal_growth) / (discount_rate - terminal_growth)
        terminal_discounted = terminal / ((1 + discount_rate) ** projection_years)
        total_value = npv + terminal_discounted
        return total_value / shares_outstanding
    low, high = -0.5, 1.0
    for _ in range(100):
        mid = (low + high) / 2
        npv = npv_given_growth(mid)
        if npv > market_price:
            high = mid
        else:
            low = mid
    return round(mid, 4)

st.sidebar.header("Reverse DCF Settings")
stage1_years = st.sidebar.slider("Stage 1 Years", 1, 10, 5)
stage2_years = st.sidebar.slider("Stage 2 Years", 1, 10, 5)
stage2_growth = st.sidebar.slider("Stage 2 Growth Rate (%)", 0.0, 10.0, 4.0, 0.1) / 100
discount_rate = st.sidebar.slider("Discount Rate (%)", 5.0, 15.0, 10.0, 0.25) / 100
projection_years = st.sidebar.slider("Projection Period (Years)", 1, 10, 5, 1)
terminal_growth = st.sidebar.slider("Terminal Growth Rate (%)", 0.0, 6.0, 2.5, 0.1) / 100

uploaded_files = st.file_uploader("Upload One or More Portfolio CSVs", type=["csv"], accept_multiple_files=True)

if not uploaded_files:
    st.info("No file uploaded. Using example portfolio.")
    uploaded_files = [StringIO("""Ticker,Shares
AAPL,20
MSFT,15
GOOGL,10
NVDA,8
JNJ,25
""")]
    uploaded_files[0].name = "Sample Portfolio"

portfolio_dfs = []
for f in uploaded_files:
    df = pd.read_csv(f)
    df["Portfolio"] = f.name.replace(".csv", "")
    portfolio_dfs.append(df)

portfolio_df = pd.concat(portfolio_dfs, ignore_index=True)

# --------- Advanced Analysis Section ---------
st.subheader("🧠 Advanced Stock-Level Assessment")

analysis_rows = []
for _, row in portfolio_df.iterrows():
    ticker = row["Ticker"]
    stock = yf.Ticker(ticker)
    portfolio = row["Portfolio"]
    try:
        fcf = get_fcf(ticker)
        price = stock.info.get("regularMarketPrice", None)
        shares = stock.info.get("sharesOutstanding", None)
        growth = reverse_dcf(fcf, price, shares, discount_rate, stage1_years, terminal_growth, stage2_growth, stage2_years)
        mos_10 = reverse_dcf(fcf, price * 0.9, shares, discount_rate, stage1_years, terminal_growth, stage2_growth, stage2_years)
        mos_20 = reverse_dcf(fcf, price * 0.8, shares, discount_rate, stage1_years, terminal_growth, stage2_growth, stage2_years)
        hist_growth = stock.info.get("earningsQuarterlyGrowth", None)
    except:
        continue

    if growth is None:
        continue

    if growth < 0.05:
        realism = "🟦 Conservative"
    elif growth < 0.15:
        realism = "🟨 Reasonable"
    else:
        realism = "🔴 Aggressive"

    analysis_rows.append({
        "Portfolio": portfolio,
        "Ticker": ticker,
        "Implied Growth (%)": round(growth * 100, 2),
        "10% MOS (%)": round(mos_10 * 100, 2) if mos_10 else None,
        "20% MOS (%)": round(mos_20 * 100, 2) if mos_20 else None,
        "Realism": realism,
        "Hist Growth (Est)": round(hist_growth * 100, 2) if hist_growth else None
    })

analysis_df = pd.DataFrame(analysis_rows)
st.dataframe(analysis_df, use_container_width=True)
