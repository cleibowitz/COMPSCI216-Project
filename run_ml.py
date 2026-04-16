"""
Run the ML layer: HMM regime detection, then Random Forest classifier.

Assumes the main pipeline has already produced
`data/processed/final_dataset_with_signals.parquet`.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.hmm_regimes import run_hmm
from src.analysis.rf_classifier import run_rf

PROJECT_ROOT = Path(__file__).resolve().parents[0]
DATA = PROJECT_ROOT / "data" / "processed" / "final_dataset_with_signals.parquet"


def _investigate_2y_spikes(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("2Y spread outlier investigation")
    print("=" * 60)
    spike = df[df["spread_2y"] > 1.0][["spread_2y", "ois_2y", "DGS2"]]
    print(f"  Rows with spread_2y > 1.0 pp: {len(spike)}")
    print(spike.round(3).to_string())
    print("\n  Pattern: OIS 2Y jumps ~200bp while DGS2 stays flat, with "
          "immediate reversion. These are LSEG OIS data artifacts.")
    print("  Action: excluding 2Y spread from ML features (using 5Y and 10Y only).")


def main():
    df = pd.read_parquet(DATA)
    print(f"Loaded dataset: {df.shape}  |  "
          f"{df.index.min().date()} → {df.index.max().date()}")

    _investigate_2y_spikes(df)

    df_hmm = run_hmm(df)
    run_rf(df_hmm)

    print("\n" + "=" * 60)
    print("ML pipeline complete.")
    print("=" * 60)
    print("  Outputs:")
    print("    outputs/figures/hmm_regimes.png")
    print("    outputs/figures/rf_roc.png")
    print("    outputs/figures/rf_confusion.png")
    print("    outputs/figures/rf_importance.png")
    print("    outputs/figures/rf_shap.png (if shap available)")
    print("    outputs/ml/rf_model.pkl")
    print("    outputs/ml/rf_events.csv")
    print("    outputs/ml/rf_metrics.csv")
    print("    outputs/ml/dataset_with_hmm.parquet")


if __name__ == "__main__":
    main()
