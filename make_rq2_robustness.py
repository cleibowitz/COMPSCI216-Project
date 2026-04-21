"""
Presentation-quality RQ2 robustness figure — 5Y, 10-day horizon.
Two-panel layout:
  TOP    — side-by-side p-value heatmaps (z<-thr  |  z>+thr)
  BOTTOM — coefficient plot with 95% CIs, both signal directions
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

PROJECT_ROOT = Path(__file__).resolve().parent
FIGURES_DIR  = PROJECT_ROOT / "outputs" / "figures"

# ── Load data ─────────────────────────────────────────────────────────────────

df = pd.read_csv(PROJECT_ROOT / "outputs" / "tables" / "rq2_combinations.csv")
sub = df[(df["maturity"] == "5y") & (df["horizon"] == 10)].copy()
sub["window"]    = sub["window"].astype(int)
sub["threshold"] = sub["threshold"].astype(float)

WINDOWS     = [30, 60, 120]
THRESHOLDS  = [1.5, 2.0, 2.5]
SIG_ALPHA   = 0.05

cheap = sub[sub["direction"] == "negative"].set_index(["window", "threshold"])
rich  = sub[sub["direction"] == "positive"].set_index(["window", "threshold"])

# ── Colour palette ────────────────────────────────────────────────────────────

NAVY      = "#0B2545"
MID_BLUE  = "#1A6FAD"
LIGHT_BLU = "#A8CBE8"
SIG_GRN   = "#1A8F4C"   # significant cell fill
NSIG_RED  = "#C0392B"   # not-significant cell fill
CELL_TEXT = "#FFFFFF"
ZERO_CLR  = "#555555"
CHEAP_CLR = "#1A6FAD"   # z < -thr  →  blue
RICH_CLR  = "#C0392B"   # z > +thr  →  red
BG        = "white"

# ── Figure layout ─────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(14, 16), facecolor=BG)
gs  = gridspec.GridSpec(
    2, 1,
    figure=fig,
    height_ratios=[1, 2.2],
    hspace=0.38,
)

# ── TOP: heatmaps ─────────────────────────────────────────────────────────────

gs_top = gridspec.GridSpecFromSubplotSpec(
    1, 2, subplot_spec=gs[0], wspace=0.30
)
ax_hl = fig.add_subplot(gs_top[0])   # z < -thr
ax_hr = fig.add_subplot(gs_top[1])   # z > +thr


def draw_heatmap(ax, data_idx, title, signal_color):
    nrow, ncol = len(WINDOWS), len(THRESHOLDS)
    cell_w, cell_h = 1.0, 1.0

    for ri, win in enumerate(WINDOWS):
        for ci, thr in enumerate(THRESHOLDS):
            row   = data_idx.loc[(win, thr)]
            pval  = float(row["t_p_bh"])
            is_sig = bool(row["sig_bh"])
            mean  = float(row["mean_bps"])
            n     = int(row["n"])

            fill = SIG_GRN if is_sig else NSIG_RED
            rect = mpl.patches.FancyBboxPatch(
                (ci * cell_w + 0.05, (nrow - 1 - ri) * cell_h + 0.05),
                cell_w - 0.10, cell_h - 0.10,
                boxstyle="round,pad=0.04",
                facecolor=fill, edgecolor=BG, linewidth=0,
                zorder=2,
            )
            ax.add_patch(rect)

            # p-value annotation (top)
            p_str = f"p = {pval:.3f}" if pval >= 0.001 else "p < 0.001"
            ax.text(
                ci * cell_w + cell_w / 2,
                (nrow - 1 - ri) * cell_h + cell_h * 0.62,
                p_str,
                ha="center", va="center",
                fontsize=10.5, fontweight="bold",
                color=CELL_TEXT, zorder=3,
            )

            # mean + n annotation (bottom)
            sign = "+" if mean >= 0 else ""
            ax.text(
                ci * cell_w + cell_w / 2,
                (nrow - 1 - ri) * cell_h + cell_h * 0.32,
                f"{sign}{mean:.1f} bps  (n={n})",
                ha="center", va="center",
                fontsize=9, color=CELL_TEXT, alpha=0.92, zorder=3,
            )

    # Axes dressing
    ax.set_xlim(0, ncol)
    ax.set_ylim(0, nrow)
    ax.set_xticks([i + 0.5 for i in range(ncol)])
    ax.set_xticklabels([f"±{t}σ" for t in THRESHOLDS], fontsize=12)
    ax.set_yticks([nrow - 1 - i + 0.5 for i in range(nrow)])
    ax.set_yticklabels([f"{w}d" for w in WINDOWS], fontsize=12)
    ax.set_xlabel("Z-score threshold", fontsize=12, labelpad=8, color=NAVY)
    ax.set_ylabel("Rolling window", fontsize=12, labelpad=8, color=NAVY)

    # Coloured title bar
    ax.set_title(title, fontsize=13, fontweight="bold",
                 color=signal_color, pad=10)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False, colors=NAVY)


draw_heatmap(ax_hl, cheap, "z < −thr  (spread cheap → expect ↑)", CHEAP_CLR)
draw_heatmap(ax_hr, rich,  "z > +thr  (spread rich → expect ↓)",  RICH_CLR)

# Shared heatmap legend
legend_patches = [
    Patch(facecolor=SIG_GRN, label=f"Significant  (p$_{{\\rm BH}}$ < {SIG_ALPHA})"),
    Patch(facecolor=NSIG_RED, label=f"Not significant"),
]
fig.legend(
    handles=legend_patches,
    loc="upper center",
    bbox_to_anchor=(0.50, 0.995),
    ncol=2,
    fontsize=11,
    frameon=True,
    framealpha=0.95,
    edgecolor="#CCCCCC",
    handlelength=1.4,
)

# Section label
fig.text(0.5, 0.965, "Panel A — P-value Heatmaps  (5Y · 10-day horizon)",
         ha="center", va="center", fontsize=14, fontweight="bold", color=NAVY)

# ── BOTTOM: coefficient plot (split into 2 sub-panels) ───────────────────────

gs_bot = gridspec.GridSpecFromSubplotSpec(
    1, 2, subplot_spec=gs[1], wspace=0.55
)
ax_cl = fig.add_subplot(gs_bot[1])   # z < -thr  (positive means, right panel)
ax_cr = fig.add_subplot(gs_bot[0])   # z > +thr  (negative means, left panel)

# Build row lists
cheap_rows = []
rich_rows  = []
for win in WINDOWS:
    for thr in THRESHOLDS:
        c = cheap.loc[(win, thr)]
        r = rich.loc[(win, thr)]
        cheap_rows.append({
            "label": f"{win}d  ±{thr}σ",
            "mean":  float(c["mean_bps"]),
            "lo":    float(c["ci_low_bps"]),
            "hi":    float(c["ci_high_bps"]),
            "sig":   bool(c["sig_bh"]),
            "n":     int(c["n"]),
        })
        rich_rows.append({
            "label": f"{win}d  ±{thr}σ",
            "mean":  float(r["mean_bps"]),
            "lo":    float(r["ci_low_bps"]),
            "hi":    float(r["ci_high_bps"]),
            "sig":   bool(r["sig_bh"]),
            "n":     int(r["n"]),
        })

# y positions (shared between both sub-panels)
n_each = len(cheap_rows)   # 9
y_pos  = np.arange(n_each, 0, -1, dtype=float)


def draw_coef_panel(ax, rows, color, title, x_lo, x_hi, x_step,
                    label_side="right", shade_positive=True):
    for row, y in zip(rows, y_pos):
        alpha_ci = 1.00 if row["sig"] else 0.40
        alpha_pt = 1.00 if row["sig"] else 0.45
        lw_ci    = 2.0  if row["sig"] else 1.3

        # CI bar
        ax.plot([row["lo"], row["hi"]], [y, y],
                color=color, linewidth=lw_ci, alpha=alpha_ci,
                solid_capstyle="butt", zorder=3)
        # End caps
        for x_cap in [row["lo"], row["hi"]]:
            ax.plot([x_cap, x_cap], [y - 0.22, y + 0.22],
                    color=color, linewidth=lw_ci, alpha=alpha_ci, zorder=3)

        # Point
        marker = "o" if row["sig"] else "D"
        ax.scatter(row["mean"], y, color=color, s=65, zorder=5,
                   marker=marker, alpha=alpha_pt,
                   edgecolors="white", linewidths=0.9)

        # n label
        if label_side == "right":
            lx = row["hi"] + abs(x_hi - x_lo) * 0.025
            ha = "left"
        else:
            lx = row["lo"] - abs(x_hi - x_lo) * 0.025
            ha = "right"
        ax.text(lx, y, f"n={row['n']}",
                va="center", ha=ha, fontsize=9, color="#888888", zorder=4)

    # Zero line
    ax.axvline(0, color=ZERO_CLR, linestyle="--", linewidth=1.5,
               alpha=0.75, zorder=2)

    # Correct-side shading
    if shade_positive:
        ax.axvspan(0, x_hi, alpha=0.05, color=color, zorder=1)
    else:
        ax.axvspan(x_lo, 0, alpha=0.05, color=color, zorder=1)

    # y-axis labels (only on left sub-panel)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([row["label"] for row in rows], fontsize=10.5)
    ax.tick_params(axis="y", left=True, right=False, colors=NAVY)

    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_pos.min() - 0.7, y_pos.max() + 0.7)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(x_step))
    ax.tick_params(axis="x", labelsize=11, colors=NAVY)
    ax.set_xlabel("Mean Forward Change (bps)", fontsize=12,
                  labelpad=8, color=NAVY)
    ax.grid(axis="x", color="#EBEBEB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.spines["left"].set_color("#CCCCCC")

    # Title / group label above each panel
    ax.set_title(title, fontsize=12.5, fontweight="bold",
                 color=color, pad=10)


draw_coef_panel(
    ax_cr, rich_rows, RICH_CLR,
    "z > +thr   (spread rich → expect ↓)",
    x_lo=-26, x_hi=4, x_step=5,
    label_side="left", shade_positive=False,
)
draw_coef_panel(
    ax_cl, cheap_rows, CHEAP_CLR,
    "z < −thr   (spread cheap → expect ↑)",
    x_lo=-2, x_hi=9, x_step=2,
    label_side="right", shade_positive=True,
)

# Shared section super-label via ax_cr title area (spans both panels visually)
ax_cr.annotate(
    "Panel B — Coefficient Plot: Mean Forward Change ± 95% CI",
    xy=(0.5, 1.0), xycoords=("figure fraction", "axes fraction"),  # type: ignore[arg-type]
    xytext=(0, 30), textcoords="offset points",
    ha="center", va="bottom",
    fontsize=13.5, fontweight="bold", color=NAVY,
    annotation_clip=False,
)

# Shared legend (bottom-center of the bottom panel area)
legend_coef = [
    Line2D([0], [0], marker="o", color="w", markerfacecolor=NAVY,
           markersize=8, label="Significant  (p$_{\\rm BH}$ < 0.05)"),
    Line2D([0], [0], marker="D", color="w", markerfacecolor="#AAAAAA",
           markersize=7, label="Not significant"),
    Line2D([0], [0], color=ZERO_CLR, linestyle="--",
           linewidth=1.4, label="Zero reference"),
]
ax_cl.legend(handles=legend_coef, loc="lower right", fontsize=10,
             frameon=True, framealpha=0.95, edgecolor="#CCCCCC",
             handlelength=1.5, labelspacing=0.4)


# ── Super-title ───────────────────────────────────────────────────────────────

fig.text(
    0.5, 1.003,
    "RQ2 Robustness: Sign and Magnitude Are Stable Across All 18 Parameter Combinations",
    ha="center", va="bottom", fontsize=15.5, fontweight="bold", color=NAVY,
)
fig.text(
    0.5, 0.991,
    "OIS-Treasury Spread  ·  5Y Maturity  ·  10-Day Forward Horizon  ·  BH-FDR corrected",
    ha="center", va="bottom", fontsize=11, color="#555555",
)

# ── Save ──────────────────────────────────────────────────────────────────────

fig.subplots_adjust(top=0.96, bottom=0.07, left=0.10, right=0.97,
                    hspace=0.45, wspace=0.55)
out = FIGURES_DIR / "rq2_robustness_clean.png"
fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"Saved → {out}")
