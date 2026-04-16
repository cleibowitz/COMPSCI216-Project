"""
HMM Regime Detection
====================

Fits a 2-state Gaussian HMM on (spread_5y, 60-day EFFR change).
Decodes the Viterbi path, labels the states economically, and
attaches an `hmm_state` column to the dataset.

Also computes an agreement rate vs the manually-defined rate_regime
as a sanity check; below 60% triggers a warning.
"""

from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
ML_DIR = PROJECT_ROOT / "outputs" / "ml"

N_COMPONENTS = 2
RANDOM_STATE = 42


def _fit_hmm(X: np.ndarray) -> GaussianHMM:
    model = GaussianHMM(
        n_components=N_COMPONENTS,
        covariance_type="full",
        n_iter=1000,
        random_state=RANDOM_STATE,
    )
    model.fit(X)
    return model


def _print_state_params(model: GaussianHMM, feature_names) -> None:
    print("\n--- HMM state parameters (in standardized space) ---")
    for s in range(model.n_components):
        print(f"  State {s}:")
        means = dict(zip(feature_names, model.means_[s].round(3)))
        print(f"    mean     = {means}")
        cov = np.round(model.covars_[s], 3)
        print(f"    cov      = {cov.tolist()}")


def _diagnostics(df: pd.DataFrame, state_col: str = "hmm_state") -> None:
    """Compare HMM states to rate_regime, MOVE, spread_5y."""
    print("\n--- HMM state diagnostics ---")
    print(f"  {'state':>6s}  {'n':>5s}  {'%rising':>10s}  "
          f"{'mean_MOVE':>12s}  {'mean_spread5y':>15s}")
    print("  " + "-" * 55)
    for s in sorted(df[state_col].dropna().unique()):
        sub = df[df[state_col] == s]
        n = len(sub)
        pct_rising = 100.0 * sub["rate_regime"].mean()
        mean_move = sub["MOVE"].mean()
        mean_s5 = sub["spread_5y"].mean()
        print(f"  {int(s):>6d}  {n:>5d}  {pct_rising:>9.1f}%  "
              f"{mean_move:>12.2f}  {mean_s5:>15.4f}")


def _label_states(df: pd.DataFrame) -> Tuple[dict, str, str]:
    """
    Label each state as 'stress/trending' or 'stable/mean-reverting'
    based on MOVE level and spread dispersion. Returns:
      labels: {state_id: label}
      stress_name, stable_name
    """
    profile = df.groupby("hmm_state").agg(
        mean_move=("MOVE", "mean"),
        std_spread5y=("spread_5y", "std"),
        pct_rising=("rate_regime", "mean"),
    )
    # Higher MOVE + higher spread dispersion → stress/trending
    profile["score"] = profile["mean_move"] + 100.0 * profile["std_spread5y"]
    stress_state = int(profile["score"].idxmax())
    stable_state = int(profile["score"].idxmin())
    labels = {
        stress_state: "stress/trending",
        stable_state: "stable/mean-reverting",
    }
    print("\n--- State labels ---")
    for s, name in labels.items():
        row = profile.loc[s]
        print(f"  State {s} → {name}  "
              f"(mean MOVE={row['mean_move']:.1f}, "
              f"std(spread_5y)={row['std_spread5y']:.3f}, "
              f"%rising={100 * row['pct_rising']:.1f}%)")
    return labels, stress_state, stable_state


def _transition_matrix(model: GaussianHMM) -> None:
    print("\n--- Transition probability matrix ---")
    trans = model.transmat_
    print("         " + "  ".join(f"S{j}" for j in range(model.n_components)))
    for i in range(model.n_components):
        row = "  ".join(f"{p:.3f}" for p in trans[i])
        expected_dur = 1.0 / (1.0 - trans[i, i]) if trans[i, i] < 1 else np.inf
        print(f"  From S{i}: {row}   (expected dwell ≈ {expected_dur:.1f} days)")


def _agreement_rate(df: pd.DataFrame, stress_state: int) -> float:
    """
    Compare hmm_state to rate_regime. Since the mapping isn't inherent
    (HMM is unsupervised), we report max(agreement, 1-agreement) across
    both possible sign assignments, so the metric is 50-100%.
    """
    hmm_rising = (df["hmm_state"] != stress_state).astype(int)
    raw_agree = (hmm_rising == df["rate_regime"]).mean()
    flipped_agree = (1 - hmm_rising == df["rate_regime"]).mean()
    return max(raw_agree, flipped_agree)


def _plot(df: pd.DataFrame, labels: dict) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)

    colors = {0: "#1f77b4", 1: "#d62728"}
    for ax, col, ylabel in [
        (axes[0], "spread_5y", "OIS 5Y - DGS5 (pp)"),
        (axes[1], "MOVE", "MOVE index (bp)"),
    ]:
        ax.plot(df.index, df[col], color="lightgray", linewidth=0.7, zorder=1)
        for s in sorted(df["hmm_state"].dropna().unique()):
            mask = df["hmm_state"] == s
            ax.scatter(df.index[mask], df[col][mask],
                       s=4, color=colors.get(int(s), "black"),
                       label=f"State {int(s)} — {labels[int(s)]}",
                       zorder=2)
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=9, markerscale=2)

    axes[0].set_title("HMM regime decoding")
    axes[1].set_xlabel("Date")
    fig.tight_layout()
    out = FIGURES_DIR / "hmm_regimes.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def run_hmm(df: pd.DataFrame) -> pd.DataFrame:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    ML_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("HMM Regime Detection (2-state Gaussian)")
    print("=" * 60)

    # Build features: spread_5y and 60-day EFFR change
    feats = pd.DataFrame({
        "spread_5y": df["spread_5y"],
        "effr_change_60d": df["EFFR"].diff(60),
    }).dropna()

    print(f"  Observations: {len(feats)} (2019-present)")

    scaler = StandardScaler()
    X = scaler.fit_transform(feats.values)

    model = _fit_hmm(X)
    print(f"  HMM converged: {model.monitor_.converged}  "
          f"(n_iter={model.monitor_.iter})")

    states = model.predict(X)
    state_series = pd.Series(states, index=feats.index, name="hmm_state")

    out = df.copy()
    out["hmm_state"] = state_series.reindex(out.index)

    _print_state_params(model, ["spread_5y", "effr_change_60d"])
    _diagnostics(out.dropna(subset=["hmm_state", "rate_regime", "MOVE"]))
    labels, stress_state, stable_state = _label_states(
        out.dropna(subset=["hmm_state", "rate_regime", "MOVE"])
    )
    _transition_matrix(model)

    agree = _agreement_rate(
        out.dropna(subset=["hmm_state", "rate_regime"]), stress_state
    )
    print(f"\n--- Sanity check ---")
    print(f"  Agreement with rate_regime: {100 * agree:.1f}%")
    if agree < 0.60:
        print("  ⚠ WARNING: below 60% — HMM may not be tracking a rate-direction regime.")
    else:
        print("  ✓ Above 60% threshold.")

    _plot(out.dropna(subset=["hmm_state"]), labels)

    # Persist for downstream ML
    out.to_parquet(ML_DIR / "dataset_with_hmm.parquet")
    print(f"  Saved dataset with hmm_state to outputs/ml/dataset_with_hmm.parquet")
    return out
