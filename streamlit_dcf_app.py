
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

st.altair_chart(growth_chart, use_container_width=True)


# -------- Per-Stock DCF Details (Expander Style) --------
st.subheader("🔍 Individual DCF Breakdown")

for _, row in filtered_df.iterrows():
    with st.expander(f"📊 {row['Ticker']} – Detailed DCF Analysis"):
        st.markdown(f"**Implied Growth Rate:** {row['Implied Growth (%)']}%")
        st.markdown(f"**10% Margin of Safety Implied Growth:** {row['10% MOS (%)']}%")
        st.markdown(f"**20% Margin of Safety Implied Growth:** {row['20% MOS (%)']}%")
        st.markdown(f"**Realism Rating:** {row['Realism']}")
        st.markdown(f"**Historical Growth Estimate:** {row['Hist Growth (Est)']}%")
        
        
        # Generate per-year FCF projection (2-stage model)
        base_fcf = get_fcf(row["Ticker"])
        years = []
        growths = []
        fcfs = []
        npvs = []
        disc_rate = discount_rate
        stage1 = stage1_years
        stage2 = stage2_years
        g2 = stage2_growth
        g1 = row["Implied Growth (%)"] / 100
        if not base_fcf or not g1 or g1 <= -1:
            continue
        for i in range(1, stage1 + stage2 + 1):
            if i <= stage1:
                growth = g1
            else:
                growth = g2
            if i == 1:
                fcf = base_fcf * (1 + growth)
            else:
                fcf = fcfs[-1] * (1 + growth)
            npv = fcf / ((1 + disc_rate) ** i)
            years.append(f"Year {i}")
            growths.append(round(growth * 100, 2))
            fcfs.append(round(fcf, 2))
            npvs.append(round(npv, 2))

        terminal_value = fcfs[-1] * (1 + terminal_growth) / (disc_rate - terminal_growth)
        terminal_npv = terminal_value / ((1 + disc_rate) ** (stage1 + stage2))
        years.append(f"Terminal Year")
        growths.append(round(terminal_growth * 100, 2))
        fcfs.append(round(terminal_value, 2))
        npvs.append(round(terminal_npv, 2))

        dcf_df = pd.DataFrame({
            "Year": years,
            "Growth Rate (%)": growths,
            "Projected FCF": fcfs,
            "Discounted NPV": npvs
        })

        dcf_data = {
            "Metric": ["Implied Growth (%)", "10% MOS (%)", "20% MOS (%)", "Historical Growth (Est)"],
            "Value": [row["Implied Growth (%)"], row["10% MOS (%)"], row["20% MOS (%)"], row["Hist Growth (Est)"]]
        }
        dcf_df = pd.DataFrame(dcf_data)

        csv = dcf_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download DCF Breakdown CSV",
            data=csv,
            file_name=f"{row['Ticker']}_dcf_breakdown.csv",
            mime="text/csv"
        )

