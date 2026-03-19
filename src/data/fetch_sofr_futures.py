"""
Fetch SOFR rate data from FRED.

Pulls the overnight SOFR rate plus 30-day, 90-day, and 180-day
averages — all freely available from the Federal Reserve via FRED.
"""

import pandas as pd
from fredapi import Fred

from src.utils.config import FRED_API_KEY, SOFR_SERIES, START_DATE, END_DATE, RAW_DATA_DIR


def fetch_sofr_rates() -> pd.DataFrame:
    """
    Download SOFR rate series from FRED.

    Returns
    -------
    pd.DataFrame
        Columns: SOFR, SOFR30DAYAVG, SOFR90DAYAVG, SOFR180DAYAVG (percent)
        Index: DatetimeIndex (daily)
    """
    if not FRED_API_KEY:
        raise EnvironmentError(
            "FRED_API_KEY not set. Add it to your .env file:\n"
            "  FRED_API_KEY=your_key_here"
        )

    fred = Fred(api_key=FRED_API_KEY)
    frames = {}

    for series_id, label in SOFR_SERIES.items():
        print(f"  Fetching {series_id} ({label}) from FRED...")
        s = fred.get_series(series_id, observation_start=START_DATE, observation_end=END_DATE)
        s.name = series_id
        frames[series_id] = s

    df = pd.DataFrame(frames)
    df.index.name = "date"
    df = df.apply(pd.to_numeric, errors="coerce")

    # Save raw data
    raw_path = RAW_DATA_DIR / "sofr_rates_raw.csv"
    df.to_csv(raw_path)
    print(f"  Saved raw SOFR rates to {raw_path}")

    return df


if __name__ == "__main__":
    df = fetch_sofr_rates()
    print(df.head(10))
    print(f"\nShape: {df.shape}")
