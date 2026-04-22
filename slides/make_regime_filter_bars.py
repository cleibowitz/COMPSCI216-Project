"""
Bar chart: OOS backtest performance with vs. without HMM regime filtering.
Source: outputs/backtest_metrics.csv
OOS period: 2024-01-01 to 2026-03-24 · 1 bp round-trip cost · daily mark-to-market PnL
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs" / "figures" / "regime_filter_bars.png"

# ── Data (from outputs/backtest_metrics.csv) ──────────────────────────────────
# Strategy 1 = Rules-based (no regime filter)
# Strategy 3 = HMM-filtered (trade only in stable state = State 1)
UNFILTERED = dict(avg_return=0.82,  hit_rate=55.0, sharpe=0.39, n=20)
FILTERED   = dict(avg_return=1.55,  hit_rate=72.7, sharpe=0.51, n=11)

# ── Style ──────────────────────────────────────────────────────────────────────
GRAY   = "#A8B8C8"    # no-filter bars
BLUE   = "#1A3A5C"    # regime-filtered bars
NAVY   = "#0B2545"
BG     = "white"

METRICS = [
    ("avg_return", "Avg Net Return\nper Trade (bps)", "bps", 0, 2.0,  0.5),
    ("hit_rate",   "Win Rate (%)",                     "%",   0, 100,  20),
    ("sharpe",     "Sharpe Ratio\n(Annualised)",        "",    0, 0.8,  0.2),
]

BAR_W = 0.34
X     = np.array([-BAR_W / 2 - 0.02, BAR_W / 2 + 0.02])   # two bars per panel

fig, axes = plt.subplots(1, 3, figsize=(14, 7), facecolor=BG)
fig.subplots_adjust(left=0.06, right=0.97, top=0.72, bottom=0.18,
                    wspace=0.42)

for ax, (key, ylabel, unit, y_lo, y_hi, y_step) in zip(axes, METRICS):
    vals = [UNFILTERED[key], FILTERED[key]]
    colors = [GRAY, BLUE]

    bars = ax.bar(X, vals, width=BAR_W, color=colors,
                  zorder=3, linewidth=0)

    # ── Value labels above bars ────────────────────────────────────────────────
    offset = (y_hi - y_lo) * 0.032
    for xi, (val, clr) in enumerate(zip(vals, colors)):
        if key == "avg_return":
            label = f"+{val:.2f}"
        elif key == "hit_rate":
            label = f"{val:.1f}%"
        else:
            label = f"{val:.2f}"

        ax.text(X[xi], val + offset, label,
                ha="center", va="bottom",
                fontsize=14.5, fontweight="bold", color=clr,
                zorder=5)

    # ── Improvement delta annotation (inside top of filtered bar) ─────────────
    if key == "avg_return":
        delta_str = f"▲ +{FILTERED[key] - UNFILTERED[key]:.2f} bps"
    elif key == "hit_rate":
        delta_str = f"▲ +{FILTERED[key] - UNFILTERED[key]:.1f}pp"
    else:
        delta_str = f"▲ +{FILTERED[key] - UNFILTERED[key]:.2f}"

    # Place delta just above the filtered bar label — right side annotation
    ax.text(X[1], FILTERED[key] + offset * 3.8, delta_str,
            ha="center", va="bottom",
            fontsize=10.5, color="#1A6B3C", fontweight="bold",
            zorder=5)

    # ── Axes dressing ──────────────────────────────────────────────────────────
    ax.set_facecolor(BG)
    ax.set_xlim(-0.65, 0.65)
    ax.set_ylim(y_lo, y_hi)

    ax.set_xticks(X)
    ax.set_xticklabels(
        [f"No Filter\n(n={UNFILTERED['n']})",
         f"HMM Filter\n(n={FILTERED['n']})"],
        fontsize=11.5, color="#333333", fontweight="bold", linespacing=1.5,
    )

    ax.set_ylabel(ylabel, fontsize=13, color=NAVY, labelpad=8)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(y_step))
    ax.tick_params(axis="y", labelsize=11, colors="#444444", length=0)
    ax.tick_params(axis="x", length=0)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")

    ax.yaxis.grid(True, color="#F0F0F0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    # Faint reference bar tray
    ax.axhline(0, color="#CCCCCC", linewidth=0.8, zorder=2)

# ── Super-title ────────────────────────────────────────────────────────────────
fig.text(0.515, 0.995,
         "Regime Filtering Improves Trading Performance",
         ha="center", va="top",
         fontsize=18, fontweight="bold", color=NAVY)

fig.text(0.515, 0.955,
         "OOS Backtest: Jan 2024 – Mar 2026  ·  5Y OIS-Treasury  ·  Net of 1 bp Round-Trip Cost",
         ha="center", va="top",
         fontsize=11.5, color="#666666")

# ── Shared legend ──────────────────────────────────────────────────────────────
from matplotlib.patches import Patch
legend_items = [
    Patch(facecolor=GRAY, edgecolor="none", label="No Regime Filter"),
    Patch(facecolor=BLUE, edgecolor="none", label="HMM-Filtered (Stable / State 1 only)"),
]
fig.legend(
    handles=legend_items,
    loc="upper center",
    bbox_to_anchor=(0.515, 0.915),
    ncol=2, fontsize=12, frameon=False,
    handlelength=1.4, handleheight=1.0, columnspacing=2.5,
)

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, bbox_inches="tight", pad_inches=0.2, facecolor=BG)
plt.close(fig)
print(f"Saved → {OUT}")
