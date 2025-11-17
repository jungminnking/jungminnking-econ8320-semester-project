import pandas as pd
import streamlit as st
import plotly.express as px

# Title
st.set_page_config(page_title="US Economy Dashboard", layout="wide")
st.title("US Economy Dashboard")
st.caption("Semester Project for Econ 8320")

# CSV loading 
@st.cache_data(show_spinner=False)
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url, parse_dates=["date"])
    df["series_id"] = df["series_id"].astype("string")
    return df
    
csv_url = "https://github.com/jungminnking/jungminnking-econ8320-semester-project/raw/main/data/bls_timeseries.csv"
df_all = load_data(csv_url)

# Series
series = {
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)"},
    "PRS85006092": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)"},
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, Basis: 1982–84)"},
    "CIU1010000000000A": {"section": "Compensation", "name": "ECI — Total Compensation, Private (12m % change, NSA)"},
}
sections = ["Employment", "Productivity", "Price Index", "Compensation"]

# Sidebar
min_year = int(df_all["date"].dt.year.min())
max_year = int(df_all["date"].dt.year.max())
year_min, year_max = st.sidebar.slider("Year range", min_value=min_year, max_value=max_year, value=(min_year, max_year))

# Summary 
df = df_all[(df_all["date"].dt.year >= year_min) & (df_all["date"].dt.year <= year_max)]
st.subheader("Data Summary")
coverage = (df.groupby("series_id")["date"]
    .agg(["min", "max", "count"])
    .rename_axis("series_id")
    .reset_index()
)

coverage["series_name"] = coverage["series_id"].map(lambda sid: series.get(sid, {}).get("name", sid))
coverage["coverage_year"] = (coverage["min"].dt.strftime("%Y-%m-%d") + "–" + coverage["max"].dt.strftime("%Y-%m-%d"))

coverage = coverage.rename(columns={
    "series_name": "Economic Indicator",
    "coverage_year": "Coverage Year",
    "count": "Number of Obs.",
})[["Economic Indicator", "Coverage Year", "Number of Obs."]]

coverage.index = coverage.index + 1
coverage.index.name = "#"

st.caption("Original Source: [U.S. Bureau of Labor Statistics](https://data.bls.gov/toppicks?survey=bls)")
st.dataframe(coverage, use_container_width=True)

# Download filtered CSV
st.download_button(
    "⬇️ Download CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="bls_timeseries_filtered.csv",
    mime="text/csv",
)

# Charts
tabs = st.tabs(sections)
for sec, tab in zip(sections, tabs):
    with tab:
        st.subheader(sec)
        sub_ids = [sid for sid, meta in series.items() if meta["section"] == sec]
        for sid in sub_ids:
            name = series[sid]["name"]
            d = df[df.series_id == sid].sort_values("date")
            if d.empty:
                continue
            fig = px.line(d, x="date", y="value", title=name, labels={"value": "Value", "date": "Year"},)
            fig.update_traces(mode="lines", hovertemplate="%{x|%Y-%m} — %{y:.2f}")
            start_date = pd.Timestamp("2006-01-01") - pd.DateOffset(months=3)  
            end_date = d["date"].max() + pd.DateOffset(months=3)               
            fig.update_layout(xaxis=dict(range=[start_date, end_date],title="Year", tickformat="%Y", showgrid=True, zeroline=False,), yaxis=dict(showgrid=True, zeroline=False), margin=dict(l=40, r=40, t=60, b=40),)
            st.plotly_chart(fig, use_container_width=True)

# Footer
st.write("---")
st.caption(f"Reading data directly from: {csv_url}")