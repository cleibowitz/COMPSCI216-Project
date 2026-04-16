"""
Fetch U.S. Treasury yield and EFFR data from the FRED API.

Pulls DGS2, DGS5, DGS10, and EFFR (daily) and returns a single DataFrame
indexed by date with one column per series. EFFR is included here because
it is needed for regime classification (RQ3) and is no longer fetched
alongside SOFR averages.
"""

import pandas as pd
from fredapi import Fred

from src.utils.config import FRED_API_KEY, TREASURY_SERIES, START_DATE, END_DATE, RAW_DATA_DIR


def fetch_treasury_yields() -> pd.DataFrame:
    """
    Download Treasury yield and EFFR series from FRED.

    Returns
    -------
    pd.DataFrame
        Columns: DGS2, DGS5, DGS10, EFFR  (percent, e.g. 4.25 = 4.25%)
        Index: DatetimeIndex (daily, business days only)
    """
    if not FRED_API_KEY:
        raise EnvironmentError(
            "FRED_API_KEY not set. Export it as an environment variable:\n"
            "  export FRED_API_KEY='your_key_here'"
        )

    fred = Fred(api_key=FRED_API_KEY)
    frames = {}

    for series_id, label in TREASURY_SERIES.items():
        print(f"  Fetching {series_id} ({label}) from FRED...")
        s = fred.get_series(series_id, observation_start=START_DATE, observation_end=END_DATE)
        s.name = series_id
        frames[series_id] = s

    df = pd.DataFrame(frames)
    df.index.name = "date"

    # FRED returns "." for missing observations; coerce to numeric
    df = df.apply(pd.to_numeric, errors="coerce")

    # Save raw data
    raw_path = RAW_DATA_DIR / "treasury_yields.csv"
    df.to_csv(raw_path)
    print(f"  Saved raw Treasury yields to {raw_path}")

    return df


if __name__ == "__main__":
    df = fetch_treasury_yields()
    print(df.head(10))
    print(f"\nShape: {df.shape}")
