"""
Validate and clean SOFR OIS par-rate data loaded from LSEG CSVs.

The raw OIS DataFrame (ois_2y, ois_5y, ois_10y) has already had
its mid-rate computed and scale verified in fetch_sofr_futures.py.
This module performs final sanity checks and reports data quality.
"""

import pandas as pd


def process_ois_rates(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and validate LSEG OIS rate data.

    Checks performed:
      1. All values should be in percentage-point scale (0 < rate < 15).
      2. Rows where every OIS column is NaN are dropped.
      3. Summary of remaining NaNs is printed for transparency.

    Parameters
    ----------
    raw_df : pd.DataFrame
        Columns: ois_2y, ois_5y, ois_10y  (percentage points)

    Returns
    -------
    pd.DataFrame
        Cleaned OIS rates; rows with all-NaN OIS values removed.
    """
    ois_cols = ["ois_2y", "ois_5y", "ois_10y"]

    # Confirm scale for each column
    for col in ois_cols:
        if col not in raw_df.columns:
            continue
        col_data = raw_df[col].dropna()
        if col_data.empty:
            print(f"  WARNING [{col}]: no non-NaN observations.")
            continue
        if col_data.max() > 15:
            print(f"  WARNING [{col}]: max = {col_data.max():.3f} — "
                  f"unusually high; verify units are percentage points.")
        elif col_data.max() < 1.0:
            print(f"  WARNING [{col}]: max = {col_data.max():.4f} — "
                  f"values may be in decimal form rather than percentage points.")
        else:
            print(f"  [{col}] scale OK — range [{col_data.min():.3f}, {col_data.max():.3f}] pp")

    # Drop rows where all OIS columns are NaN
    before = len(raw_df)
    cleaned = raw_df.dropna(subset=ois_cols, how="all")
    dropped = before - len(cleaned)
    print(f"  Dropped {dropped} all-NaN rows; {len(cleaned)} rows remain.")

    # Report per-column NaN counts
    nan_counts = cleaned[ois_cols].isna().sum()
    if nan_counts.any():
        print(f"  Remaining NaNs per column:\n{nan_counts.to_string()}")

    return cleaned


# Keep old name as an alias so any existing callsites don't break
process_sofr_rates = process_ois_rates


if __name__ == "__main__":
    from src.data.fetch_sofr_futures import load_ois_rates

    raw = load_ois_rates()
    df = process_ois_rates(raw)
    print(df.tail(5))
    print(f"\nShape: {df.shape}")
