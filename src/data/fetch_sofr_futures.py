"""
Load SOFR OIS par rates from LSEG Workspace CSV exports.

Each CSV has ~17 rows of metadata followed by a header row
(Date, Exchange Date, Bid, Ask) and daily observations in
descending date order. We compute mid = (Bid + Ask) / 2
and return a single DataFrame indexed by date.

Scale check: LSEG exports rates in percentage points
(e.g. 3.54 = 3.54%), matching the FRED convention for DGS series.
"""

import pandas as pd
from pathlib import Path

from src.utils.config import OIS_2Y_PATH, OIS_5Y_PATH, OIS_10Y_PATH


def _parse_lseg_ois(path: Path, col_name: str) -> pd.Series:
    """
    Parse one LSEG OIS CSV and return a Series of mid-rates.

    Parameters
    ----------
    path : Path
        Path to the LSEG CSV file.
    col_name : str
        Name for the output Series (e.g. 'ois_2y').

    Returns
    -------
    pd.Series
        Mid-rate (percentage points), indexed by date, sorted ascending.
    """
    # Dynamically locate the header row that begins with "Date,"
    # This is robust to LSEG adding or removing metadata rows.
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Date,"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(f"Could not locate 'Date,' header row in {path}")

    # Read only the columns we need: Date (0), Bid (2), Ask (3)
    df = pd.read_csv(
        path,
        skiprows=header_idx,
        encoding="utf-8-sig",
        usecols=[0, 2, 3],
        header=0,
        names=["date", "bid", "ask"],
    )

    # Parse DD-MMM-YYYY date strings (e.g. "15-Apr-2026")
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.set_index("date")

    # Coerce rates to numeric; rows with non-numeric values become NaN
    df["bid"] = pd.to_numeric(df["bid"], errors="coerce")
    df["ask"] = pd.to_numeric(df["ask"], errors="coerce")

    # Compute mid-rate
    s = (df["bid"] + df["ask"]) / 2
    s.name = col_name
    s = s.dropna().sort_index()

    # Scale check: LSEG rates should be in percentage points (e.g. 3.54, not 0.0354).
    # If the maximum observed rate is below 1 the series is likely in decimal form.
    if s.max() < 1.0:
        print(f"  WARNING [{col_name}]: max rate = {s.max():.4f} — "
              f"values appear to be in decimal form, multiplying by 100.")
        s = s * 100

    return s


def load_ois_rates() -> pd.DataFrame:
    """
    Load all three LSEG OIS series and return a combined DataFrame.

    Returns
    -------
    pd.DataFrame
        Columns: ois_2y, ois_5y, ois_10y  (percentage points)
        Index: DatetimeIndex (daily, business days only)
    """
    print("  Loading OIS 2Y from LSEG CSV...")
    s2y = _parse_lseg_ois(OIS_2Y_PATH, "ois_2y")
    print(f"    {len(s2y)} observations  |  "
          f"range {s2y.index.min().date()} to {s2y.index.max().date()}  |  "
          f"mid [{s2y.min():.3f}, {s2y.max():.3f}] pp")

    print("  Loading OIS 5Y from LSEG CSV...")
    s5y = _parse_lseg_ois(OIS_5Y_PATH, "ois_5y")
    print(f"    {len(s5y)} observations  |  "
          f"range {s5y.index.min().date()} to {s5y.index.max().date()}  |  "
          f"mid [{s5y.min():.3f}, {s5y.max():.3f}] pp")

    print("  Loading OIS 10Y from LSEG CSV...")
    s10y = _parse_lseg_ois(OIS_10Y_PATH, "ois_10y")
    print(f"    {len(s10y)} observations  |  "
          f"range {s10y.index.min().date()} to {s10y.index.max().date()}  |  "
          f"mid [{s10y.min():.3f}, {s10y.max():.3f}] pp")

    df = pd.concat([s2y, s5y, s10y], axis=1)
    df.index.name = "date"
    return df


if __name__ == "__main__":
    df = load_ois_rates()
    print("\nSample (last 5 rows):")
    print(df.tail(5))
    print(f"\nShape: {df.shape}")
    print(f"NaN counts:\n{df.isna().sum()}")
