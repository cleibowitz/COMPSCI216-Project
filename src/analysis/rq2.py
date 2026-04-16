"""
RQ2: Sensitivity and Robustness Analysis
========================================

Runs the full statistical battery across the Cartesian product of
rolling windows (30, 60, 120), z-score thresholds (1.5, 2.0, 2.5),
and forward horizons (5, 10, 20), for each of the three maturities
and each signal direction.

162 cells total (3 × 3 × 3 × 3 × 2). We apply Benjamini-Hochberg
FDR correction across all 162 t-test p-values and report what
fraction of combinations show the sign predicted by mean reversion.

Visualizations focus on the 10-day horizon, 5Y maturity cross-section:
a p-value heatmap and a coefficient plot.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.stats_utils import (
    MATURITIES,
    DIRECTIONS,
    DIR_LABEL,
    EXPECTED_SIGN,
    bh_correct,
    compute_z_scores,
    extract_signal_events,
    run_stat_battery,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

WINDOWS = (30, 60, 120)
THRESHOLDS = (1.5, 2.0, 2.5)
HORIZONS = (5, 10, 20)
MIN_GAP = 5
BOOT_N = 500   # smaller bootstrap for 162 cells to keep runtime reasonable


# ---------------------------------------------------------------------------
# Main grid
# ---------------------------------------------------------------------------

def _build_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Run the battery on every (window, threshold, horizon, maturity, direction) combo."""
    rows = []
    for window in WINDOWS:
        df_z = compute_z_scores(df, window=window)
        for threshold in THRESHOLDS:
            for tenor in MATURITIES:
                spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
                for direction in DIRECTIONS:
                    for horizon in HORIZONS:
                        fwd, _ = extract_signal_events(
                            df_z, spread_col, z_col, threshold, direction,
                            horizon, min_gap=MIN_GAP,
                        )
                        r = run_stat_battery(fwd, n_bootstrap=BOOT_N)
                        expected = EXPECTED_SIGN[direction]
                        mean_sign = (
                            int(np.sign(r["mean_bps"]))
                            if np.isfinite(r["mean_bps"]) else 0
                        )
                        rows.append({
                            "window": window,
                            "threshold": threshold,
                            "maturity": tenor,
                            "signal": DIR_LABEL[direction].replace("thr", f"{threshold}"),
                            "direction": direction,
                            "horizon": horizon,
                            "correct_sign": mean_sign == expected,
                            **r,
                        })

    table = pd.DataFrame(rows)
    p_adj, reject = bh_correct(table["t_pvalue"].values, q=0.05)
    table["t_p_bh"] = p_adj
    table["sig_bh"] = reject
    return table


def _print_stability_summary(table: pd.DataFrame) -> None:
    """Print the RQ2 stability summary."""
    total = len(table)
    total_with_events = (table["n"] >= 5).sum()
    correct = int((table["correct_sign"] & (table["n"] >= 5)).sum())
    n_sig = int(table["sig_bh"].sum())
    pct_correct = 100.0 * correct / max(total_with_events, 1)

    print("\n--- RQ2 Stability Summary ---")
    print(f"  Total combinations:                 {total}")
    print(f"  Combinations with n>=5 events:      {total_with_events}")
    print(f"  Combinations with correct sign:     {correct}  ({pct_correct:.1f}%)")
    print(f"  Combinations significant (BH q<.05): {n_sig}")

    # Break down sign correctness by direction
    print("\n  Sign-correctness by direction (cells with n>=5):")
    for direction in DIRECTIONS:
        sub = table[(table["direction"] == direction) & (table["n"] >= 5)]
        if len(sub) == 0:
            continue
        pct = 100.0 * sub["correct_sign"].sum() / len(sub)
        print(f"    {DIR_LABEL[direction]:10s}: "
              f"{int(sub['correct_sign'].sum()):3d}/{len(sub):3d}  ({pct:.1f}%)")


def _summarize_rq2(table: pd.DataFrame) -> str:
    """Plain-English summary of RQ2."""
    total_with_events = (table["n"] >= 5).sum()
    correct = int((table["correct_sign"] & (table["n"] >= 5)).sum())
    pct_correct = 100.0 * correct / max(total_with_events, 1)
    n_sig = int(table["sig_bh"].sum())
    pct_sig = 100.0 * n_sig / max(total_with_events, 1)

    lines = ["Plain-English summary:"]
    if pct_correct >= 90:
        lines.append(f"  - The mean-reversion sign holds in {pct_correct:.0f}% of "
                     f"combinations (out of {total_with_events} with n≥5).")
    else:
        lines.append(f"  - The mean-reversion sign appears in {pct_correct:.0f}% of "
                     f"combinations — suggesting meaningful modeling sensitivity.")
    lines.append(f"  - {n_sig} combinations ({pct_sig:.0f}%) survive BH FDR correction.")

    # Which parameter drives the most variability? Use range of mean_bps
    # across each parameter holding others fixed (approximate).
    for col in ["window", "threshold", "horizon"]:
        grouped = table.groupby(col)["mean_bps"].mean()
        spread_range = grouped.max() - grouped.min()
        lines.append(f"  - Across {col} levels, average mean forward change "
                     f"spans {spread_range:.2f} bps.")

    lines.append("  - Conclusion: " + (
        "the result is robust to modeling choices." if pct_correct >= 85
        else "results depend materially on parameter choices — interpret with care."
    ))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Visualizations (5Y, 10-day horizon cross-section)
