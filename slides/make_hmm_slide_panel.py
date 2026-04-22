"""
Simplified slide panel: 5Y OIS-Treasury spread + HMM regime shading + signal markers.
Single panel, presentation-ready for left half of a slide.
"""

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis.stats_utils import compute_z_scores, extract_signal_events

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs" / "figures" / "hmm_slide_panel.png"

# ── Data (identical to main analysis) ────────────────────────────────────────
df   = pd.read_parquet(PROJECT_ROOT / "outputs" / "ml" / "dataset_with_hmm.parquet")
df_z = compute_z_scores(df, window=60)

_, cheap_pos = extract_signal_events(df_z, "spread_5y", "z_5y", 2.0, "negative", 10, min_gap=5)
_, rich_pos  = extract_signal_events(df_z, "spread_5y", "z_5y", 2.0, "positive", 10, min_gap=5)

valid        = df_z.dropna(subset=["spread_5y", "z_5y", "hmm_state"])
ts_dates     = valid.index
ts_spread    = valid["spread_5y"].values * 100
ts_hmm       = valid["hmm_state"].values

idx          = df_z.index
cheap_dates  = idx[cheap_pos]
cheap_spread = df_z["spread_5y"].iloc[cheap_pos].values * 100
cheap_state  = df_z["hmm_state"].iloc[cheap_pos].values

rich_dates   = idx[rich_pos]
rich_spread  = df_z["spread_5y"].iloc[rich_pos].values * 100
rich_state   = df_z["hmm_state"].iloc[rich_pos].values

def get_spans(dates, states, target):
    spans, in_span, start = [], False, None
    for d, s in zip(dates, states):
        if s == target and not in_span:
            start, in_span = d, True
        elif s != target and in_span:
            spans.append((start, d)); in_span = False
    if in_span:
        spans.append((start, dates[-1]))
    return spans

stress_spans = get_spans(ts_dates, ts_hmm, 0.0)
stable_spans = get_spans(ts_dates, ts_hmm, 1.0)

# ── Palette ───────────────────────────────────────────────────────────────────
STRESS_FC   = "#FCEAE8"
STRESS_EC   = "#D4695A"
STABLE_FC   = "#EAF2FB"
STABLE_EC   = "#6799C4"
LINE_CLR    = "#1C2B3A"
CHEAP_CLR   = "#1565C0"
RICH_CLR    = "#B71C1C"
NAVY        = "#0B2545"
BG          = "white"

# ── Figure ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(13, 6.2), facecolor=BG)
fig.subplots_adjust(left=0.09, right=0.97, top=0.86, bottom=0.12)
ax.set_facecolor(BG)

# ── Regime shading ────────────────────────────────────────────────────────────
for t0, t1 in stress_spans:
    ax.axvspan(t0, t1, facecolor=STRESS_FC, edgecolor="none",
               alpha=0.85, zorder=0)
for t0, t1 in stable_spans:
    ax.axvspan(t0, t1, facecolor=STABLE_FC, edgecolor="none",
               alpha=0.70, zorder=0)

# ── Spread line ───────────────────────────────────────────────────────────────
ax.plot(ts_dates, ts_spread, color=LINE_CLR, linewidth=1.1,
        alpha=0.82, zorder=2)
ax.axhline(0, color="#888888", linewidth=0.8, linestyle="--",
           alpha=0.45, zorder=1)

# ── Signal markers ────────────────────────────────────────────────────────────
ax.scatter(cheap_dates, cheap_spread,
           marker="^", s=110, color=CHEAP_CLR,
           edgecolors="white", linewidths=0.8,
           zorder=4, label="z < −2  (cheap spread)")

ax.scatter(rich_dates, rich_spread,
           marker="v", s=110, color=RICH_CLR,
           edgecolors="white", linewidths=0.8,
           zorder=4, label="z > +2  (rich spread)")

# ── Regime strip labels (top of chart) ────────────────────────────────────────
Y_STRIP = 41
STRIP_KW = dict(va="center", fontsize=10.5, fontweight="bold",
                clip_on=False, zorder=5)

