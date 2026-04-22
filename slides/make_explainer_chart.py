"""
Generate the OIS vs Treasury explainer chart for the "What Are OIS–Treasury
Spreads?" slide.

Saves:
    outputs/figures/ois_vs_treasury_spread.png
    outputs/figures/ois_vs_treasury_spread.pdf
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "final_dataset_with_signals.parquet"
OUT  = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Load & clean ──────────────────────────────────────────────────────────────
df = pd.read_parquet(DATA).sort_index()
df = df[["ois_5y", "DGS5", "spread_5y"]].dropna()

dates    = df.index
ois      = df["ois_5y"].values          # percent
treasury = df["DGS5"].values            # percent
spread   = df["spread_5y"].values * 100 # bps (for annotation)

# ── Colour palette ─────────────────────────────────────────────────────────────
C_TREASURY = "#1A3A5C"   # deep navy
C_OIS      = "#C0392B"   # muted crimson (distinct, not neon)
C_FILL_POS = "#C0392B"   # fill when OIS > Treasury (spread positive)
C_FILL_NEG = "#1A3A5C"   # fill when OIS < Treasury (spread negative)
BG         = "white"

# ── Rcparams ──────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.sans-serif":   ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.color":        "#EBEBEB",
    "grid.linewidth":    0.6,
    "axes.axisbelow":    True,
})

# ── Figure ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13.5, 6.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

# ── Shaded spread region ──────────────────────────────────────────────────────
# Split into positive-spread (OIS > Treasury) and negative-spread regions
ax.fill_between(dates, ois, treasury,
                where=(ois >= treasury),
                color=C_FILL_POS, alpha=0.20, linewidth=0, zorder=1)
ax.fill_between(dates, ois, treasury,
                where=(ois < treasury),
                color=C_FILL_NEG, alpha=0.14, linewidth=0, zorder=1)

# ── Main lines ────────────────────────────────────────────────────────────────
ax.plot(dates, treasury, color=C_TREASURY, linewidth=2.2, zorder=3,
        solid_capstyle="round")
ax.plot(dates, ois,      color=C_OIS,      linewidth=2.2, zorder=3,
        solid_capstyle="round")

# ── Direct line labels — end-of-line style, placed to the right of the chart ──
# Extend x-axis slightly and place labels past the last data point
last_date = dates[-1]
label_x   = last_date + pd.Timedelta(days=30)

# Get values at the last data point
ois_end      = ois[-1]
treasury_end = treasury[-1]

# Treasury is typically above OIS; add vertical offset for breathing room
gap = abs(treasury_end - ois_end)
offset = max(0.08, gap * 0.3)

ax.annotate(
    "Treasury Yield",
    xy=(last_date, treasury_end),
    xytext=(label_x, treasury_end + offset),
    fontsize=11, color=C_TREASURY, fontweight="bold",
    ha="left", va="center",
    arrowprops=dict(arrowstyle="-", color=C_TREASURY,
                    lw=1.1, connectionstyle="arc3,rad=0.0"),
    annotation_clip=False,
)

ax.annotate(
    "OIS Rate\n(Swap-Implied)",
    xy=(last_date, ois_end),
    xytext=(label_x, ois_end - offset),
    fontsize=11, color=C_OIS, fontweight="bold",
    ha="left", va="center",
    arrowprops=dict(arrowstyle="-", color=C_OIS,
                    lw=1.1, connectionstyle="arc3,rad=0.0"),
    annotation_clip=False,
)

# ── Spread annotation — point to the June 2022 wide-spread episode ─────────────
# At 2022-06-10: OIS = ~4.6%, Treasury = ~3.2%, spread ≈ +46 bps
ann_date = pd.Timestamp("2022-06-10")
idx_ann  = df.index.get_indexer([ann_date], method="nearest")[0]
mid_y    = (ois[idx_ann] + treasury[idx_ann]) / 2   # midpoint of shaded region

ax.annotate(
    "Spread\n(OIS − Treasury)",
    xy=(ann_date, mid_y),
    xytext=(pd.Timestamp("2021-07-01"), mid_y + 0.90),
    fontsize=10.5, color="#444444", ha="center", va="bottom",
    arrowprops=dict(arrowstyle="-|>", color="#666666",
                    lw=1.1, mutation_scale=10,
                    connectionstyle="arc3,rad=-0.25"),
    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#CCCCCC",
              alpha=0.92, lw=0.8),
)

# ── Axis formatting ───────────────────────────────────────────────────────────
ax.set_ylabel("Yield  (%)", fontsize=13, labelpad=8)
ax.set_xlabel("Date", fontsize=13, labelpad=8)
ax.tick_params(labelsize=11)

ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))

ax.set_xlim(dates[0], dates[-1] + pd.Timedelta(days=200))
# Let y-axis be auto but add a touch of padding
ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo - 0.05, yhi + 0.05)

# ── Title ─────────────────────────────────────────────────────────────────────
ax.set_title(
    "OIS and Treasury Yields Track Similar Rates but Diverge Over Time",
    fontsize=16, fontweight="bold", pad=14, loc="left",
)

# Subtitle
ax.text(0, 1.015,
        "5Y maturity  •  daily data  •  2019 – 2026  •  OIS = SOFR swap rate,  "
        "Treasury = FRED DGS5",
        transform=ax.transAxes, fontsize=9, color="#666666", va="bottom")

fig.tight_layout()

# ── Save ──────────────────────────────────────────────────────────────────────
png = OUT / "ois_vs_treasury_spread.png"
pdf = OUT / "ois_vs_treasury_spread.pdf"
fig.savefig(png, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(pdf,           bbox_inches="tight", facecolor=BG)
plt.close(fig)

print(f"Saved PNG → {png}")
print(f"Saved PDF → {pdf}")
print(f"Date range: {dates[0].date()} to {dates[-1].date()}  ({len(df)} trading days)")