# ---------------------------------------------------------------------------

def _plot_heatmap(table: pd.DataFrame) -> None:
    """Heatmap of t-test p-values (rows=window, cols=threshold) for 5Y h=10."""
    sub = table[(table["maturity"] == "5y") & (table["horizon"] == 10)]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, direction in zip(axes, DIRECTIONS):
        d = sub[sub["direction"] == direction]
        pivot = d.pivot(index="window", columns="threshold", values="t_pvalue")
        pivot = pivot.reindex(index=WINDOWS, columns=THRESHOLDS)

        im = ax.imshow(pivot.values, cmap="RdYlGn_r", vmin=0, vmax=0.1,
                       aspect="auto")
        ax.set_xticks(range(len(THRESHOLDS)))
        ax.set_xticklabels([f"±{t}" for t in THRESHOLDS])
        ax.set_yticks(range(len(WINDOWS)))
        ax.set_yticklabels([f"{w}d" for w in WINDOWS])
        ax.set_xlabel("Z-score threshold")
        ax.set_ylabel("Rolling window")
        ax.set_title(f"5Y, h=10d — {DIR_LABEL[direction]} signals")

        # Annotate each cell with p-value and n
        for i, w in enumerate(WINDOWS):
            for j, th in enumerate(THRESHOLDS):
                cell = d[(d["window"] == w) & (d["threshold"] == th)]
                if len(cell) == 0:
                    continue
                p = cell["t_pvalue"].iloc[0]
                n = int(cell["n"].iloc[0])
                txt = f"p={p:.3f}\nn={n}" if np.isfinite(p) else f"n={n}"
                ax.text(j, i, txt, ha="center", va="center",
                        fontsize=8, color="black")

        fig.colorbar(im, ax=ax, label="t-test p-value (clipped at 0.1)")

    fig.suptitle("RQ2 Heatmap: p-values across (window × threshold) at 5Y, h=10d",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    out = FIGURES_DIR / "rq2_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def _plot_coef(table: pd.DataFrame) -> None:
    """Coefficient plot: mean ± parametric 95% CI across window × threshold for 5Y h=10."""
    sub = table[(table["maturity"] == "5y") & (table["horizon"] == 10)]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, direction in zip(axes, DIRECTIONS):
        d = sub[sub["direction"] == direction].copy()
        d["combo"] = d.apply(
            lambda r: f"w={int(r['window'])} / ±{r['threshold']}", axis=1
        )
        d = d.sort_values(["window", "threshold"]).reset_index(drop=True)
        ypos = np.arange(len(d))
        ax.errorbar(
            d["mean_bps"], ypos,
            xerr=[d["mean_bps"] - d["ci_low_bps"], d["ci_high_bps"] - d["mean_bps"]],
            fmt="o", color="steelblue", ecolor="gray", elinewidth=1,
            capsize=3, markersize=6,
        )
        ax.axvline(0, color="black", linestyle="--", linewidth=0.6)
        ax.set_yticks(ypos)
        ax.set_yticklabels(d["combo"])
        ax.set_xlabel("Mean forward spread change (bps), 95% CI")
        ax.set_title(f"5Y, h=10d — {DIR_LABEL[direction]}")
        ax.grid(axis="x", alpha=0.3)

    fig.suptitle("RQ2 Coefficient Plot: mean forward change ± 95% CI",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    out = FIGURES_DIR / "rq2_coefplot.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_rq2(df: pd.DataFrame) -> pd.DataFrame:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("RQ2: Sensitivity across (window × threshold × horizon)")
    print("=" * 60)
    print("  Running 3 windows × 3 thresholds × 3 horizons × 3 maturities "
          "× 2 directions = 162 cells...")

    table = _build_grid(df)
    _print_stability_summary(table)
    print()
    print(_summarize_rq2(table))

    # Save the full grid
    table.to_csv(TABLES_DIR / "rq2_combinations.csv", index=False)
    print(f"\n  Saved outputs/tables/rq2_combinations.csv ({len(table)} rows)")

    print("\n--- Generating RQ2 figures ---")
    _plot_heatmap(table)
    _plot_coef(table)

    return table
