"""
Slide-ready KDE chart: 10-day forward spread change distributions for 5Y,
z < -2 (blue) vs z > +2 (red).  Uses identical event-extraction logic as rq1.py.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from src.analysis.stats_utils import compute_z_scores, extract_signal_events

FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"

# ── Load data & compute z-scores ─────────────────────────────────────────────

df = pd.read_parquet(
    PROJECT_ROOT / "data" / "processed" / "final_dataset_with_signals.parquet"
)
df_z = compute_z_scores(df, window=60)

# ── Extract 5Y, 10d events (same spec as rq1.py) ─────────────────────────────

cheap_pp, _ = extract_signal_events(df_z, "spread_5y", "z_5y",
                                     threshold=2.0, direction="negative",
                                     horizon=10, min_gap=5)
rich_pp, _  = extract_signal_events(df_z, "spread_5y", "z_5y",
                                     threshold=2.0, direction="positive",
                                     horizon=10, min_gap=5)

cheap = cheap_pp * 100   # pp → bps
rich  = rich_pp  * 100

mean_cheap = cheap.mean()
mean_rich  = rich.mean()

# ── Clip x-axis to the main distribution body (drop far-left outliers) ────────
# Percentile-based limits so the chart focuses on where the mass is
x_lo = np.percentile(np.concatenate([cheap, rich]), 1) - 2
x_hi = np.percentile(np.concatenate([cheap, rich]), 99) + 2
x_grid = np.linspace(x_lo, x_hi, 1000)

kde_cheap = gaussian_kde(cheap, bw_method="scott")
kde_rich  = gaussian_kde(rich,  bw_method="scott")

# ── Plot ──────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(12, 5.5))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

BLUE = "#2166AC"
RED  = "#D6604D"

# KDE fills
ax.fill_between(x_grid, kde_cheap(x_grid), alpha=0.18, color=BLUE)
ax.fill_between(x_grid, kde_rich(x_grid),  alpha=0.18, color=RED)

# KDE lines
ax.plot(x_grid, kde_cheap(x_grid), color=BLUE, linewidth=2.5,
        label=f"z < −2  (cheap)    n={len(cheap)},  mean = {mean_cheap:+.2f} bps")
ax.plot(x_grid, kde_rich(x_grid),  color=RED,  linewidth=2.5,
        label=f"z > +2  (rich)      n={len(rich)},  mean = {mean_rich:+.2f} bps")

# Zero reference
ax.axvline(0, color="black", linestyle="--", linewidth=1.4, alpha=0.65, zorder=3,
           label="zero")

# Group mean lines
ax.axvline(mean_cheap, color=BLUE, linestyle="-", linewidth=2.0, alpha=0.80, zorder=4)
ax.axvline(mean_rich,  color=RED,  linestyle="-", linewidth=2.0, alpha=0.80, zorder=4)

# Axis labels & title
ax.set_xlim(x_lo, x_hi)
ax.set_xlabel("Forward Change (bps)", fontsize=16, labelpad=10)
ax.set_ylabel("Density", fontsize=16, labelpad=10)
ax.set_title("Distribution of 10-Day Forward Spread Changes (5Y)",
             fontsize=18, fontweight="bold", pad=14)

# Light horizontal grid only
ax.grid(axis="y", color="#E0E0E0", linewidth=0.7, zorder=0)
ax.set_axisbelow(True)

# Tick fonts
ax.tick_params(axis="both", labelsize=13)

# Clean spines
for spine in ["top", "right"]:
    ax.spines[spine].set_visible(False)
ax.spines["left"].set_color("#CCCCCC")
ax.spines["bottom"].set_color("#CCCCCC")

# Legend (top-left to avoid mean-line clutter on the right)
ax.legend(fontsize=13, loc="upper left", frameon=True,
          framealpha=0.92, edgecolor="#CCCCCC",
          handlelength=1.8, handleheight=1.0)

fig.tight_layout(pad=1.2)

out = FIGURES_DIR / "rq1_distribution_clean.png"
fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved → {out}")
print(f"  z<-2 : n={len(cheap)}, mean={mean_cheap:.2f} bps")
print(f"  z>+2 : n={len(rich)},  mean={mean_rich:.2f} bps")