label_cfg = [
    (pd.Timestamp("2019-10-01"), "Stress",         STRESS_EC),
    (pd.Timestamp("2020-04-20"), "Stress",         STRESS_EC),
    (pd.Timestamp("2021-04-01"), "Stable",         STABLE_EC),
    (pd.Timestamp("2022-10-01"), "Stress\n(Hiking)", STRESS_EC),
    (pd.Timestamp("2024-01-15"), "Stable",         STABLE_EC),
    (pd.Timestamp("2024-12-01"), "Stress",         STRESS_EC),
    (pd.Timestamp("2025-05-15"), "Stable",         STABLE_EC),
    (pd.Timestamp("2025-11-01"), "Stress",         STRESS_EC),
    (pd.Timestamp("2026-03-20"), "Stable",         STABLE_EC),
]
for xd, txt, clr in label_cfg:
    ax.text(xd, Y_STRIP, txt, ha="center", color=clr, **STRIP_KW)

# ── Callout annotations ───────────────────────────────────────────────────────
CALLOUT_BOX = dict(boxstyle="round,pad=0.45", facecolor="white",
                   edgecolor="#CCCCCC", alpha=0.95, linewidth=1.0)
ARROW_KW = dict(arrowstyle="->", color="#555555", lw=1.4,
                connectionstyle="arc3,rad=-0.25")

# 1. Signal clustering during hiking cycle
ax.annotate(
    "Signals cluster in\nrising-rate regimes",
    xy=(pd.Timestamp("2022-09-01"), -24.5),     # arrow tip → signal cluster
    xytext=(pd.Timestamp("2021-07-01"), -2),    # text box location
    fontsize=11.5, fontweight="bold", color=NAVY,
    ha="center", va="center",
    bbox=CALLOUT_BOX,
    arrowprops={**ARROW_KW, "connectionstyle": "arc3,rad=0.18"},
    zorder=6,
)

# 2. Stronger reversion in stress
ax.annotate(
    "Stronger reversion in stress:\n+5.4 bps  vs  +1.7 bps (stable)",
    xy=(pd.Timestamp("2023-04-01"), -31),       # arrow tip → stress-period signal
    xytext=(pd.Timestamp("2023-11-15"), -13),   # text box location
    fontsize=11, fontweight="bold", color=NAVY,
    ha="center", va="center",
    bbox=CALLOUT_BOX,
    arrowprops={**ARROW_KW, "connectionstyle": "arc3,rad=-0.20"},
    zorder=6,
)

# ── Axis dressing ─────────────────────────────────────────────────────────────
ax.set_ylabel("5Y OIS-Treasury Spread (bps)", fontsize=13,
              color=NAVY, labelpad=10)
ax.set_ylim(-52, 52)
ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
ax.tick_params(labelsize=12, length=3, colors="#444444")

ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
ax.tick_params(axis="x", which="minor", length=2, color="#DDDDDD")
ax.set_xlim(ts_dates[0], ts_dates[-1])

for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
for sp in ["left", "bottom"]:
    ax.spines[sp].set_color("#CCCCCC")

ax.grid(axis="y", color="#F0F0F0", linewidth=0.7, zorder=0)

# ── Legend ────────────────────────────────────────────────────────────────────
signal_handles = [
    ax.scatter([], [], marker="^", s=100, color=CHEAP_CLR,
               edgecolors="white", linewidths=0.7,
               label="z < −2  (cheap spread)"),
    ax.scatter([], [], marker="v", s=100, color=RICH_CLR,
               edgecolors="white", linewidths=0.7,
               label="z > +2  (rich spread)"),
    mpatches.Patch(facecolor=STRESS_FC, edgecolor=STRESS_EC,
                   linewidth=1.2, label="Stress / Rising Rates"),
    mpatches.Patch(facecolor=STABLE_FC, edgecolor=STABLE_EC,
                   linewidth=1.2, label="Stable / Falling Rates"),
]
ax.legend(
    handles=signal_handles,
    loc="lower left", fontsize=11,
    frameon=True, framealpha=0.95, edgecolor="#CCCCCC",
    handlelength=1.4, handleheight=1.0, labelspacing=0.45,
    ncol=2, columnspacing=1.6,
)

# ── Title ─────────────────────────────────────────────────────────────────────
ax.set_title(
    "OIS-Treasury Spread: HMM Regime Shading and Mean-Reversion Signals  (5Y)",
    fontsize=14, fontweight="bold", color=NAVY, pad=10, loc="left",
)

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, bbox_inches="tight", pad_inches=0.2, facecolor=BG)
plt.close(fig)
print(f"Saved → {OUT}")
