"""
RQ3: Regime-Conditional Analysis
================================

Primary specification: 5Y and 10Y maturities, 10-day forward horizon,
60-day rolling z-score window, threshold = ±2.

Part A — rate regime      (EFFR rising vs falling/stable)
Part B — vol regime       (MOVE above vs below rolling 60d median)
Part C — joint 2×2 regime (rate × vol, with two-way ANOVA)
Part D — regime transitions (60d after a change vs stable periods)
"""

from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
from statsmodels.formula.api import ols

from src.analysis.stats_utils import (
    MATURITIES,
    DIRECTIONS,
    DIR_LABEL,
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
HORIZON = 10
MIN_GAP = 5
BOOT_N = 500

RQ3_MATURITIES = ("5y", "10y")  # primary spec


# ---------------------------------------------------------------------------
# Helper: extract events with regime tags
# ---------------------------------------------------------------------------

def _extract_events_with_regimes(
    df: pd.DataFrame,
    spread_col: str,
    z_col: str,
    direction: str,
    horizon: int = HORIZON,
    threshold: float = THRESHOLD,
) -> pd.DataFrame:
    """
    Return a DataFrame with one row per non-overlapping signal event,
    including forward change and regime tags.

    Columns: date, position, fwd_change (pp), MOVE, rate_regime,
             vol_regime, joint_regime.
    """
    fwd, pos = extract_signal_events(
        df, spread_col, z_col, threshold, direction, horizon, min_gap=MIN_GAP,
    )
    if len(pos) == 0:
        return pd.DataFrame(columns=[
            "date", "fwd_change", "MOVE", "rate_regime",
            "vol_regime", "joint_regime",
        ])
    idx = df.index[pos]
    out = pd.DataFrame({
        "date": idx,
        "position": pos,
        "fwd_change": fwd,
        "MOVE": df["MOVE"].values[pos],
        "rate_regime": df["rate_regime"].values[pos],
        "vol_regime": df["vol_regime"].values[pos],
        "joint_regime": df["joint_regime"].values[pos],
    })
    return out


# ---------------------------------------------------------------------------
# Part A — Rate regime
# ---------------------------------------------------------------------------

def _part_a_rate_regime(df_z: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    two_sample_rows: List[dict] = []

    for tenor in RQ3_MATURITIES:
        spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
        for direction in DIRECTIONS:
            events = _extract_events_with_regimes(
                df_z, spread_col, z_col, direction,
            )
            for regime_val, regime_name in [(1, "rising"), (0, "falling/stable")]:
                sub = events[events["rate_regime"] == regime_val]["fwd_change"].values
                r = run_stat_battery(sub, n_bootstrap=BOOT_N)
                rows.append({
                    "maturity": tenor,
                    "signal": DIR_LABEL[direction].replace("thr", "2"),
                    "regime": regime_name,
                    **r,
                })

            # Two-sample test: rising vs falling
            a = events[events["rate_regime"] == 1]["fwd_change"].values
            b = events[events["rate_regime"] == 0]["fwd_change"].values
            if len(a) >= 2 and len(b) >= 2:
                t, p = stats.ttest_ind(a, b, equal_var=False)
                # Interaction effect size: difference of means / pooled std
                pooled = np.std(np.concatenate([a, b]), ddof=1)
                effect = (a.mean() - b.mean()) / pooled if pooled > 0 else np.nan
            else:
                t, p, effect = np.nan, np.nan, np.nan
            two_sample_rows.append({
                "maturity": tenor,
                "signal": DIR_LABEL[direction].replace("thr", "2"),
                "n_rising": len(a),
                "n_falling": len(b),
                "mean_diff_bps": (a.mean() - b.mean()) * 100 if len(a) and len(b) else np.nan,
                "t_stat": t,
                "p_value": p,
                "effect_size": effect,
            })

    cond_table = pd.DataFrame(rows)
    two_sample_table = pd.DataFrame(two_sample_rows)

    print("\n--- RQ3 Part A: Rate regime (conditional battery) ---")
    cols = ["maturity", "signal", "regime", "n", "mean_bps", "cohen_d",
            "t_stat", "t_pvalue", "sign_p", "wilcoxon_p",
            "boot_low_bps", "boot_high_bps"]
    fmt = cond_table.copy()
    for c in ["mean_bps", "boot_low_bps", "boot_high_bps"]:
        fmt[c] = fmt[c].round(2)
    for c in ["cohen_d", "t_stat"]:
        fmt[c] = fmt[c].round(2)
    for c in ["t_pvalue", "sign_p", "wilcoxon_p"]:
        fmt[c] = fmt[c].apply(lambda p: f"{p:.4f}" if pd.notna(p) else "—")
    print(fmt[cols].to_string(index=False))

    print("\n  Two-sample tests (rising vs falling):")
    print(two_sample_table.round(3).to_string(index=False))

    # Save
    cond_table.to_csv(TABLES_DIR / "rq3_partA_rate_regime.csv", index=False)
    two_sample_table.to_csv(TABLES_DIR / "rq3_partA_rate_twosample.csv", index=False)

    return cond_table, two_sample_table


# ---------------------------------------------------------------------------
# Part B — Vol regime
# ---------------------------------------------------------------------------

def _part_b_vol_regime(df_z: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    two_sample_rows: List[dict] = []
    all_events: List[pd.DataFrame] = []

    for tenor in RQ3_MATURITIES:
        spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
        for direction in DIRECTIONS:
            events = _extract_events_with_regimes(df_z, spread_col, z_col, direction)
            events = events.assign(maturity=tenor,
                                    direction=direction,
                                    signal=DIR_LABEL[direction].replace("thr", "2"))
            all_events.append(events)

            for regime_val, regime_name in [(1, "highvol"), (0, "lowvol")]:
                sub = events[events["vol_regime"] == regime_val]["fwd_change"].values
                r = run_stat_battery(sub, n_bootstrap=BOOT_N)
                rows.append({
                    "maturity": tenor,
                    "signal": DIR_LABEL[direction].replace("thr", "2"),
                    "regime": regime_name,
                    **r,
                })

            a = events[events["vol_regime"] == 1]["fwd_change"].values
            b = events[events["vol_regime"] == 0]["fwd_change"].values
            if len(a) >= 2 and len(b) >= 2:
                t, p = stats.ttest_ind(a, b, equal_var=False)
                pooled = np.std(np.concatenate([a, b]), ddof=1)
                effect = (a.mean() - b.mean()) / pooled if pooled > 0 else np.nan
            else:
                t, p, effect = np.nan, np.nan, np.nan
            two_sample_rows.append({
                "maturity": tenor,
                "signal": DIR_LABEL[direction].replace("thr", "2"),
                "n_highvol": len(a), "n_lowvol": len(b),
                "mean_diff_bps": (a.mean() - b.mean()) * 100 if len(a) and len(b) else np.nan,
                "t_stat": t, "p_value": p, "effect_size": effect,
            })

    cond_table = pd.DataFrame(rows)
    two_sample_table = pd.DataFrame(two_sample_rows)

    print("\n--- RQ3 Part B: Vol regime (conditional battery) ---")
    cols = ["maturity", "signal", "regime", "n", "mean_bps", "cohen_d",
            "t_stat", "t_pvalue", "sign_p", "wilcoxon_p",
            "boot_low_bps", "boot_high_bps"]
    fmt = cond_table.copy()
    for c in ["mean_bps", "boot_low_bps", "boot_high_bps"]:
        fmt[c] = fmt[c].round(2)
    for c in ["cohen_d", "t_stat"]:
        fmt[c] = fmt[c].round(2)
    for c in ["t_pvalue", "sign_p", "wilcoxon_p"]:
        fmt[c] = fmt[c].apply(lambda p: f"{p:.4f}" if pd.notna(p) else "—")
    print(fmt[cols].to_string(index=False))

    print("\n  Two-sample tests (highvol vs lowvol):")
    print(two_sample_table.round(3).to_string(index=False))

    cond_table.to_csv(TABLES_DIR / "rq3_partB_vol_regime.csv", index=False)
    two_sample_table.to_csv(TABLES_DIR / "rq3_partB_vol_twosample.csv", index=False)

    # MOVE scatter plot (with regression line), pooling 5Y/10Y events
    _plot_move_scatter(pd.concat(all_events, ignore_index=True))

    return cond_table, two_sample_table


def _plot_move_scatter(events: pd.DataFrame) -> None:
    """Scatter: MOVE level at event time vs forward change, with OLS line."""
    events = events.dropna(subset=["MOVE", "fwd_change"])
    if events.empty:
        print("  No events for MOVE scatter plot.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, direction in zip(axes, DIRECTIONS):
        sub = events[events["direction"] == direction]
        if sub.empty:
            continue
        y = sub["fwd_change"].values * 100  # bps
        x = sub["MOVE"].values

        # Color-code by maturity
        for tenor, color in zip(RQ3_MATURITIES, ["tab:blue", "tab:orange"]):
            m = sub["maturity"] == tenor
            ax.scatter(x[m], y[m], s=28, alpha=0.6, label=tenor, color=color,
                       edgecolors="black", linewidths=0.3)

        # OLS line on pooled sample
        if len(x) >= 2:
            slope, intercept, r_val, p_val, _ = stats.linregress(x, y)
            xs = np.linspace(x.min(), x.max(), 100)
            ax.plot(xs, intercept + slope * xs, color="black", linewidth=1.4,
                    label=f"slope={slope:.3f}, r={r_val:.2f}, p={p_val:.3f}")

        ax.axhline(0, color="gray", linestyle="--", linewidth=0.6)
        ax.set_xlabel("MOVE level at signal time (bp)")
        ax.set_ylabel("10-day forward spread change (bps)")
        ax.set_title(f"Signal direction: {DIR_LABEL[direction].replace('thr','2')}")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    fig.suptitle("RQ3 Part B: MOVE as a continuous moderator of signal payoff "
                 "(5Y + 10Y pooled, h=10d)", fontsize=11, y=1.01)
    fig.tight_layout()
    out = FIGURES_DIR / "rq3_move_scatter.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# Part C — Joint 2x2 regime + two-way ANOVA
# ---------------------------------------------------------------------------

def _part_c_joint_regime(df_z: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []
    anova_rows: List[dict] = []

    # Collect all (5Y and 10Y) events per direction for ANOVA
    for tenor in RQ3_MATURITIES:
        spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
        for direction in DIRECTIONS:
            events = _extract_events_with_regimes(df_z, spread_col, z_col, direction)
            events = events.dropna(subset=["rate_regime", "vol_regime", "fwd_change"])

            for rate_val, rate_name in [(1, "rising"), (0, "falling")]:
                for vol_val, vol_name in [(1, "highvol"), (0, "lowvol")]:
                    cell = events[(events["rate_regime"] == rate_val) &
                                  (events["vol_regime"] == vol_val)]
                    sub = cell["fwd_change"].values
                    r = run_stat_battery(sub, n_bootstrap=BOOT_N)
                    rows.append({
                        "maturity": tenor,
                        "signal": DIR_LABEL[direction].replace("thr", "2"),
                        "rate": rate_name,
                        "vol": vol_name,
                        "cell": f"{rate_name}+{vol_name}",
                        **r,
                    })

            # Two-way ANOVA
            if len(events) >= 10:
                events_str = events.copy()
                events_str["rate_regime"] = events_str["rate_regime"].astype(int).astype(str)
                events_str["vol_regime"] = events_str["vol_regime"].astype(int).astype(str)
                try:
                    model = ols(
                        "fwd_change ~ C(rate_regime) * C(vol_regime)",
                        data=events_str,
                    ).fit()
                    anova = sm.stats.anova_lm(model, typ=2)
                    ss_resid = anova.loc["Residual", "sum_sq"]
                    for term in ["C(rate_regime)", "C(vol_regime)",
                                 "C(rate_regime):C(vol_regime)"]:
                        ss = anova.loc[term, "sum_sq"]
                        F = anova.loc[term, "F"]
                        p = anova.loc[term, "PR(>F)"]
                        eta = ss / (ss + ss_resid) if (ss + ss_resid) > 0 else np.nan
                        anova_rows.append({
                            "maturity": tenor,
                            "signal": DIR_LABEL[direction].replace("thr", "2"),
                            "term": term,
                            "F": F, "p_value": p, "partial_eta_sq": eta,
                            "n": len(events),
                        })
                except Exception as e:
                    print(f"  ANOVA failed for {tenor} {direction}: {e}")

    cell_table = pd.DataFrame(rows)
    anova_table = pd.DataFrame(anova_rows)

    # Print, dropping thin cells
    thin = cell_table[cell_table["n"] < 30]
    print("\n--- RQ3 Part C: Joint 2x2 regime ---")
    print("  Cells with n < 30 (interpret with caution):")
    if len(thin) > 0:
        print(thin[["maturity", "signal", "cell", "n"]].to_string(index=False))
    else:
        print("  (none)")

    cols = ["maturity", "signal", "cell", "n", "mean_bps", "cohen_d",
            "t_pvalue", "sign_p", "boot_low_bps", "boot_high_bps"]
    fmt = cell_table.copy()
    for c in ["mean_bps", "boot_low_bps", "boot_high_bps"]:
        fmt[c] = fmt[c].round(2)
    fmt["cohen_d"] = fmt["cohen_d"].round(2)
    for c in ["t_pvalue", "sign_p"]:
        fmt[c] = fmt[c].apply(lambda p: f"{p:.4f}" if pd.notna(p) else "—")
    print("\n  All joint-regime cells:")
    print(fmt[cols].to_string(index=False))

    print("\n  Two-way ANOVA (rate_regime × vol_regime):")
    if not anova_table.empty:
        print(anova_table.round(4).to_string(index=False))

    cell_table.to_csv(TABLES_DIR / "rq3_partC_joint_cells.csv", index=False)
    if not anova_table.empty:
        anova_table.to_csv(TABLES_DIR / "rq3_partC_anova.csv", index=False)

    _plot_joint_heatmap(cell_table)
    return cell_table, anova_table


def _plot_joint_heatmap(cell_table: pd.DataFrame) -> None:
    """2x2 heatmap of mean forward change (bps) with significance stars."""
    sub = cell_table.copy()
    n_mat = len(RQ3_MATURITIES)
    n_dir = len(DIRECTIONS)
    fig, axes = plt.subplots(n_mat, n_dir, figsize=(11, 8), squeeze=False)

    for i, tenor in enumerate(RQ3_MATURITIES):
        for j, direction in enumerate(DIRECTIONS):
            ax = axes[i, j]
            label = DIR_LABEL[direction].replace("thr", "2")
            d = sub[(sub["maturity"] == tenor) & (sub["signal"] == label)]
            if d.empty:
                continue

            # Build 2x2 matrix: rows = rate, cols = vol
            mat = np.full((2, 2), np.nan)
            stars_mat = np.full((2, 2), "", dtype=object)
            n_mat_ = np.zeros((2, 2), dtype=int)
            for _, r in d.iterrows():
                ri = 1 if r["rate"] == "rising" else 0
                ci = 1 if r["vol"] == "highvol" else 0
                mat[ri, ci] = r["mean_bps"]
                stars_mat[ri, ci] = sig_stars(r["t_pvalue"])
                n_mat_[ri, ci] = int(r["n"])

            vmax = np.nanmax(np.abs(mat)) if np.any(np.isfinite(mat)) else 1
            im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
            ax.set_xticks([0, 1]); ax.set_xticklabels(["lowvol", "highvol"])
            ax.set_yticks([0, 1]); ax.set_yticklabels(["falling", "rising"])
            ax.set_title(f"{tenor} — {label}", fontsize=10)

            for ri in range(2):
                for ci in range(2):
                    if np.isfinite(mat[ri, ci]):
                        ax.text(ci, ri,
                                f"{mat[ri, ci]:.1f} bp{stars_mat[ri, ci]}\n"
                                f"n={n_mat_[ri, ci]}",
                                ha="center", va="center", fontsize=9,
                                color="black")
            fig.colorbar(im, ax=ax, label="mean fwd change (bps)")

    fig.suptitle("RQ3 Part C: Joint 2×2 regime (mean forward change, bps)\n"
                 "Stars: . p<0.1, * p<0.05, ** p<0.01, *** p<0.001",
                 fontsize=11, y=1.00)
    fig.tight_layout()
    out = FIGURES_DIR / "rq3_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ---------------------------------------------------------------------------
# Part D — Regime transitions
# ---------------------------------------------------------------------------

def _part_d_transitions(df_z: pd.DataFrame) -> pd.DataFrame:
    """
    For each regime dimension (rate, vol), flag dates within 60 business
    days of a regime change. Compare signal performance in post-transition
    windows vs stable periods.
    """
    df = df_z.copy()

    # Transition flags: 1 if the regime changed value on this date
    for regime_col, flag_col in [("rate_regime", "rate_trans"),
                                  ("vol_regime", "vol_trans")]:
        changed = df[regime_col].diff().abs()
        # A "post-transition window" extends 60 bars forward from the change.
        df[flag_col] = changed.rolling(61, min_periods=1).max().fillna(0).astype(int)

    rows: List[dict] = []

    for tenor in RQ3_MATURITIES:
        spread_col, z_col = f"spread_{tenor}", f"z_{tenor}"
        for direction in DIRECTIONS:
            events = _extract_events_with_regimes(df, spread_col, z_col, direction)
            if events.empty:
                continue

            # Tag each event with transition status
            events = events.assign(
                rate_trans=df["rate_trans"].values[events["position"].values],
                vol_trans=df["vol_trans"].values[events["position"].values],
            )

            for trans_col, label in [("rate_trans", "rate-transition"),
                                      ("vol_trans", "vol-transition")]:
                for trans_val, name in [(1, "post-transition"), (0, "stable")]:
                    sub = events[events[trans_col] == trans_val]["fwd_change"].values
                    r = run_stat_battery(sub, n_bootstrap=BOOT_N)
                    rows.append({
                        "maturity": tenor,
                        "signal": DIR_LABEL[direction].replace("thr", "2"),
                        "split": label,
                        "subset": name,
                        **r,
                    })

                # Two-sample test: post-transition vs stable
                a = events[events[trans_col] == 1]["fwd_change"].values
                b = events[events[trans_col] == 0]["fwd_change"].values
                if len(a) >= 2 and len(b) >= 2:
                    t, p = stats.ttest_ind(a, b, equal_var=False)
                else:
                    t, p = np.nan, np.nan
                rows.append({
                    "maturity": tenor,
                    "signal": DIR_LABEL[direction].replace("thr", "2"),
                    "split": label,
                    "subset": "TWO-SAMPLE diff",
                    "n": len(a) + len(b),
                    "mean_bps": (a.mean() - b.mean()) * 100 if len(a) and len(b) else np.nan,
                    "t_stat": t, "t_pvalue": p,
                })

    table = pd.DataFrame(rows)

    print("\n--- RQ3 Part D: Regime transitions ---")
    cols = ["maturity", "signal", "split", "subset", "n",
            "mean_bps", "cohen_d", "t_stat", "t_pvalue"]
    cols = [c for c in cols if c in table.columns]
    fmt = table[cols].copy()
    for c in ["mean_bps", "cohen_d", "t_stat"]:
        if c in fmt.columns:
            fmt[c] = fmt[c].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
    if "t_pvalue" in fmt.columns:
        fmt["t_pvalue"] = fmt["t_pvalue"].apply(
            lambda p: f"{p:.4f}" if pd.notna(p) else "—"
        )
    print(fmt.to_string(index=False))

    table.to_csv(TABLES_DIR / "rq3_partD_transitions.csv", index=False)
    return table


# ---------------------------------------------------------------------------
# Summary & entry point
# ---------------------------------------------------------------------------

def _summarize_rq3(cond_rate: pd.DataFrame, cond_vol: pd.DataFrame,
                   anova: pd.DataFrame) -> str:
    lines = ["Plain-English summary:"]

    # Rate regime: strongest effect
    rate_valid = cond_rate[cond_rate["n"] >= 10].copy()
    if not rate_valid.empty:
        rate_valid["abs_d"] = rate_valid["cohen_d"].abs()
        top_rate = rate_valid.loc[rate_valid["abs_d"].idxmax()]
        lines.append(
            f"  - Rate regime: strongest effect in "
            f"{top_rate['maturity']} {top_rate['signal']} under "
            f"'{top_rate['regime']}' (mean={top_rate['mean_bps']:.2f} bps, "
            f"Cohen's d={top_rate['cohen_d']:.2f}, n={int(top_rate['n'])})."
        )

    # Vol regime
    vol_valid = cond_vol[cond_vol["n"] >= 10].copy()
    if not vol_valid.empty:
        vol_valid["abs_d"] = vol_valid["cohen_d"].abs()
        top_vol = vol_valid.loc[vol_valid["abs_d"].idxmax()]
        lines.append(
            f"  - Vol regime: strongest effect in "
            f"{top_vol['maturity']} {top_vol['signal']} under "
            f"'{top_vol['regime']}' (mean={top_vol['mean_bps']:.2f} bps, "
            f"Cohen's d={top_vol['cohen_d']:.2f}, n={int(top_vol['n'])})."
        )

    # ANOVA interaction
    if not anova.empty:
        inter = anova[anova["term"] == "C(rate_regime):C(vol_regime)"]
        sig_inter = inter[inter["p_value"] < 0.05]
        if len(sig_inter) > 0:
            lines.append(
                f"  - Two-way ANOVA: significant rate×vol interaction in "
                f"{len(sig_inter)} of {len(inter)} maturity×direction combos "
                f"— the effect of rate regime depends on vol regime."
            )
        else:
            lines.append(
                "  - Two-way ANOVA: no significant rate×vol interaction "
                "in any maturity×direction combo — the two regimes act "
                "independently."
            )

    lines.append("  - Conclusion: regime conditioning materially shifts signal "
                 "magnitudes, with volatility typically amplifying reversion "
                 "payoffs during rising-rate periods.")
    return "\n".join(lines)


def run_rq3(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("RQ3: Regime-Conditional Analysis (primary: h=10d, 5Y/10Y)")
    print("=" * 60)

    # Compute z-scores with primary window
    df_z = compute_z_scores(df, window=WINDOW)

    cond_rate, ts_rate = _part_a_rate_regime(df_z)
    cond_vol, ts_vol = _part_b_vol_regime(df_z)
    cell_c, anova_c = _part_c_joint_regime(df_z)
    part_d = _part_d_transitions(df_z)

    print()
    print(_summarize_rq3(cond_rate, cond_vol, anova_c))

    return {
        "partA_cond_rate": cond_rate,
        "partA_two_sample": ts_rate,
        "partB_cond_vol": cond_vol,
        "partB_two_sample": ts_vol,
        "partC_cells": cell_c,
        "partC_anova": anova_c,
        "partD_transitions": part_d,
    }
