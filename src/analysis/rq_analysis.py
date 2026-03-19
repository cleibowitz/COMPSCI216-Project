"""
Research question analysis for Treasury-SOFR relative value.

RQ1: Do spreads mean-revert after extreme z-score signals?
RQ2: How sensitive are results to the normalization window?
RQ3: Does mean-reversion strength vary across rate regimes?

Methodology:
  - For each spread, compute the 5-day forward change in spread level.
  - Condition on z-score breaching +/-2 thresholds.
  - If mean reversion holds, we expect:
      * After z > +2 (spread unusually wide): spread should narrow → negative fwd change
      * After z < -2 (spread unusually tight): spread should widen  → positive fwd change
  - Statistical significance via one-sample t-test (H0: mean fwd change = 0).
"""

import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from pathlib import Path

# ---------- Paths ----------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

SPREAD_COLS = ["spread_2y", "spread_5y", "spread_10y"]
MATURITIES = ["2y", "5y", "10y"]
FWD_HORIZON = 5  # business days


# =========================================================================
# Helpers
# =========================================================================

def _compute_z_for_window(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Compute z-scores for all spreads using a given rolling window."""
    out = df.copy()
    for col, tenor in zip(SPREAD_COLS, MATURITIES):
        roll_mean = out[col].rolling(window=window, min_periods=window).mean()
        roll_std = out[col].rolling(window=window, min_periods=window).std()
        out[f"z_{tenor}"] = (out[col] - roll_mean) / roll_std
    return out


def _mean_reversion_test(df: pd.DataFrame, spread_col: str, z_col: str,
                         signal: str) -> dict:
    """
    Test whether the forward spread change is significantly different from zero
    when the z-score breaches a threshold.

    signal: "z>+2" or "z<-2"
    """
    # 5-day forward change in spread level
    fwd = df[spread_col].shift(-FWD_HORIZON) - df[spread_col]

    if signal == "z>+2":
        mask = df[z_col] > 2
    else:
        mask = df[z_col] < -2

    sample = fwd[mask].dropna()
    n = len(sample)

    if n < 2:
        return {"signal": signal, "mean_forward": np.nan, "t_stat": np.nan,
                "p_value": np.nan, "count": n}

    t_stat, p_value = stats.ttest_1samp(sample, 0)
    return {
        "signal": signal,
        "mean_forward": sample.mean(),
        "t_stat": t_stat,
        "p_value": p_value,
        "count": n,
    }


# =========================================================================
# RQ1: Mean Reversion
# =========================================================================

def rq1_mean_reversion(df: pd.DataFrame) -> pd.DataFrame:
    """
    Test whether spreads mean-revert after extreme z-score readings.

    Economic intuition: SOFR-Treasury spreads reflect funding conditions.
    Extreme deviations from recent norms create relative-value opportunities
    because arbitrageurs and basis traders push spreads back toward fair value.
    If mean reversion exists, we should see:
      - Negative forward changes after z > +2 (spread was too wide, narrows)
      - Positive forward changes after z < -2  (spread was too tight, widens)
    """
    rows = []
    for col, tenor in zip(SPREAD_COLS, MATURITIES):
        z_col = f"z_{tenor}"
        for signal in ["z<-2", "z>+2"]:
            result = _mean_reversion_test(df, col, z_col, signal)
            result["maturity"] = tenor
            rows.append(result)

    results = pd.DataFrame(rows)[["maturity", "signal", "mean_forward",
                                   "t_stat", "p_value", "count"]]

    print("\n--- RQ1: Mean Reversion Test (5-day forward spread change) ---")
    print("  Expectation: z>+2 → negative forward change; z<-2 → positive")
    print(results.to_string(index=False))

    # Interpretation: check whether signs align with mean-reversion hypothesis
    for _, row in results.iterrows():
        if row["count"] < 5:
            continue
        sig = "***" if row["p_value"] < 0.01 else "**" if row["p_value"] < 0.05 else "*" if row["p_value"] < 0.10 else ""
        direction = "confirms" if (
            (row["signal"] == "z>+2" and row["mean_forward"] < 0) or
            (row["signal"] == "z<-2" and row["mean_forward"] > 0)
        ) else "CONTRADICTS"
        print(f"  {row['maturity']} {row['signal']}: {direction} mean reversion "
              f"(mean={row['mean_forward']:+.4f}, p={row['p_value']:.4f}) {sig}")

    return results


# =========================================================================
# RQ2: Window Sensitivity
# =========================================================================

def rq2_window_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Test how the normalization window affects signal quality.

    A short window (30d) adapts quickly but generates more noise.
    A long window (120d) is more stable but slower to detect regime shifts.
    If results are consistent across windows → robust signal.
    If results flip sign or lose significance → fragile, window-dependent.
    """
    windows = [30, 60, 120]
    rows = []

    for window in windows:
        df_w = _compute_z_for_window(df, window)
        for col, tenor in zip(SPREAD_COLS, MATURITIES):
            z_col = f"z_{tenor}"
            for signal in ["z<-2", "z>+2"]:
                result = _mean_reversion_test(df_w, col, z_col, signal)
                result["maturity"] = tenor
                result["window"] = window
                rows.append(result)

    results = pd.DataFrame(rows)[["maturity", "window", "signal",
                                   "mean_forward", "t_stat", "p_value", "count"]]

    print("\n--- RQ2: Window Sensitivity ---")
    print("  Consistent signs across windows = robust signal")
    print(results.to_string(index=False))

    # Interpretation: flag cases where the sign of mean_forward flips
    for tenor in MATURITIES:
        for signal in ["z<-2", "z>+2"]:
            subset = results[(results["maturity"] == tenor) &
                             (results["signal"] == signal)]
            signs = subset["mean_forward"].dropna().apply(np.sign).unique()
            if len(signs) > 1 and 0 not in signs:
                print(f"  WARNING: {tenor} {signal} — sign flips across windows → fragile signal")

    return results


# =========================================================================
# RQ3: Regime Analysis
# =========================================================================

def rq3_regime_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Test whether mean reversion differs in rising vs. falling/stable rate regimes.

    Uses EFFR (Effective Federal Funds Rate) as the regime indicator.
    Rising rates compress credit spreads differently than falling rates—
    during hikes, front-end SOFR rates lead Treasury yields (positive spread),
    while during easing, the relationship can invert.

    Regime definition:
      - 60-day change in EFFR > 0 → "rising"
      - Otherwise → "falling/stable"
    """
    if "EFFR" not in df.columns:
        print("  WARNING: EFFR not in dataset, skipping regime analysis.")
        return pd.DataFrame()

    # Define regime based on trailing 60-day change in fed funds rate
    effr_change = df["EFFR"].diff(60)
    df = df.copy()
    df["regime"] = np.where(effr_change > 0, "rising", "falling/stable")

    rows = []
    for regime in ["rising", "falling/stable"]:
        df_r = df[df["regime"] == regime]
        for col, tenor in zip(SPREAD_COLS, MATURITIES):
            z_col = f"z_{tenor}"
            for signal in ["z<-2", "z>+2"]:
                result = _mean_reversion_test(df_r, col, z_col, signal)
                result["maturity"] = tenor
                result["regime"] = regime
                rows.append(result)

    results = pd.DataFrame(rows)[["maturity", "regime", "signal",
                                   "mean_forward", "t_stat", "p_value", "count"]]

    print("\n--- RQ3: Regime Analysis ---")
    print("  Rising = EFFR increased over trailing 60 days")
    print(results.to_string(index=False))

    # Interpretation
    for tenor in MATURITIES:
        for signal in ["z<-2", "z>+2"]:
            subset = results[(results["maturity"] == tenor) &
                             (results["signal"] == signal)]
            for _, row in subset.iterrows():
                if row["count"] < 5:
                    continue
                direction = "reverts" if (
                    (row["signal"] == "z>+2" and row["mean_forward"] < 0) or
                    (row["signal"] == "z<-2" and row["mean_forward"] > 0)
                ) else "does NOT revert"
                print(f"  {tenor} {signal} in {row['regime']}: {direction} "
                      f"(mean={row['mean_forward']:+.4f}, n={row['count']})")

    return results


# =========================================================================
# Visualization
# =========================================================================

def plot_rq1(results: pd.DataFrame) -> None:
    """Bar chart: mean 5-day forward spread change by signal and maturity."""
    fig, ax = plt.subplots(figsize=(8, 5))
    pivot = results.pivot(index="maturity", columns="signal", values="mean_forward")
    pivot = pivot.reindex(MATURITIES)
    pivot.plot(kind="bar", ax=ax, edgecolor="black", alpha=0.8)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("Mean 5-Day Forward Spread Change (pp)")
    ax.set_title("RQ1: Mean Reversion After Extreme Z-Scores")
    ax.set_xlabel("Maturity")
    ax.legend(title="Signal")
    plt.xticks(rotation=0)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "rq1_mean_reversion.png", dpi=150)
    plt.close(fig)
    print("  Saved rq1_mean_reversion.png")


def plot_rq2(results: pd.DataFrame) -> None:
    """Line plot: mean forward return vs normalization window by maturity."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    for ax, signal in zip(axes, ["z<-2", "z>+2"]):
        subset = results[results["signal"] == signal]
        for tenor in MATURITIES:
            data = subset[subset["maturity"] == tenor]
            ax.plot(data["window"], data["mean_forward"], marker="o", label=tenor)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_xlabel("Rolling Window (days)")
        ax.set_ylabel("Mean 5-Day Forward Spread Change (pp)")
        ax.set_title(f"RQ2: Window Sensitivity — {signal}")
        ax.legend(title="Maturity")
        ax.set_xticks([30, 60, 120])

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "rq2_window_sensitivity.png", dpi=150)
    plt.close(fig)
    print("  Saved rq2_window_sensitivity.png")


