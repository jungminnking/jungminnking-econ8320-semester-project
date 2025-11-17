# -*- coding: utf-8 -*-
"""
BLS Timeseries — Incremental Updater (Format/Flow Refactor Only)

- No content changes: same endpoints, series IDs, logic, and CSV/meta outputs.
- Reorganized for clarity: constants → paths → errors → API → parsing → I/O → main.
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import requests
import pandas as pd

# ===========================================================
# Constants
# ===========================================================
START_YEAR: int = 2006
END_YEAR: int = datetime.utcnow().year

BLS_URL: str = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Curated series (unchanged)
SERIES: Dict[str, Dict[str, str]] = {
    # Employment (Monthly, SA)
    "LNS12000000": {"section": "Employment", "name": "Civilian Employment (Thousands, SA)", "freq": "M"},
    "CES0000000001": {"section": "Employment", "name": "Total Nonfarm Employment (Thousands, SA)", "freq": "M"},
    "LNS14000000": {"section": "Employment", "name": "Unemployment Rate (% SA)", "freq": "M"},
    "CES0500000002": {"section": "Employment", "name": "Avg Weekly Hours, Total Private (SA)", "freq": "M"},
    "CES0500000003": {"section": "Employment", "name": "Avg Hourly Earnings, Total Private ($, SA)", "freq": "M"},
    # Productivity (Quarterly, SA) — percent change from previous quarter
    "PRS85006093": {"section": "Productivity", "name": "Output per Hour — Nonfarm Business (Q/Q %)", "freq": "Q"},
    # Price Index (Monthly, NSA)
    "CUUR0000SA0": {"section": "Price Index", "name": "CPI-U All Items (NSA, 1982–84=100)", "freq": "M"},
    # Compensation (Quarterly, NSA)
    "CIU1010000000000I": {"section": "Compensation", "name": "ECI — Total Compensation, Private (Index, NSA)", "freq": "Q"},
    "CIU1010000000000A": {"section": "Compensation", "name": "ECI — Total Compensation, Private (12m % change, NSA)", "freq": "Q"},
}

# ===========================================================
# Paths
# ===========================================================
DATA_DIR: Path = Path("data")
CSV_PATH: Path = DATA_DIR / "bls_timeseries.csv"
META_PATH: Path = DATA_DIR / "meta.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ===========================================================
# Errors
# ===========================================================
class BLSError(Exception):
    """Custom error for BLS API failures."""
    pass

# ===========================================================
# API
# ===========================================================
def fetch_bls_timeseries(series_ids: List[str], start_year: int, end_year: int) -> Dict[str, Any]:
    """
    Fetch BLS time series for the given IDs and year range.
    Preserves original behavior: optional API key, same URL and payload.
    """
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
# Parsing
# ===========================================================
def _q_to_month(q: int) -> int:
    """Map BLS quarterly period to calendar month (Q1→3, Q2→6, Q3→9, Q4→12)."""
    return {1: 3, 2: 6, 3: 9, 4: 12}[q]

def series_payload_to_rows(series_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Flatten a single series JSON payload into rows: (series_id, date, value).
    Ignores annual averages (M13). Keeps monthly and quarterly (mapped to Mar/Jun/Sep/Dec).
    """
    sid = series_json["seriesID"]
    rows: List[Dict[str, Any]] = []
    for item in series_json["data"]:
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
# I/O
# ===========================================================
def load_existing() -> pd.DataFrame:
    """Load existing CSV (if present) into a DataFrame with parsed dates."""
    if CSV_PATH.exists():
        return pd.read_csv(CSV_PATH, parse_dates=["date"])
    return pd.DataFrame(columns=["series_id", "date", "value"])

def union_and_dedupe(df_old: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """Union old/new rows and drop duplicates by (series_id, date), keeping_
