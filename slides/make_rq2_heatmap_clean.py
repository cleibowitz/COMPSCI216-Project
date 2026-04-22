"""
Clean presentation heatmap — RQ2 robustness, 5Y / 10-day horizon.
Two vertically-stacked 3×3 grids: cheap signal (top) | rich signal (bottom).
Each cell: mean bps (bold) + BH-adjusted p-value.
Colour: deep green = sig, sage = borderline, grey = not sig.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs" / "figures" / "rq2_heatmap_clean.png"

# ── Data ──────────────────────────────────────────────────────────────────────
df  = pd.read_csv(PROJECT_ROOT / "outputs" / "tables" / "rq2_combinations.csv")
sub = df[(df["maturity"] == "5y") & (df["horizon"] == 10)].copy()
sub["window"]    = sub["window"].astype(int)
sub["threshold"] = sub["threshold"].astype(float)

WINDOWS    = [30, 60, 120]
THRESHOLDS = [1.5, 2.0, 2.5]

cheap = sub[sub["direction"] == "negative"].set_index(["window", "threshold"])
rich  = sub[sub["direction"] == "positive"].set_index(["window", "threshold"])

# ── Colours ───────────────────────────────────────────────────────────────────
C_SIG    = "#1A6B3C"
C_BORDER = "#72B585"
C_NSIG   = "#C4C4C4"
NAVY     = "#0B2545"
BG       = "white"

def cell_style(p):
    if   p < 0.05: return C_SIG,    "white"
    elif p < 0.10: return C_BORDER, "#1A1A1A"
    else:          return C_NSIG,   "#444444"

def fmt_p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"

def fmt_mean(v):
    sign = "+" if v >= 0 else "−"
    return f"{sign}{abs(v):.2f} bps"

# ── Figure: two rows, one column ──────────────────────────────────────────────
NR, NC = len(WINDOWS), len(THRESHOLDS)

fig, axes = plt.subplots(2, 1, figsize=(11, 11), facecolor=BG)
fig.subplots_adjust(left=0.18, right=0.96, top=0.88, bottom=0.11, hspace=0.52)

PANELS = [
    ("z < −thr", "Spread cheap → upward reversion",   cheap, "#1A6B3C"),
    ("z > +thr", "Spread rich → downward reversion",  rich,  "#9B2318"),
]

GAP      = 0.045
CORNER_R = 0.12

for ax, (signal_label, subtitle, data_idx, title_color) in zip(axes, PANELS):
    ax.set_facecolor(BG)
    ax.set_xlim(0, NC)
    ax.set_ylim(0, NR)

    for ri, win in enumerate(WINDOWS):
        for ci, thr in enumerate(THRESHOLDS):
            row  = data_idx.loc[(win, thr)]
            pval = float(row["t_p_bh"])
            mean = float(row["mean_bps"])
            fc, tc = cell_style(pval)

            rect = mpatches.FancyBboxPatch(
                (ci + GAP, NR - 1 - ri + GAP),
                1 - 2*GAP, 1 - 2*GAP,
                boxstyle=f"round,pad={CORNER_R}",
                facecolor=fc, edgecolor=BG, linewidth=3,
                zorder=2, clip_on=False,
            )
            ax.add_patch(rect)

            cx = ci + 0.5
            cy = NR - ri - 0.5

            ax.text(cx, cy + 0.13, fmt_mean(mean),
                    ha="center", va="center",
                    fontsize=17, fontweight="bold", color=tc, zorder=3)

            ax.text(cx, cy - 0.17, fmt_p(pval),
                    ha="center", va="center",
                    fontsize=12.5, color=tc, alpha=0.88, zorder=3)

    # x-ticks
    ax.set_xticks([i + 0.5 for i in range(NC)])
    ax.set_xticklabels([f"±{t}σ" for t in THRESHOLDS],
                       fontsize=14, fontweight="bold", color="#333333")

    # y-ticks — drawn as ax.text in axes coords so they are never clipped
    ax.set_yticks([])
    for ri, win in enumerate(WINDOWS):
        cy = NR - ri - 0.5
        ax.text(-0.06, cy, f"{win}d",
                ha="right", va="center",
                fontsize=14, fontweight="bold", color="#333333",
                transform=ax.transData, clip_on=False)

    ax.tick_params(length=0, pad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # "Rolling Window" axis label via fig.text to avoid clipping
    # (positioned in figure coordinates, drawn once per panel via ax.transAxes)
    ax.text(-0.15, 0.5, "Rolling Window",
            ha="center", va="center",
            fontsize=13, fontweight="bold", color=NAVY,
            rotation=90, transform=ax.transAxes, clip_on=False)

    ax.set_title(f"{signal_label}  ·  {subtitle}",
                 fontsize=15, fontweight="bold",
                 color=title_color, pad=14)

# x-axis label only on bottom panel
axes[1].set_xlabel("Z-score Threshold", fontsize=13, labelpad=12,
                   color=NAVY, fontweight="bold")

# ── Super-title ────────────────────────────────────────────────────────────────
fig.text(0.555, 0.975,
         "RQ2 — Mean Reversion Is Robust Across All Parameter Choices",
         ha="center", va="top",
         fontsize=17, fontweight="bold", color=NAVY)

fig.text(0.555, 0.942,
         "5Y OIS-Treasury Spread  ·  10-Day Forward Horizon  ·  BH-FDR Corrected",
         ha="center", va="top", fontsize=12, color="#666666")

# ── Legend ─────────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(facecolor=C_SIG,    edgecolor="none",
                   label="Significant  (p < 0.05)"),
    mpatches.Patch(facecolor=C_BORDER, edgecolor="none",
                   label="Borderline  (0.05 – 0.10)"),
    mpatches.Patch(facecolor=C_NSIG,   edgecolor="none",
                   label="Not significant  (p ≥ 0.10)"),
]
fig.legend(
    handles=legend_items,
    loc="lower center",
    bbox_to_anchor=(0.555, 0.005),
    ncol=3,
    fontsize=12,
    frameon=False,
    handlelength=1.6,
    handleheight=1.1,
    columnspacing=2.0,
)

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, facecolor=BG)
plt.close(fig)
print(f"Saved → {OUT}")
