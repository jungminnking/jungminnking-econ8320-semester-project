# %run "C:/Users/jungm/Documents/GitHub/jungminnking-econ8320-semester-project/Hello.py"
# Imports
import os                         # Read environment variables (e.g., BLS_API_KEY)
import json                       # Read/write meta.json (a simple timestamp file)
from datetime import datetime, timezone     # Add timezone for UTC handling
from pathlib import Path          # Clean, cross-platform path handling
from typing import Dict, List, Any  # Type hints for clarity (non-functional at runtime)
import requests                   # Make HTTP POST requests to the BLS API
import pandas as pd               # Work with tabular data (DataFrames)

# 1) CONSTANTS — global config and BLS series definitions
BLS_URL: str = "https://api.bls.gov/publicAPI/v2/timeseries/data/"  # BLS v2 endpoint
START_YEAR: int = 2006                 # Earliest year to include in the data
END_YEAR: int = datetime.now(timezone.utc).year

# List-of-tuples: (series_id, section, name, frequency)
SERIES = [
     ("LNS12000000", "Employment", "Civilian Employment (Thousands, SA)", "M"),
    ("CES0000000001", "Employment", "Total Nonfarm Employment (Thousands, SA)", "M"),
    ("LNS14000000", "Employment", "Unemployment Rate (% SA)", "M"),
    ("CES0500000002", "Employment", "Avg Weekly Hours, Total Private (SA)", "M"),
    ("CES0500000003", "Employment", "Avg Hourly Earnings, Total Private ($, SA)", "M"),
    ("PRS85006092", "Productivity", "Output per Hour — Nonfarm Business (Q/Q %)", "Q"),
    ("CUUR0000SA0", "Price Index", "CPI-U All Items (NSA, 1982–84=100)", "M"),
    ("CIU1010000000000A", "Compensation", "ECI — Total Compensation, Private (12m % change, NSA)", "Q"),
]

# ===========================================================
# 2) PATHS — where to store outputs (CSV + meta)
# ===========================================================
DATA_DIR: Path = Path("data")                                 # Root folder for outputs
CSV_PATH: Path = DATA_DIR / "bls_timeseries.csv"              # Main dataset (long format)
META_PATH: Path = DATA_DIR / "meta.json"                      # JSON metadata (last update)

# ===========================================================
# 4) API — request helper to fetch multiple series in one POST
# ===========================================================
def bls_timeseries(series_ids: List[str], start_year: int, end_year: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
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
        raise BLSError(f"BLS error: {json.dumps(data)[:300]}")
    return data

# ===========================================================
# 5) PARSING — convert BLS periods to monthly timestamps and tidy rows
# ===========================================================
def _q_to_month(q: int) -> int:
    """Q1→3, Q2→6, Q3→9, Q4→12 (pin quarterly data to the last month of the quarter)."""
    return {1: 3, 2: 6, 3: 9, 4: 12}[q]

def series_payload_to_rows(series_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flatten a single series' JSON into a list of tidy rows:
    {"series_id": <id>, "date": <Timestamp>, "value": <float>}
    Skips "M13" (annual averages). Supports M01..M12 and Q01..Q04.
    """
    sid = series_json["seriesID"]
    rows: List[Dict[str, Any]] = []

    for item in series_json.get("data", []):
        period = item.get("period")
        if not period or period == "M13":
            continue

        year = int(item["year"])
        if period.startswith("M"):
            month = int(period[1:])
        elif period.startswith("Q"):
            month = _q_to_month(int(period[1:]))
        else:
            continue

        dt = pd.Timestamp(year=year, month=month, day=1)
        val = float(item["value"])
        rows.append({"series_id": sid, "date": dt, "value": val})

    return rows

# ===========================================================
# 6) I/O — load existing CSV and merge (union + de-duplicate)
# ===========================================================
def load_existing() -> pd.DataFrame:
    """Load the existing CSV if present; else return an empty DataFrame with correct columns."""
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, parse_dates=["date"])
    return pd.DataFrame(columns=["series_id", "date", "value"])

def union_and_dedupe(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """Append new data, drop dups on (series_id, date) keeping last, and sort."""
    df = pd.concat([df_old, df_new], ignore_index=True)
    df = df.drop_duplicates(subset=["series_id", "date"], keep="last")
    return df.sort_values(["series_id", "date"]).reset_index(drop=True)

# ===========================================================
# 7) MAIN — full or incremental run, save CSV + meta.json
# ===========================================================
def run_full_or_incremental() -> pd.DataFrame:
    """
    First run: fetch START_YEAR..END_YEAR.
    Subsequent runs: backfill 24 months from latest date (to capture revisions).
    Writes CSV + meta.json. Returns the unified DataFrame.
    """
    df_old = load_existing()

    if df_old.empty:
        start = START_YEAR
    else:
        last_date = df_old["date"].max()
        start = max(START_YEAR, (last_date - pd.DateOffset(months=24)).year)

    # *** IMPORTANT: extract IDs from list-of-tuples ***
    series_ids = [sid for sid, _section, _name, _freq in SERIES]

    api = bls_timeseries(series_ids, start, END_YEAR)
    rows = [r for s in api["Results"]["series"] for r in series_payload_to_rows(s)]
    df_new = pd.DataFrame(rows)

    df_out = union_and_dedupe(df_old, df_new)

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(CSV_PATH, index=False)
    META_PATH.write_text(json.dumps({"last_updated_utc": datetime.utcnow().isoformat()}, indent=2))

    print(f"✅ Updated {len(df_out)} rows → {CSV_PATH}")
    return df_out

# ===========================================================
# 8) ENTRY POINT — run when executed as a script
# ===========================================================
if __name__ == "__main__":
    # Optional: export BLS_API_KEY="your_key_here" for better rate limits
    run_full_or_incremental()
