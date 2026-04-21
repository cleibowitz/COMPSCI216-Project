"""
Institutional-quality regime + signal visualization.
Panel A: 5Y OIS-Treasury spread with non-overlapping signal events.
Panel B: 60-day rolling z-score with HMM regime shading.
All signals are the exact non-overlapping events used in RQ1 / backtest.
"""

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.analysis.stats_utils import compute_z_scores, extract_signal_events

PROJECT_ROOT = Path(__file__).resolve().parent
OUT = PROJECT_ROOT / "outputs" / "figures" / "hmm_regime_signals.png"

# ── Load & prepare data ───────────────────────────────────────────────────────
df   = pd.read_parquet(PROJECT_ROOT / "outputs" / "ml" / "dataset_with_hmm.parquet")
df_z = compute_z_scores(df, window=60)

# Exact non-overlapping events (same spec as rq1.py)
_, cheap_pos = extract_signal_events(df_z, "spread_5y", "z_5y", 2.0, "negative", 10, min_gap=5)
_, rich_pos  = extract_signal_events(df_z, "spread_5y", "z_5y", 2.0, "positive", 10, min_gap=5)

valid = df_z.dropna(subset=["spread_5y", "z_5y", "hmm_state"])
ts_dates  = valid.index
ts_spread = valid["spread_5y"].values * 100     # pp → bps
ts_z      = valid["z_5y"].values
ts_hmm    = valid["hmm_state"].values

idx       = df_z.index
cheap_dates  = idx[cheap_pos]
cheap_spread = df_z["spread_5y"].iloc[cheap_pos].values * 100
cheap_z      = df_z["z_5y"].iloc[cheap_pos].values
cheap_state  = df_z["hmm_state"].iloc[cheap_pos].values

rich_dates   = idx[rich_pos]
rich_spread  = df_z["spread_5y"].iloc[rich_pos].values * 100
rich_z       = df_z["z_5y"].iloc[rich_pos].values
rich_state   = df_z["hmm_state"].iloc[rich_pos].values

# ── Regime span boundaries ────────────────────────────────────────────────────
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

stress_spans = get_spans(ts_dates, ts_hmm, 0.0)   # state 0 — stress
stable_spans = get_spans(ts_dates, ts_hmm, 1.0)   # state 1 — stable

# Labels for major regime blocks  (mid-point, text)
REGIME_LABELS = [
    (pd.Timestamp("2020-05-01"), 0, "COVID\nStress"),
    (pd.Timestamp("2022-12-01"), 0, "Fed Hiking\nCycle"),
    (pd.Timestamp("2021-01-01"), 1, "Recovery &\nLow Rates"),
    (pd.Timestamp("2024-01-01"), 1, "Post-Hike\nStabilisation"),
]

# ── Colour palette ────────────────────────────────────────────────────────────
STRESS_BG   = "#FEF0ED"    # very light rose  — state 0 background
STABLE_BG   = "#EEF4FB"    # very light sky   — state 1 background
STRESS_EDGE = "#E07060"    # muted coral      — state 0 border
STABLE_EDGE = "#7AADD4"    # muted steel-blue — state 1 border

LINE_CLR    = "#1C2B3A"    # near-black navy  — spread / z-score line
CHEAP_CLR   = "#1565C0"    # deep blue        — z < -2
RICH_CLR    = "#B71C1C"    # deep red         — z > +2
THRESH_CLR  = "#999999"    # mid-grey         — ±2σ dashed lines
NAVY        = "#0B2545"
BG          = "white"

# ── Figure layout ─────────────────────────────────────────────────────────────
fig, (ax_a, ax_b) = plt.subplots(
    2, 1, figsize=(16, 9), sharex=True, facecolor=BG,
    gridspec_kw={"height_ratios": [1, 1.15]},
)
fig.subplots_adjust(left=0.07, right=0.97, top=0.91, bottom=0.07, hspace=0.08)


