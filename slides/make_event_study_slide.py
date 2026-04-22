"""
Generate a presentation-ready event study chart for the CS216 project slide deck.

Uses the 5Y OIS-Treasury spread with z > +2 / z < -2 signal definition,
60-day rolling window, min_gap=5 non-overlap filter.

Saves: outputs/figures/event_study_slide.png
       outputs/figures/event_study_slide.pdf
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DATA  = ROOT / "data" / "processed" / "final_dataset_with_signals.parquet"
OUT   = ROOT / "outputs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ── Parameters (match project primary spec) ──────────────────────────────────
WINDOW    = 60
THRESHOLD = 2.0
MIN_GAP   = 5
PRE       = 10
POST      = 20
N_BOOT    = 2000
RNG       = np.random.default_rng(42)

SPREAD_COL = "spread_5y"
Z_COL      = "z_5y"

# ── Load data ─────────────────────────────────────────────────────────────────
df = pd.read_parquet(DATA).sort_index()
spread = df[SPREAD_COL].values
z      = df[Z_COL].values

# ── Non-overlap filter (mirrors stats_utils._drop_overlapping_positions) ─────
def drop_overlapping(positions: np.ndarray, min_gap: int) -> np.ndarray:
    kept = []
    last = -min_gap - 1
    for p in positions:
        if p - last >= min_gap:
            kept.append(p)
            last = p
    return np.array(kept, dtype=int)

# ── Extract event-window paths ────────────────────────────────────────────────
def get_paths(mask: np.ndarray) -> np.ndarray:
    positions = drop_overlapping(
        np.where(np.nan_to_num(mask, nan=False))[0], MIN_GAP
    )
    n = len(spread)
    paths = []
    for p in positions:
        if p - PRE < 0 or p + POST >= n:
            continue
        window = spread[p - PRE : p + POST + 1].astype(float)
        if np.all(np.isfinite(window)):
            paths.append((window - spread[p]) * 100)   # bps
    return np.array(paths) if paths else np.empty((0, PRE + POST + 1))

pos_paths = get_paths(z > THRESHOLD)        # spread too high → should revert down
neg_paths = get_paths(z < -THRESHOLD)       # spread too low  → should revert up

lags = np.arange(-PRE, POST + 1)

# ── Bootstrap CI ─────────────────────────────────────────────────────────────
def boot_ci(paths: np.ndarray, n_boot: int = N_BOOT, level: float = 95):
    n = paths.shape[0]
    idx = RNG.integers(0, n, size=(n_boot, n))
    boots = paths[idx].mean(axis=1)          # (n_boot, n_lags)
    lo = np.percentile(boots, (100 - level) / 2,     axis=0)
    hi = np.percentile(boots, 100 - (100 - level) / 2, axis=0)
    return lo, hi

pos_mean = pos_paths.mean(axis=0)
pos_lo, pos_hi = boot_ci(pos_paths)

neg_mean = neg_paths.mean(axis=0)
neg_lo, neg_hi = boot_ci(neg_paths)

n_pos = pos_paths.shape[0]
n_neg = neg_paths.shape[0]

# ── Styling ──────────────────────────────────────────────────────────────────
CRIMSON  = "#C0392B"
NAVY     = "#1A3A5C"
GREY_REF = "#888888"
BG       = "white"

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
fig, ax = plt.subplots(figsize=(13, 5.2))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

# Zero reference
ax.axhline(0, color=GREY_REF, linewidth=0.9, linestyle="--", zorder=1, alpha=0.7)

# ── Confidence bands ─────────────────────────────────────────────────────────
ax.fill_between(lags, pos_lo, pos_hi, color=CRIMSON, alpha=0.13, zorder=2)
ax.fill_between(lags, neg_lo, neg_hi, color=NAVY,    alpha=0.13, zorder=2)

# ── Mean paths ───────────────────────────────────────────────────────────────
ax.plot(lags, pos_mean, color=CRIMSON, linewidth=2.5, zorder=4,
        label=f"Spread Too High  (z > +{THRESHOLD:.0f},  n = {n_pos})")
ax.plot(lags, neg_mean, color=NAVY,    linewidth=2.5, zorder=4,
        label=f"Spread Too Low   (z < −{THRESHOLD:.0f},  n = {n_neg})")

# Signal date vertical line (drawn after paths so it's on top)
ax.axvline(0, color="#222222", linewidth=1.6, linestyle="-", zorder=5)

# ── Signal Date label — placed just above plot area ───────────────────────────
ymin, ymax = ax.get_ylim()
yrange = ymax - ymin
ax.text(0.6, ymax - 0.04 * yrange,
        "Signal Date  (t = 0)",
        fontsize=10.5, color="#222222", ha="left", va="top", zorder=6,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.8))

# ── Axes labels & title ───────────────────────────────────────────────────────
ax.set_xlabel("Trading Days Relative to Signal Date",
              fontsize=13, labelpad=8)
ax.set_ylabel("Spread Change from Signal Date (bps)",
              fontsize=13, labelpad=8)
ax.set_title("Spreads Revert After Extreme Deviations",
             fontsize=17, fontweight="bold", pad=14, loc="left")

# Subtitle
ax.text(0, 1.015,
        "5Y OIS – Treasury Spread  •  60-day rolling z-score  •  |z| > 2.0  •  avg. path ± 95% CI",
        transform=ax.transAxes, fontsize=9.5, color="#666666", va="bottom")

ax.set_xlim(-PRE, POST)
# Force clean integer ticks, exclude 0 from auto-ticks (add it back manually)
ax.set_xticks([-10, -5, 0, 5, 10, 15, 20])
ax.tick_params(labelsize=11)

# Bold the "0" x-tick
for label in ax.get_xticklabels():
    if label.get_text() in ("0",):
        label.set_fontweight("bold")

# ── Legend ───────────────────────────────────────────────────────────────────
ax.legend(fontsize=11, frameon=True, framealpha=0.92,
          edgecolor="#CCCCCC", loc="lower right",
          handlelength=2.2, handletextpad=0.7)

fig.tight_layout()

# ── Save ──────────────────────────────────────────────────────────────────────
png_path = OUT / "event_study_slide.png"
pdf_path = OUT / "event_study_slide.pdf"

fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(pdf_path,           bbox_inches="tight", facecolor=BG)
plt.close(fig)

print(f"Saved PNG → {png_path}")
print(f"Saved PDF → {pdf_path}")
print(f"Events: {n_pos} positive (z > +2),  {n_neg} negative (z < -2)")
