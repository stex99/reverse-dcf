
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

def reverse_dcf(fcf, market_price, shares_outstanding, discount_rate=0.10, projection_years=5, terminal_growth=0.025):
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
discount_rate = st.sidebar.slider("Discount Rate (%)", 5.0, 15.0, 10.0, 0.25) / 100
projection_years = st.sidebar.slider("Projection Period (Years)", 1, 10, 5, 1)
terminal_growth = st.sidebar.slider("Terminal Growth Rate (%)", 0.0, 6.0, 2.5, 0.1) / 100
sort_method = st.sidebar.radio("Sort By", ["Implied Growth Rate", "Market Price"], index=0)

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

results = []
for _, row in portfolio_df.iterrows():
    ticker = row["Ticker"]
    shares = row["Shares"]
    portfolio = row["Portfolio"]
    fcf = get_fcf(ticker)
    stock = yf.Ticker(ticker)
    try:
        current_price = stock.info.get("regularMarketPrice", None)
    except:
        current_price = None
    shares_outstanding = stock.info.get("sharesOutstanding", None)
    implied_growth = reverse_dcf(fcf, current_price, shares_outstanding, discount_rate, projection_years, terminal_growth)
    results.append({
        "Portfolio": portfolio,
        "Ticker": ticker,
        "Shares": shares,
        "Market Price ($)": round(current_price, 2) if current_price else None,
        "Implied Growth Rate (%)": round(implied_growth * 100, 2) if implied_growth else None
    })

results_df = pd.DataFrame(results).dropna()

if sort_method == "Implied Growth Rate":
    results_df = results_df.sort_values(by="Implied Growth Rate (%)", ascending=False)
elif sort_method == "Market Price":
    results_df = results_df.sort_values(by="Market Price ($)", ascending=False)

st.dataframe(results_df, use_container_width=True)

chart_df = results_df.melt(
    id_vars=["Portfolio", "Ticker"],
    value_vars=["Implied Growth Rate (%)", "Market Price ($)"],
    var_name="Type",
    value_name="Value"
)

st.subheader("📊 Implied Growth vs. Market Price")

base = alt.Chart(chart_df).encode(
    x=alt.X("Ticker:N", title="Stock"),
    y=alt.Y("Value:Q", title="Value"),
    color=alt.Color("Type:N"),
    tooltip=["Portfolio", "Ticker", "Type", "Value"]
)

bars = base.transform_filter(alt.datum.Type == "Implied Growth Rate (%)").mark_bar()
line = base.transform_filter(alt.datum.Type == "Market Price ($)").mark_line(point=True, strokeDash=[4, 2])

combined = (bars + line).properties(height=400)

facet = alt.Facet("Portfolio:N", title="Portfolio")
chart = alt.FacetChart(
    data=chart_df,
    facet=facet,
    spec=combined,
    columns=2
)

st.altair_chart(chart, use_container_width=True)