def plot_rq3(results: pd.DataFrame) -> None:
    """Bar chart: mean forward return by regime, signal, and maturity."""
    if results.empty:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    for ax, signal in zip(axes, ["z<-2", "z>+2"]):
        subset = results[results["signal"] == signal]
        pivot = subset.pivot(index="maturity", columns="regime", values="mean_forward")
        pivot = pivot.reindex(MATURITIES)
        pivot.plot(kind="bar", ax=ax, edgecolor="black", alpha=0.8)
        ax.axhline(0, color="black", linewidth=0.5)
        ax.set_ylabel("Mean 5-Day Forward Spread Change (pp)")
        ax.set_title(f"RQ3: Regime Analysis — {signal}")
        ax.set_xlabel("Maturity")
        ax.legend(title="Regime")
        plt.sca(ax)
        plt.xticks(rotation=0)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "rq3_regime_analysis.png", dpi=150)
    plt.close(fig)
    print("  Saved rq3_regime_analysis.png")


# =========================================================================
# Save
# =========================================================================

def save_tables(rq1: pd.DataFrame, rq2: pd.DataFrame, rq3: pd.DataFrame) -> None:
    """Save all result tables as CSVs."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    rq1.to_csv(TABLES_DIR / "rq1_mean_reversion.csv", index=False)
    rq2.to_csv(TABLES_DIR / "rq2_window_sensitivity.csv", index=False)
    if not rq3.empty:
        rq3.to_csv(TABLES_DIR / "rq3_regime_analysis.csv", index=False)
    print(f"  Saved result tables to {TABLES_DIR}/")


# =========================================================================
# Entry point
# =========================================================================

def run_rq_analysis(df: pd.DataFrame) -> None:
    """Run all three research question analyses."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("RQ1: Mean Reversion Test")
    print("=" * 60)
    rq1 = rq1_mean_reversion(df)

    print("\n" + "=" * 60)
    print("RQ2: Window Sensitivity")
    print("=" * 60)
    rq2 = rq2_window_sensitivity(df)

    print("\n" + "=" * 60)
    print("RQ3: Regime Analysis")
    print("=" * 60)
    rq3 = rq3_regime_analysis(df)

    print("\n" + "=" * 60)
    print("Generating RQ Plots")
    print("=" * 60)
    plot_rq1(rq1)
    plot_rq2(rq2)
    plot_rq3(rq3)

    save_tables(rq1, rq2, rq3)


if __name__ == "__main__":
    from src.analysis.eda import load_dataset
    from src.analysis.signals import compute_z_scores

    df = load_dataset()
    df = compute_z_scores(df)
    run_rq_analysis(df)
