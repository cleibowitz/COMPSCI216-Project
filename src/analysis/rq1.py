"""
RQ1: Mean Reversion After Extreme Z-Scores
==========================================

Primary specification uses a 60-day rolling window and |z| > 2 threshold,
tested across forward horizons of 5, 10, and 20 business days, separately
for each of the three OIS-Treasury spreads.

For each cell we report the full statistical battery (t-test, sign test,
Wilcoxon signed-rank, Cohen's d, parametric and bootstrap 95% CIs).
Benjamini-Hochberg FDR correction is applied across all 18 t-test p-values.
"""

from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats

from src.analysis.stats_utils import (
    MATURITIES,
    DIRECTIONS,
    DIR_LABEL,
    bh_correct,
    compute_z_scores,
    extract_signal_events,
    run_stat_battery,
    sig_stars,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

WINDOW = 60
THRESHOLD = 2.0
HORIZONS = (5, 10, 20)
MIN_GAP = 5
BOOT_N = 1000


# ---------------------------------------------------------------------------
# Master table
# ---------------------------------------------------------------------------

def _build_master_table(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[tuple, np.ndarray]]:
    """
    Build the RQ1 master table and return (table, samples_by_cell).

    samples_by_cell[(maturity, direction, horizon)] is the array of
    forward changes for that cell — needed later for distribution and
    event-study plots.
    """
    df_z = compute_z_scores(df, window=WINDOW)
    rows: List[dict] = []
    samples: Dict[tuple, np.ndarray] = {}

    for tenor in MATURITIES:
        spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
        for direction in DIRECTIONS:
            for horizon in HORIZONS:
                fwd, _ = extract_signal_events(
                    df_z, spread_col, z_col, THRESHOLD, direction,
                    horizon, min_gap=MIN_GAP,
                )
                samples[(tenor, direction, horizon)] = fwd
                result = run_stat_battery(fwd, n_bootstrap=BOOT_N)
                rows.append({
                    "maturity": tenor,
                    "signal": DIR_LABEL[direction].replace("thr", "2"),
                    "horizon": horizon,
                    **result,
                })

    table = pd.DataFrame(rows)

    # BH correction on t-test p-values across all 18 cells
    p_adj, reject = bh_correct(table["t_pvalue"].values, q=0.05)
    table["t_p_bh"] = p_adj
    table["sig_bh"] = reject

    return table, samples


def _print_master_table(table: pd.DataFrame) -> None:
    """Print the master table in a readable format."""
    print("\n--- RQ1 Master Table (primary spec: window=60, threshold=±2) ---")
    fmt = table.copy()
    for col in ["mean_bps", "ci_low_bps", "ci_high_bps",
                "boot_low_bps", "boot_high_bps"]:
        fmt[col] = fmt[col].round(2)
    for col in ["std_pp", "cohen_d"]:
        fmt[col] = fmt[col].round(3)
    for col in ["t_stat"]:
        fmt[col] = fmt[col].round(2)
    for col in ["t_pvalue", "t_p_bh", "sign_p", "wilcoxon_p"]:
        fmt[col] = fmt[col].apply(lambda p: f"{p:.4f}" if pd.notna(p) else "—")

    cols = ["maturity", "signal", "horizon", "n", "mean_bps", "std_pp",
            "t_stat", "t_pvalue", "t_p_bh", "cohen_d",
            "sign_p", "wilcoxon_p",
            "boot_low_bps", "boot_high_bps", "sig_bh"]
    print(fmt[cols].to_string(index=False))


def _summarize_rq1(table: pd.DataFrame) -> str:
    """Plain-English interpretation of the RQ1 master table."""
    n_sig = int(table["sig_bh"].sum())
    total = len(table)

    # Check sign consistency with mean reversion
    expected_sign = table.apply(
        lambda r: -1 if "z>+" in r["signal"] else +1, axis=1
    )
    actual_sign = np.sign(table["mean_bps"].fillna(0))
    correct_sign = int((expected_sign == actual_sign).sum())

    # Find the strongest cell
    strongest = table.iloc[table["cohen_d"].abs().idxmax()]

    lines = [
        "Plain-English summary:",
        f"  - {n_sig} of {total} cells survive BH FDR correction at q<0.05.",
        f"  - {correct_sign} of {total} cells show the sign predicted by mean "
        f"reversion (negative forward change after z>+2, positive after z<-2).",
        f"  - Strongest effect: {strongest['maturity']} {strongest['signal']} "
        f"at h={int(strongest['horizon'])} days: "
        f"mean={strongest['mean_bps']:.2f} bps, Cohen's d={strongest['cohen_d']:.2f}, "
        f"t-p={strongest['t_pvalue']:.4f}.",
    ]

    if n_sig >= total * 0.7:
        lines.append("  - Conclusion: mean reversion is a pervasive feature — "
                     "nearly every cell rejects H0 after FDR correction.")
    elif n_sig >= total * 0.3:
        lines.append("  - Conclusion: mean reversion is present in a majority "
                     "of cells but not universal.")
    else:
        lines.append("  - Conclusion: the mean-reversion signal is weak — only "
                     "a few cells survive FDR correction.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Distribution + QQ plots for significant cells
# ---------------------------------------------------------------------------

def _plot_distributions(
    table: pd.DataFrame,
    samples: Dict[tuple, np.ndarray],
) -> None:
    """Histogram + QQ plot (2 columns) for each BH-significant cell."""
    sig_rows = table[table["sig_bh"]].sort_values(
        ["maturity", "signal", "horizon"]
    ).reset_index(drop=True)
    n_rows = len(sig_rows)
    if n_rows == 0:
        print("  No BH-significant cells — skipping distribution plots.")
        return

    fig, axes = plt.subplots(n_rows, 2, figsize=(11, 2.8 * n_rows), squeeze=False)

    for i, row in sig_rows.iterrows():
        direction = "positive" if "z>+" in row["signal"] else "negative"
        key = (row["maturity"], direction, int(row["horizon"]))
        data = samples[key] * 100  # to bps

        ax_h = axes[i, 0]
        ax_h.hist(data, bins=30, color="steelblue", edgecolor="black", alpha=0.75)
        ax_h.axvline(0, color="black", linestyle="--", linewidth=0.6)
        ax_h.axvline(data.mean(), color="red", linestyle="-", linewidth=1,
                     label=f"mean={data.mean():.1f} bp")
        ax_h.set_title(f"{row['maturity']} {row['signal']} h={int(row['horizon'])}d "
                       f"(n={row['n']}, t-p(BH)={row['t_p_bh']:.3f})",
                       fontsize=9)
        ax_h.set_xlabel("Forward change (bps)")
        ax_h.set_ylabel("Freq")
        ax_h.legend(fontsize=7, loc="upper right")

        ax_q = axes[i, 1]
        stats.probplot(data, dist="norm", plot=ax_q)
        ax_q.set_title(f"QQ plot vs Normal", fontsize=9)
        ax_q.get_lines()[0].set_markersize(3)

    fig.tight_layout()
    out = FIGURES_DIR / "rq1_distributions.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# Event study: average spread path around signals
# ---------------------------------------------------------------------------

def _event_study_paths(
    df: pd.DataFrame,
    spread_col: str,
    z_col: str,
    direction: str,
    pre: int = 10,
    post: int = 20,
) -> np.ndarray:
    """
    Return an (n_events, pre+post+1) matrix of spread paths around each
    signal event, normalized so the value at t=0 is the spread level at
    that event (path = spread[t+k] - spread[t]).
    """
    if direction == "positive":
        mask = df[z_col].values > THRESHOLD
    else:
        mask = df[z_col].values < -THRESHOLD
    positions = np.where(np.nan_to_num(mask, nan=False))[0]

    # Drop overlaps to keep one path per economic episode
    from src.analysis.stats_utils import _drop_overlapping_positions
    positions = _drop_overlapping_positions(positions, min_gap=MIN_GAP)

    spread = df[spread_col].values
    n = len(spread)
    paths = []
    for p in positions:
        if p - pre < 0 or p + post >= n:
            continue
        window = spread[p - pre: p + post + 1].astype(float)
        if not np.all(np.isfinite(window)):
            continue
        paths.append(window - spread[p])  # normalize at t=0
    return np.array(paths) if paths else np.empty((0, pre + post + 1))


def _plot_event_study(df: pd.DataFrame) -> None:
    """Event study figure: 3 rows (maturity) × 2 cols (direction)."""
    df_z = compute_z_scores(df, window=WINDOW)
    pre, post = 10, 20
    lags = np.arange(-pre, post + 1)
    rng = np.random.default_rng(42)
    n_boot = 500

    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True)
    colors = {"negative": "seagreen", "positive": "firebrick"}

    for i, tenor in enumerate(MATURITIES):
        spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
        for j, direction in enumerate(DIRECTIONS):
            ax = axes[i, j]
            paths = _event_study_paths(df_z, spread_col, z_col, direction, pre, post)
            n_events = paths.shape[0]

            if n_events == 0:
                ax.text(0.5, 0.5, "no events", transform=ax.transAxes,
                        ha="center", va="center")
                ax.set_title(f"{tenor} — {DIR_LABEL[direction].replace('thr','2')} (n=0)")
                continue

            mean_path = paths.mean(axis=0) * 100  # bps

            # Bootstrap CI at each lag
            idx = rng.integers(0, n_events, size=(n_boot, n_events))
            boot_paths = paths[idx].mean(axis=1) * 100
            lo = np.percentile(boot_paths, 2.5, axis=0)
            hi = np.percentile(boot_paths, 97.5, axis=0)

            c = colors[direction]
            ax.fill_between(lags, lo, hi, alpha=0.25, color=c,
                            label="95% boot CI")
            ax.plot(lags, mean_path, color=c, linewidth=1.6, label="mean")
            ax.axvline(0, color="black", linestyle=":", linewidth=0.7)
            ax.axhline(0, color="black", linestyle="--", linewidth=0.5, alpha=0.6)

            sig_label = DIR_LABEL[direction].replace("thr", "2")
            ax.set_title(f"{tenor} — {sig_label}  (n={n_events} events)")
            ax.set_ylabel("Spread change from t=0 (bps)")
            if i == 2:
                ax.set_xlabel("Business days around signal (t=0)")
            ax.legend(fontsize=8, loc="best")

    fig.suptitle("RQ1 Event Study: average spread path around extreme z-score events",
                 fontsize=12, y=1.00)
    fig.tight_layout()
    out = FIGURES_DIR / "rq1_event_study.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_rq1(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full RQ1 analysis; return the master results table."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("RQ1: Mean Reversion — Master Table & Event Study")
    print("=" * 60)

    table, samples = _build_master_table(df)
    _print_master_table(table)
    print()
    print(_summarize_rq1(table))

    table.to_csv(TABLES_DIR / "rq1_master.csv", index=False)
    print(f"\n  Saved outputs/tables/rq1_master.csv")

    print("\n--- Generating RQ1 figures ---")
    _plot_distributions(table, samples)
    _plot_event_study(df)

    return table