# ── Helper: shade regime spans ────────────────────────────────────────────────
def shade_regimes(ax, alpha_stress=0.45, alpha_stable=0.30):
    for t0, t1 in stress_spans:
        ax.axvspan(t0, t1, facecolor=STRESS_BG, edgecolor="none",
                   alpha=alpha_stress, zorder=0)
    for t0, t1 in stable_spans:
        ax.axvspan(t0, t1, facecolor=STABLE_BG, edgecolor="none",
                   alpha=alpha_stable, zorder=0)


# ══════════════════════════════════════════════════════════════════════════════
# PANEL A — Spread time series + signal events
# ══════════════════════════════════════════════════════════════════════════════
shade_regimes(ax_a, alpha_stress=0.55, alpha_stable=0.30)

ax_a.plot(ts_dates, ts_spread, color=LINE_CLR, linewidth=0.9,
          alpha=0.85, zorder=2, label="5Y Spread")
ax_a.axhline(0, color="#888888", linewidth=0.8, linestyle="--",
             alpha=0.5, zorder=1)

# Signal markers — cheap (▲) and rich (▼)
ax_a.scatter(cheap_dates, cheap_spread,
             marker="^", s=72, color=CHEAP_CLR,
             edgecolors="white", linewidths=0.6,
             zorder=4, label="z < −2  (cheap → upward reversion)")

ax_a.scatter(rich_dates, rich_spread,
             marker="v", s=72, color=RICH_CLR,
             edgecolors="white", linewidths=0.6,
             zorder=4, label="z > +2  (rich → downward reversion)")

# Axis dressing
ax_a.set_ylabel("5Y OIS-Treasury Spread (bps)", fontsize=12,
                color=NAVY, labelpad=8)
ax_a.yaxis.set_major_locator(mticker.MultipleLocator(20))
ax_a.tick_params(labelsize=11, length=3, colors="#444444")
ax_a.set_facecolor(BG)
for sp in ["top", "right"]:
    ax_a.spines[sp].set_visible(False)
for sp in ["left", "bottom"]:
    ax_a.spines[sp].set_color("#CCCCCC")
ax_a.grid(axis="y", color="#EBEBEB", linewidth=0.6, zorder=0)

# Legend — top-left
leg_a = ax_a.legend(
    loc="upper left", fontsize=11, frameon=True,
    framealpha=0.92, edgecolor="#CCCCCC",
    handlelength=1.2, handleheight=1.0, labelspacing=0.4,
)

ax_a.set_title("Panel A — 5Y OIS-Treasury Spread with Mean-Reversion Signal Events",
               fontsize=13, fontweight="bold", color=NAVY, pad=8, loc="left")


# ══════════════════════════════════════════════════════════════════════════════
# PANEL B — Z-score with HMM regime shading & labels
# ══════════════════════════════════════════════════════════════════════════════
shade_regimes(ax_b, alpha_stress=0.60, alpha_stable=0.35)

ax_b.plot(ts_dates, ts_z, color=LINE_CLR, linewidth=0.85,
          alpha=0.80, zorder=2)

# ±2σ threshold bands
ax_b.axhline(+2, color=RICH_CLR,  linewidth=1.0, linestyle="--", alpha=0.60, zorder=1)
ax_b.axhline(-2, color=CHEAP_CLR, linewidth=1.0, linestyle="--", alpha=0.60, zorder=1)
ax_b.axhline( 0, color="#888888", linewidth=0.7, linestyle="--", alpha=0.45, zorder=1)

ax_b.fill_between(ts_dates, 2,  ts_z, where=(ts_z >  2),
                  color=RICH_CLR,  alpha=0.10, zorder=1)
ax_b.fill_between(ts_dates, -2, ts_z, where=(ts_z < -2),
                  color=CHEAP_CLR, alpha=0.10, zorder=1)

# Signal dots on z-score line
ax_b.scatter(cheap_dates, cheap_z, marker="^", s=65,
             color=CHEAP_CLR, edgecolors="white", linewidths=0.6, zorder=4)
ax_b.scatter(rich_dates,  rich_z,  marker="v", s=65,
             color=RICH_CLR,  edgecolors="white", linewidths=0.6, zorder=4)

