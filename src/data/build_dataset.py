"""
Merge Treasury yields, SOFR OIS par rates, and the MOVE index into an
analysis-ready dataset, then construct rate and volatility regime indicators.

Spread construction (matched maturities):
  spread_2y  = ois_2y  - DGS2
  spread_5y  = ois_5y  - DGS5
  spread_10y = ois_10y - DGS10

Regime indicators
-----------------
rate_regime  : 1 if EFFR rose over the trailing 60 calendar rows, else 0
vol_regime   : 1 if MOVE > its rolling 60-day median, else 0
joint_regime : four-way string label combining both
                 "rising+highvol"   "rising+lowvol"
                 "falling+highvol"  "falling+lowvol"
"""

from typing import Optional

import numpy as np
import pandas as pd

from src.utils.config import FINAL_DATASET_PATH

# Rolling window (in trading days) used for both regime indicators
REGIME_WINDOW = 60


def _verify_spreads(df: pd.DataFrame) -> None:
    """Sanity-check spread levels: should be small, mostly negative."""
    spread_cols = ["spread_2y", "spread_5y", "spread_10y"]
    print("\n  Spread sanity check (values in percentage points):")
    print(f"  {'Column':<12} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'Neg%':>8}")
    print("  " + "-" * 52)
    for col in spread_cols:
        data = df[col].dropna()
        mean, std, mn, mx = data.mean(), data.std(), data.min(), data.max()
        pct_neg = (data < 0).mean() * 100
        print(f"  {col:<12} {mean:>8.3f} {std:>8.3f} {mn:>8.3f} {mx:>8.3f} {pct_neg:>7.1f}%")
        if abs(mean) > 2.0:
            print(f"    WARNING: mean spread of {mean:.3f} pp is unusually large — "
                  "check that OIS and Treasury use the same scale.")
        if std < 0.005:
            print(f"    WARNING: std of {std:.4f} pp is nearly zero — spreads may be constant.")


def build_regime_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rate_regime, vol_regime, and joint_regime columns to df.

    rate_regime  : 1 if EFFR(t) > EFFR(t - REGIME_WINDOW), else 0.
                   Requires 'EFFR' column.
    vol_regime   : 1 if MOVE(t) > rolling REGIME_WINDOW-day median of MOVE, else 0.
                   Requires 'MOVE' column.
    joint_regime : "rising"/"falling" + "+" + "highvol"/"lowvol"

    Returns df with the three new columns added in-place.
    """
    if "EFFR" not in df.columns:
        raise KeyError("'EFFR' column required for rate_regime but not found in dataset.")
    if "MOVE" not in df.columns:
        raise KeyError("'MOVE' column required for vol_regime but not found in dataset.")

    # Rate regime: did the fed funds rate rise over the past 60 trading days?
    effr_change = df["EFFR"].diff(REGIME_WINDOW)
    df["rate_regime"] = (effr_change > 0).astype(int)

    # Vol regime: is today's MOVE above its own rolling 60-day median?
    move_median = df["MOVE"].rolling(window=REGIME_WINDOW, min_periods=REGIME_WINDOW).median()
    df["vol_regime"] = (df["MOVE"] > move_median).astype(int)

    # Joint four-way label
    rate_label = df["rate_regime"].map({1: "rising", 0: "falling"})
    vol_label = df["vol_regime"].map({1: "highvol", 0: "lowvol"})
    df["joint_regime"] = rate_label + "+" + vol_label

    # Replace label where either indicator is NaN (burn-in period)
    missing_mask = df["rate_regime"].isna() | df["vol_regime"].isna()
    df.loc[missing_mask, "joint_regime"] = np.nan

    return df


def print_regime_counts(df: pd.DataFrame) -> None:
    """Print observation counts per regime cell."""
    print("\n  Regime observation counts (rows with valid joint_regime):")
    counts = df["joint_regime"].value_counts().reindex(
        ["rising+highvol", "rising+lowvol", "falling+highvol", "falling+lowvol"],
        fill_value=0,
    )
    total = counts.sum()
    print(f"  {'Regime':<22} {'N':>6} {'%':>7}")
    print("  " + "-" * 38)
    for regime, n in counts.items():
        print(f"  {regime:<22} {n:>6}  {n/total*100:>6.1f}%")
    print(f"  {'TOTAL':<22} {total:>6}")

    # Warn about thin cells
    thin = counts[counts < 30]
    if not thin.empty:
        print(f"\n  WARNING: the following cells have fewer than 30 observations and "
              f"may be too thin for reliable t-tests:")
        for regime, n in thin.items():
            print(f"    {regime}: {n}")


def build_dataset(
    treasury_df: pd.DataFrame,
    ois_df: pd.DataFrame,
    move_series: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """
    Merge all data sources, compute spreads, and add regime indicators.

    Parameters
    ----------
    treasury_df : pd.DataFrame
        Columns: DGS2, DGS5, DGS10, EFFR  (from FRED)
    ois_df : pd.DataFrame
        Columns: ois_2y, ois_5y, ois_10y  (from LSEG)
    move_series : pd.Series, optional
        MOVE index (bp), indexed by date  (from LSEG)

    Returns
    -------
    pd.DataFrame
        Combined dataset with yields, OIS rates, spreads, MOVE,
        and regime indicator columns.
    """
    # Inner join: only dates present in both FRED and OIS sources are kept
    df = treasury_df.join(ois_df, how="inner")

    if move_series is not None:
        df = df.join(move_series.rename("MOVE"), how="left")

    df.index.name = "date"
    df = df.sort_index()

    # Forward-fill within each column (limit=5 trading days).
    # Fills Federal holiday NaNs in FRED series and occasional LSEG gaps.
    df = df.ffill(limit=5)

    # Drop rows where every column is NaN
    df = df.dropna(how="all")

    # Matched-maturity spreads
    df["spread_2y"] = df["ois_2y"] - df["DGS2"]
    df["spread_5y"] = df["ois_5y"] - df["DGS5"]
    df["spread_10y"] = df["ois_10y"] - df["DGS10"]

    print(f"  Merged dataset: {df.shape[0]} rows  |  "
          f"{df.index.min().date()} to {df.index.max().date()}")
    if "MOVE" in df.columns:
        move_nans = df["MOVE"].isna().sum()
        print(f"  MOVE column: {df['MOVE'].notna().sum()} observations "
              f"({move_nans} NaN after ffill)")

    _verify_spreads(df)

    # Regime indicators (only if MOVE is present)
    if "MOVE" in df.columns:
        df = build_regime_indicators(df)
        print_regime_counts(df)

    # Save
    FINAL_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(FINAL_DATASET_PATH, index=True)
    print(f"\n  Saved final dataset to {FINAL_DATASET_PATH}")

    return df


if __name__ == "__main__":
    from src.data.fetch_fred import fetch_treasury_yields
    from src.data.fetch_sofr_futures import load_ois_rates
    from src.data.process_sofr import process_ois_rates
    from src.data.load_move import load_move_index

    treasury = fetch_treasury_yields()
    ois = process_ois_rates(load_ois_rates())
    move = load_move_index()
    df = build_dataset(treasury, ois, move)
    print(df[["spread_2y", "spread_5y", "spread_10y",
              "MOVE", "rate_regime", "vol_regime", "joint_regime"]].tail(10))
