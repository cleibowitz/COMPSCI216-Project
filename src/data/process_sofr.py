"""
Clean and prepare SOFR rate data for merging with Treasury yields.

No futures conversion needed — FRED provides SOFR rates directly.
We just clean missing values and ensure a consistent daily time series.
"""

import pandas as pd


def process_sofr_rates(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean raw SOFR rate data from FRED.

    Parameters
    ----------
    raw_df : pd.DataFrame
        Raw SOFR rates with columns: SOFR, SOFR30DAYAVG, SOFR90DAYAVG, SOFR180DAYAVG

    Returns
    -------
    pd.DataFrame
        Cleaned SOFR rates, NaN-only rows removed.
    """
    # Drop rows where all rates are NaN
    cleaned = raw_df.dropna(how="all")

    print(f"  Cleaned SOFR rates: {cleaned.shape[0]} rows "
          f"(dropped {raw_df.shape[0] - cleaned.shape[0]} all-NaN rows)")

    return cleaned


if __name__ == "__main__":
    from src.utils.config import RAW_DATA_DIR

    raw = pd.read_csv(RAW_DATA_DIR / "sofr_rates_raw.csv", index_col="date", parse_dates=True)
    df = process_sofr_rates(raw)
    print(df.head(10))
    print(f"\nShape: {df.shape}")
