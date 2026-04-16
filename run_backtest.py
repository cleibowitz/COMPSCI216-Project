"""Run the OOS backtest on the HMM-augmented dataset."""

from pathlib import Path

import pandas as pd

from src.analysis.backtest import run_backtest

PROJECT_ROOT = Path(__file__).resolve().parents[0]
DATA = PROJECT_ROOT / "outputs" / "ml" / "dataset_with_hmm.parquet"


def main():
    df = pd.read_parquet(DATA)
    print(f"Loaded HMM-augmented dataset: {df.shape}  |  "
          f"{df.index.min().date()} → {df.index.max().date()}")
    run_backtest(df)


if __name__ == "__main__":
    main()
