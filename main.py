"""
COMPSCI 216 Project — Treasury vs. SOFR OIS Relative Value Pipeline

Entry point that orchestrates:
  1. Fetch Treasury yields + EFFR from FRED
  2. Load SOFR OIS par rates from LSEG CSV exports (2Y, 5Y, 10Y)
  3. Validate OIS data (scale check, NaN handling)
  4. Load MOVE index from LSEG CSV
  5. Merge on date (inner join) and compute spreads + regime indicators
  6. Exploratory data analysis
  7. Z-score signal construction
  8. Research question analysis
"""

from src.data.fetch_fred import fetch_treasury_yields
from src.data.fetch_sofr_futures import load_ois_rates
from src.data.process_sofr import process_ois_rates
from src.data.load_move import load_move_index
from src.data.build_dataset import build_dataset
from src.analysis.eda import run_eda
from src.analysis.signals import run_signals
from src.analysis.rq_analysis import run_rq_analysis


def main():
    # ------ Data Pipeline ------
    print("=" * 60)
    print("Step 1: Fetching Treasury yields and EFFR from FRED")
    print("=" * 60)
    treasury_df = fetch_treasury_yields()
    print(f"  Treasury data: {treasury_df.shape[0]} rows, {list(treasury_df.columns)}\n")

    print("=" * 60)
    print("Step 2: Loading SOFR OIS rates from LSEG CSVs")
    print("=" * 60)
    ois_raw_df = load_ois_rates()
    print(f"  OIS data: {ois_raw_df.shape[0]} rows, {list(ois_raw_df.columns)}\n")

    print("=" * 60)
    print("Step 3: Validating OIS rate data")
    print("=" * 60)
    sofr_clean_df = process_ois_rates(ois_raw_df)
    print()

    print("=" * 60)
    print("Step 4: Loading MOVE index from LSEG CSV")
    print("=" * 60)
    move_series = load_move_index()
    print()

    print("=" * 60)
    print("Step 5: Building final dataset")
    print("=" * 60)
    final_df = build_dataset(treasury_df, sofr_clean_df, move_series)
    print(f"  Shape: {final_df.shape}")
    print(f"  Date range: {final_df.index.min()} to {final_df.index.max()}\n")

    # ------ Analysis ------
    print("=" * 60)
    print("Step 6: Exploratory Data Analysis")
    print("=" * 60)
    final_df = run_eda(final_df)

    print("\n" + "=" * 60)
    print("Step 7: Z-Score Signal Construction")
    print("=" * 60)
    final_df = run_signals(final_df)

    # ------ Research Questions ------
    print("\n" + "=" * 60)
    print("Step 8: Research Question Analysis")
    print("=" * 60)
    run_rq_analysis(final_df)

    # ------ Final Summary ------
    print("\n" + "=" * 60)
    print("Pipeline complete.")
    print("=" * 60)
    print(f"  Dataset shape: {final_df.shape}")
    print(f"\n  Outputs:")
    print(f"    data/processed/final_dataset.parquet")
    print(f"    data/processed/final_dataset_with_signals.parquet")
    print(f"    outputs/figures/*.png")
    print(f"    outputs/tables/*.csv")


if __name__ == "__main__":
    main()
