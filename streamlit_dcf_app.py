
import streamlit as st

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
