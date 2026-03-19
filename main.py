"""
COMPSCI 216 Project — Treasury vs. SOFR Relative Value Pipeline

Entry point that orchestrates:
  1. Fetch Treasury yields from FRED
  2. Fetch SOFR rates from FRED
  3. Clean SOFR data
  4. Merge and compute spreads
  5. Exploratory data analysis
  6. Z-score signal construction
"""

from src.data.fetch_fred import fetch_treasury_yields
from src.data.fetch_sofr_futures import fetch_sofr_rates
from src.data.process_sofr import process_sofr_rates
from src.data.build_dataset import build_dataset
from src.analysis.eda import run_eda
from src.analysis.signals import run_signals
from src.analysis.rq_analysis import run_rq_analysis


def main():
    # ------ Data Pipeline ------
    print("=" * 60)
    print("Step 1: Fetching Treasury yields from FRED")
    print("=" * 60)
    treasury_df = fetch_treasury_yields()
    print(f"  Treasury data: {treasury_df.shape[0]} rows, {list(treasury_df.columns)}\n")

    print("=" * 60)
    print("Step 2: Fetching SOFR rates from FRED")
    print("=" * 60)
    sofr_raw_df = fetch_sofr_rates()
    print(f"  SOFR data: {sofr_raw_df.shape[0]} rows, {list(sofr_raw_df.columns)}\n")

    print("=" * 60)
    print("Step 3: Cleaning SOFR data")
    print("=" * 60)
    sofr_clean_df = process_sofr_rates(sofr_raw_df)
    print()

    print("=" * 60)
    print("Step 4: Building final dataset")
    print("=" * 60)
    final_df = build_dataset(treasury_df, sofr_clean_df)
    print(f"  Shape: {final_df.shape}")
    print(f"  Date range: {final_df.index.min()} to {final_df.index.max()}\n")

    # ------ Analysis ------
    print("=" * 60)
    print("Step 5: Exploratory Data Analysis")
    print("=" * 60)
    final_df = run_eda(final_df)

    print("\n" + "=" * 60)
    print("Step 6: Z-Score Signal Construction")
    print("=" * 60)
    final_df = run_signals(final_df)

    # ------ Research Questions ------
    print("\n" + "=" * 60)
    print("Step 7: Research Question Analysis")
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
