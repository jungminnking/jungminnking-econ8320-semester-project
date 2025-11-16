# ===========================================================
# US Labor Dashboard — Exploration (v2)
# ===========================================================
# Jungmin Hwang
# -----------------------------------------------------------
# Features:
# - Correct BLS series IDs (PRS85006093, CIU1010000000000I)
# - Keeps quarterly data (Q→M: 03/06/09/12)
# - Fetches data from BLS API
# - Saves unified CSV for Streamlit dashboard
# - Visualizes Employment, Productivity, CPI, and ECI
# ===========================================================

import os
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path

# -------- Plot settings (safe in .py and notebooks) --------
try:
    import IPython  # only present in notebook/REPL
    ip = IPython.get_ipython()
    if ip is not None:
        ip.run_line_magic("matplotlib", "inline")
except Exception:
    pass

plt.rcParams["figure.figsize"] = (11, 5)
plt.rcParams["axes.grid"] = True
pd.set_option("display.float_format", lambda x: f"{x:,.3f}")

START_YEAR = 2006
END_YEAR = datetime.utcnow().year
print("Pandas", pd.__version__, "| Years", START_YEAR, "→", END_YEAR)

# -------- Paths (relative to this file) --------
BASE_DIR = Path(__file__).resolve().parent
data_dir = BASE_DIR / "data"
data_dir.mkdir(parents=True, exist_ok=True)

# ===========================================================
# 1. BLS Series Configuration
# ===========================================================
SERIES = {
    # Employment (Monthly)
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},

    # Productivity (Quarterly, SA — Q/Q %)
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q"},

    # Price Index (Monthly, NSA)
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},

    # Compensation (Quarterly, NSA)
    "CIU1010000000000I": {"section": "Compensation", "name": "ECI — Total Compensation, Private Industry (12m % chg)", "freq": "Q"},
}

# ===========================================================
# 2. Fetch from BLS API
# ===========================================================
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

class BLSError(Exception):
    pass

def fetch_bls_timeseries(series_ids, start_year, end_year):
    """Fetch data from BLS API for multiple series."""
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    key = os.getenv("BLS_API_KEY")
    if key:
        payload["registrationkey"] = key

    r = requests.post(BLS_URL, json=payload, timeout=60)
    if r.status_code != 200:
        raise BLSError(f"HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise BLSError(f"BLS API error: {json.dumps(data)[:300]}")
    return data

def _q_to_month(q: int) -> int:
    return {1: 3, 2: 6, 3: 9, 4: 12}[q]

def series_payload_to_rows(series_json):
    """Flatten each BLS series JSON into rows of (series_id, date, value).
       Keeps monthly (M01..M12) and quarterly (Q01..Q04→Mar/Jun/Sep/Dec)."""
    sid = series_json["seriesID"]
    rows = []
    for item in series_json.get("data", []):
        p = item.get("period")
        if not p or p == "M13":
            continue  # drop annual averages

        year = int(item["year"])
        if p.startswith("M"):
            month = int(p[1:])
        elif p.startswith("Q"):
            month = _q_to_month(int(p[1:]))
        else:
            # Unknown period (e.g., annual), skip
            continue

        dt = pd.Timestamp(year=year, month=month, day=1)
        rows.append({
            "series_id": sid,
            "date": dt,
            "value": float(item["value"]),
        })
    return rows

# ===========================================================
# 3. Download & Save Unified Dataset
# ===========================================================
print("Fetching data from BLS API...")
api = fetch_bls_timeseries(list(SERIES.keys()), START_YEAR, END_YEAR)

rows = []
for s in api["Results"]["series"]:
    rows.extend(series_payload_to_rows(s))

df = pd.DataFrame(rows).sort_values(["series_id", "date"]).reset_index(drop=True)
out_path = data_dir / "bls_timeseries.csv"
df.to_csv(out_path, index=False)
print(f"✅ Saved {len(df)} rows to {out_path}")

# Show data coverage summary (works in plain Python, too)
coverage = (
    df.groupby("series_id")["date"]
      .agg(["min", "max", "count"])
      .rename_axis("series_id")
      .reset_index()
)
print("\nCoverage:")
print(coverage.to_string(index=False))

# ===========================================================
# 4. Helper Functions
# ===========================================================
def plot_series(df_long, series_ids, title=None, ylabel=None, since=None):
    """Plot each series with Matplotlib."""
    sub = df_long[df_long.series_id.isin(series_ids)].copy()
    if since is not None:
        sub = sub[sub.date >= pd.to_datetime(since)]
    present = sorted(sub["series_id"].unique())
    missing = [sid for sid in series_ids if sid not in present]
    if missing:
        print("⚠️ No data for:", ", ".join(missing))
    for sid in present:
        name = SERIES.get(sid, {}).get("name", sid)
        d = sub[sub.series_id == sid].sort_values("date")
        plt.figure()
        plt.plot(d["date"], d["value"], marker="o", linewidth=1)
        plt.title(title or name)
        plt.xlabel("Date")
        plt.ylabel(ylabel or "Value")
        plt.tight_layout()
        plt.show()

def yoy(df_long, sid):
    """Compute year-over-year percentage change (12m for M, 4q for Q)."""
    freq = SERIES.get(sid, {}).get("freq", "M").upper()
    lag = 4 if freq.startswith("Q") else 12
    d = (df_long[df_long.series_id == sid]
         .set_index("date")
         .sort_index()[["value"]]
         .copy())
    d["YoY %"] = d["value"].pct_change(lag) * 100
    return d

# ===========================================================
# 5. Visualizations by Section
# ===========================================================
# --- Employment ---
employment_ids = ["LNS12000000", "CES0000000001", "LNS14000000", "CES0500000002", "CES0500000003"]
plot_series(df, employment_ids, title="Employment Indicators", since=f"{START_YEAR}-01-01")

# --- Productivity ---
plot_series(df, ["PRS85006093"], title="Output per Hour — Nonfarm Business (Q/Q %)", ylabel="Q/Q %", since=f"{START_YEAR}-01-01")

# --- Price Index (CPI) ---
plot_series(df, ["CUUR0000SA0"], title="CPI-U All Items (NSA, 1982–84=100)", ylabel="Index", since=f"{START_YEAR}-01-01")

cpi_y = yoy(df, "CUUR0000SA0")
plt.figure()
plt.plot(cpi_y.index, cpi_y["YoY %"], linewidth=1)
plt.title("CPI-U — 12-month % change")
plt.xlabel("Date")
plt.ylabel("YoY %")
plt.tight_layout()
plt.show()

# --- Compensation (ECI) ---
plot_series(df, ["CIU1010000000000I"], title="Employment Cost Index (12m % chg)", ylabel="%", since=f"{START_YEAR}-01-01")

print("✅ All plots generated successfully!")
