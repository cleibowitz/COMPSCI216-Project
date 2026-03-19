"""
Merge Treasury yields and SOFR rates into a single analysis-ready dataset.

Produces spread columns that measure the difference between
SOFR rates and Treasury yields at comparable maturities.
"""

import pandas as pd

from src.utils.config import FINAL_DATASET_PATH


def build_dataset(
    treasury_df: pd.DataFrame,
    sofr_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge Treasury yields with SOFR rates and compute spreads.

    Spread mapping (best-effort maturity alignment):
      - spread_2y:  SOFR30DAYAVG  - DGS2   (short-term proxy)
      - spread_5y:  SOFR90DAYAVG  - DGS5   (medium-term proxy)
      - spread_10y: SOFR180DAYAVG - DGS10  (longest SOFR tenor available)

    Parameters
    ----------
    treasury_df : pd.DataFrame
        Columns: DGS2, DGS5, DGS10
    sofr_df : pd.DataFrame
        Columns: SOFR, SOFR30DAYAVG, SOFR90DAYAVG, SOFR180DAYAVG

    Returns
    -------
    pd.DataFrame
        Combined dataset with yield, rate, and spread columns.
    """
    # Outer join to keep all dates from both sources
    df = treasury_df.join(sofr_df, how="outer")
    df.index.name = "date"
    df = df.sort_index()

    # Forward-fill gaps (weekends, holidays) — limit to 5 days to avoid
    # filling across long data outages
    df = df.ffill(limit=5)

    # Compute spreads: positive = SOFR rate above Treasury yield
    df["spread_2y"] = df["SOFR30DAYAVG"] - df["DGS2"]
    df["spread_5y"] = df["SOFR90DAYAVG"] - df["DGS5"]
    df["spread_10y"] = df["SOFR180DAYAVG"] - df["DGS10"]

    # Drop rows where we have no Treasury AND no SOFR data
    df = df.dropna(how="all")

    # Save final dataset
    FINAL_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(FINAL_DATASET_PATH, index=True)
    print(f"  Saved final dataset to {FINAL_DATASET_PATH}")

    return df


if __name__ == "__main__":
    from src.utils.config import PROCESSED_DATA_DIR, RAW_DATA_DIR

    treasury = pd.read_csv(RAW_DATA_DIR / "treasury_yields.csv", index_col="date", parse_dates=True)
    sofr = pd.read_csv(PROCESSED_DATA_DIR / "sofr_rates_clean.csv", index_col="date", parse_dates=True)
    df = build_dataset(treasury, sofr)
    print(df.head(10))
