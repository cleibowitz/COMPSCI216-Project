"""
Orchestrator for the full RQ1 / RQ2 / RQ3 analysis suite.

RQ1 — Mean reversion after extreme z-score signals (master table,
      distribution + QQ plots for significant cells, event study).
RQ2 — Sensitivity across (window × threshold × horizon) — 162 cells
      with BH FDR correction, heatmap, and coefficient plot.
RQ3 — Regime-conditional analysis (rate, vol, joint 2×2 + ANOVA,
      post-transition windows).

See the individual modules for methodology details.
"""

from typing import Dict

import pandas as pd

from src.analysis.rq1 import run_rq1
from src.analysis.rq2 import run_rq2
from src.analysis.rq3 import run_rq3


def run_rq_analysis(df: pd.DataFrame) -> Dict[str, object]:
    """Run RQ1, RQ2, and RQ3 end-to-end. Returns a dict of result tables."""
    rq1_table = run_rq1(df)
    rq2_table = run_rq2(df)
    rq3_tables = run_rq3(df)

    return {
        "rq1": rq1_table,
        "rq2": rq2_table,
        "rq3": rq3_tables,
    }


if __name__ == "__main__":
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    parquet_path = PROJECT_ROOT / "data" / "processed" / "final_dataset_with_signals.parquet"
    df = pd.read_parquet(parquet_path)
    run_rq_analysis(df)
