
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

def reverse_dcf(fcf, market_price, shares_outstanding, discount_rate=0.10, stage1_years=5, terminal_growth=0.025, stage2_growth=0.04, stage2_years=5):
    if fcf is None or fcf <= 0 or market_price is None or market_price <= 0 or shares_outstanding is None or shares_outstanding <= 0:
        return None
    def npv_given_growth(growth_rate):
        npv1 = sum(
            fcf * (1 + growth_rate) ** year / (1 + discount_rate) ** year
            for year in range(1, stage1_years + 1)
        )
        last_fcf = fcf * (1 + growth_rate) ** stage1_years
        npv2 = sum(
            last_fcf * (1 + stage2_growth) ** (year - stage1_years) / (1 + discount_rate) ** year
            for year in range(stage1_years + 1, stage1_years + stage2_years + 1)
        )
        terminal = (last_fcf * (1 + stage2_growth) ** stage2_years) * (1 + terminal_growth) / (discount_rate - terminal_growth)
        terminal_discounted = terminal / ((1 + discount_rate) ** (stage1_years + stage2_years))
        return (npv1 + npv2 + terminal_discounted) / shares_outstanding
    low, high = -0.5, 1.0
    for _ in range(100):
        mid = (low + high) / 2
        npv = npv_given_growth(mid)
        if npv > market_price:
            high = mid
        else:
            low = mid
    return round(mid, 4)


with st.sidebar.expander("📈 Stage 1"):
    stage1_years = st.slider("Stage 1 Duration (Years)", 1, 10, 5)

with st.sidebar.expander("📉 Stage 2"):
    stage2_growth = st.slider("Growth Rate (%)", 0.0, 10.0, 4.0, 0.1) / 100
    stage2_years = st.slider("Stage 2 Duration (Years)", 1, 10, 5)

with st.sidebar.expander("⚙️ Other Settings"):
    discount_rate = st.slider("Discount Rate (%)", 5.0, 15.0, 10.0, 0.25) / 100
    terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 6.0, 2.5, 0.1) / 100


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

# -------- Portfolio-Level Summary Section --------
st.subheader("📋 Portfolio Summary")
portfolio_options = sorted(portfolio_df["Portfolio"].unique())
selected_portfolio = st.selectbox("Select a Portfolio", options=portfolio_options)

filtered_df = analysis_df[analysis_df["Portfolio"] == selected_portfolio]
realism_dist = filtered_df["Realism"].value_counts().reset_index()
realism_dist.columns = ["Realism", "Count"]
st.write("Realism Distribution")
st.dataframe(realism_dist, use_container_width=True)

st.subheader(f"📈 Implied Growth Rates – {selected_portfolio}")
growth_chart = alt.Chart(filtered_df).mark_bar().encode(
    x=alt.X("Ticker:N", title="Stock"),
    y=alt.Y("Implied Growth (%)", title="Implied Growth Rate"),
    color=alt.Color("Realism:N", title="Realism"),
    tooltip=["Ticker", "Implied Growth (%)", "Realism"]
).properties(height=400)


# Sync chart colors with realism classifications
color_scale = alt.Scale(domain=["🟦 Conservative", "🟨 Reasonable", "🔴 Aggressive"],
                        range=["#1f77b4", "#ffdd57", "#d62728"])

growth_chart = alt.Chart(filtered_df).mark_bar().encode(
    x=alt.X("Ticker:N", title="Stock"),
    y=alt.Y("Implied Growth (%)", title="Implied Growth Rate"),
    color=alt.Color("Realism:N", title="Realism", scale=color_scale),
    tooltip=["Ticker", "Implied Growth (%)", "Realism"]
).properties(height=400)

st.altair_chart(growth_chart, use_container_width=True)




# -------- Per-Stock DCF Details with Projection --------
st.subheader("🔍 Individual DCF Breakdown")

for _, row in filtered_df.iterrows():
    ticker = row["Ticker"]
    with st.expander(f"📊 {ticker} – Detailed DCF Analysis"):
        stock_exp = yf.Ticker(ticker)
        base_fcf = get_fcf(ticker)
        price = stock_exp.info.get("regularMarketPrice", None)
        shares = stock_exp.info.get("sharesOutstanding", None)
        implied_growth = reverse_dcf(base_fcf, price, shares, discount_rate, stage1_years, terminal_growth, stage2_growth, stage2_years)

        if not base_fcf or not implied_growth or implied_growth <= -1 or not shares:
            st.warning("Insufficient data to compute full projection.")
            continue

        # Recalculate per-year projection
        years, growths, fcfs, npvs = [], [], [], []
        for i in range(1, stage1_years + stage2_years + 1):
            growth = implied_growth if i <= stage1_years else stage2_growth
            if i == 1:
                fcf = base_fcf * (1 + growth)
            else:
                fcf = fcfs[-1] * (1 + growth)
            npv = fcf / ((1 + discount_rate) ** i)
            years.append(f"Year {i}")
            growths.append(round(growth * 100, 2))
            fcfs.append(round(fcf, 2))
            npvs.append(round(npv, 2))

        terminal_value = fcfs[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        terminal_npv = terminal_value / ((1 + discount_rate) ** (stage1_years + stage2_years))
        years.append("Terminal Year")
        growths.append(round(terminal_growth * 100, 2))
        fcfs.append(round(terminal_value, 2))
        npvs.append(round(terminal_npv, 2))

        dcf_df = pd.DataFrame({
            "Year": years,
            "Growth Rate (%)": growths,
            "Projected FCF": fcfs,
            "Discounted NPV": npvs
        })

        st.markdown(f"**Implied Growth Rate:** {round(implied_growth * 100, 2)}%")
        st.dataframe(dcf_df, use_container_width=True)

        csv = dcf_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download DCF Breakdown CSV",
            data=csv,
            file_name=f"{ticker}_dcf_breakdown.csv",
            mime="text/csv"
        )