# ±2σ text labels (right edge)
x_label = ts_dates[-1]
ax_b.text(x_label, 2.10, " +2σ", va="bottom", ha="left",
          fontsize=10, color=RICH_CLR, fontweight="bold")
ax_b.text(x_label, -2.10, " −2σ", va="top", ha="left",
          fontsize=10, color=CHEAP_CLR, fontweight="bold")

# Regime labels inside the major blocks
LABEL_PROPS = dict(ha="center", va="center", fontsize=10,
                   fontweight="bold", alpha=0.70, zorder=3)
_stress_label_y = -4.8
_stable_label_y = -4.8

regime_label_data = [
    (pd.Timestamp("2020-05-01"),  _stress_label_y, "Stress", STRESS_EDGE),
    (pd.Timestamp("2022-12-01"),  _stress_label_y, "Stress\n(Hiking)", STRESS_EDGE),
    (pd.Timestamp("2025-01-01"),  _stress_label_y, "Stress", STRESS_EDGE),
    (pd.Timestamp("2021-01-01"),  _stable_label_y, "Stable", STABLE_EDGE),
    (pd.Timestamp("2024-03-01"),  _stable_label_y, "Stable", STABLE_EDGE),
]
for xd, yd, txt, clr in regime_label_data:
    ax_b.text(xd, yd, txt, color=clr, **LABEL_PROPS)

# Axis dressing
ax_b.set_ylabel("60-Day Rolling Z-Score", fontsize=12,
                color=NAVY, labelpad=8)
ax_b.set_ylim(-6, 8)
ax_b.yaxis.set_major_locator(mticker.MultipleLocator(2))
ax_b.tick_params(labelsize=11, length=3, colors="#444444")
ax_b.set_facecolor(BG)
for sp in ["top", "right"]:
    ax_b.spines[sp].set_visible(False)
for sp in ["left", "bottom"]:
    ax_b.spines[sp].set_color("#CCCCCC")
ax_b.grid(axis="y", color="#EBEBEB", linewidth=0.6, zorder=0)

ax_b.set_title("Panel B — HMM Regime States and Z-Score Signal Thresholds",
               fontsize=13, fontweight="bold", color=NAVY, pad=8, loc="left")

# X-axis formatting
ax_b.xaxis.set_major_locator(mdates.YearLocator())
ax_b.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax_b.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
ax_b.tick_params(axis="x", which="minor", length=2, color="#CCCCCC")
ax_b.set_xlim(ts_dates[0], ts_dates[-1])

# ── Shared regime legend (bottom of figure) ───────────────────────────────────
regime_handles = [
    mpatches.Patch(facecolor=STRESS_BG, edgecolor=STRESS_EDGE,
                   linewidth=1.2, label="State 0 — Stress / Rising Rates"),
    mpatches.Patch(facecolor=STABLE_BG, edgecolor=STABLE_EDGE,
                   linewidth=1.2, label="State 1 — Stable / Falling Rates"),
]
fig.legend(
    handles=regime_handles,
    loc="lower center",
    bbox_to_anchor=(0.52, 0.003),
    ncol=2, fontsize=11.5, frameon=False,
    handlelength=1.6, handleheight=1.0, columnspacing=2.5,
)

# ── Super-title ───────────────────────────────────────────────────────────────
fig.text(0.52, 0.975,
         "HMM Regime Detection and OIS-Treasury Spread Signal Clustering  (5Y Maturity)",
         ha="center", va="top",
         fontsize=15, fontweight="bold", color=NAVY)

fig.text(0.52, 0.952,
         "Shading = 2-state HMM (Viterbi decoding)  ·  Markers = non-overlapping |z| > 2 events"
         "  ·  Window = 60d  ·  Min gap = 5d",
         ha="center", va="top", fontsize=10.5, color="#666666")

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, bbox_inches="tight", pad_inches=0.2, facecolor=BG)
plt.close(fig)
print(f"Saved → {OUT}")
print(f"  Cheap signals: {len(cheap_dates)}  |  Rich signals: {len(rich_dates)}")
print(f"  Stress spans: {len(stress_spans)}  |  Stable spans: {len(stable_spans)}")
