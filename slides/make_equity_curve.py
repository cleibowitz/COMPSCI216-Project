"""
Equity curve: cumulative net P&L (bps) for rules-based vs HMM-filtered strategy.
Source: outputs/backtest_trades.csv
P&L booked at trade exit date (step function).
"""

from pathlib import Path
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs" / "figures" / "equity_curve.png"

# ── Load trades ────────────────────────────────────────────────────────────────
trades = pd.read_csv(PROJECT_ROOT / "outputs" / "backtest_trades.csv",
                     parse_dates=["entry_date", "exit_date"])

rules = trades[trades["strategy"] == "rules"].copy()
hmm   = trades[trades["strategy"] == "hmm_filtered"].copy()

# ── Build daily cumulative P&L series ─────────────────────────────────────────
OOS_START = pd.Timestamp("2024-01-01")
OOS_END   = trades["exit_date"].max() + pd.Timedelta(days=5)
dates     = pd.date_range(OOS_START, OOS_END, freq="B")   # business days

def cum_pnl_series(df, date_index):
    daily = pd.Series(0.0, index=date_index)
    for _, row in df.iterrows():
        exit_d = row["exit_date"]
        if exit_d in daily.index:
            daily[exit_d] += row["net_bps"]
        else:
            # snap to nearest business day
            nearest = daily.index[daily.index.searchsorted(exit_d)]
            daily[nearest] += row["net_bps"]
    return daily.cumsum()

cum_rules = cum_pnl_series(rules, dates)
cum_hmm   = cum_pnl_series(hmm,   dates)

# Filtered-out trades (in rules but not HMM) — mark on the rules curve
filtered_out = rules[rules["hmm_state_at_entry"] == 0].copy()

# ── Palette ────────────────────────────────────────────────────────────────────
GRAY      = "#A8B8C8"
BLUE      = "#1A3A5C"
NAVY      = "#0B2545"
RED_FADED = "#C0392B"
BG        = "white"

# ── Figure ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG)
fig.subplots_adjust(left=0.07, right=0.93, top=0.78, bottom=0.12)
ax.set_facecolor(BG)

# ── Zero line ──────────────────────────────────────────────────────────────────
ax.axhline(0, color="#BBBBBB", linewidth=0.9, linestyle="--", zorder=1)

# ── Fill under each curve ─────────────────────────────────────────────────────
ax.fill_between(cum_rules.index, 0, cum_rules.values,
                where=(cum_rules.values >= 0),
                color=GRAY, alpha=0.12, zorder=1)
ax.fill_between(cum_rules.index, 0, cum_rules.values,
                where=(cum_rules.values < 0),
                color=RED_FADED, alpha=0.08, zorder=1)

ax.fill_between(cum_hmm.index, 0, cum_hmm.values,
                color=BLUE, alpha=0.08, zorder=1)

# ── Equity lines ──────────────────────────────────────────────────────────────
ax.step(cum_rules.index, cum_rules.values, where="post",
        color=GRAY, linewidth=2.0, zorder=3, label="No Regime Filter  (n=20)")
ax.step(cum_hmm.index, cum_hmm.values, where="post",
        color=BLUE, linewidth=2.2, zorder=4, label="HMM-Filtered  (n=11)")

# ── Markers: HMM trade exits ──────────────────────────────────────────────────
for _, row in hmm.iterrows():
    exit_d = row["exit_date"]
    if exit_d not in cum_hmm.index:
        exit_d = cum_hmm.index[cum_hmm.index.searchsorted(exit_d)]
    ax.scatter(exit_d, cum_hmm[exit_d],
               color=BLUE, s=55, zorder=5,
               edgecolors="white", linewidths=0.8)

# ── Markers: filtered-out trades (shown on rules curve as ✕) ─────────────────
for _, row in filtered_out.iterrows():
    exit_d = row["exit_date"]
    if exit_d not in cum_rules.index:
        exit_d = cum_rules.index[cum_rules.index.searchsorted(exit_d)]
    ax.scatter(exit_d, cum_rules[exit_d],
               marker="X", color=RED_FADED, s=70, zorder=5,
               edgecolors="white", linewidths=0.7,
               label="_nolegend_")

# ── End-point annotations ─────────────────────────────────────────────────────
final_rules = cum_rules.iloc[-1]
final_hmm   = cum_hmm.iloc[-1]
end_date    = cum_rules.index[-1]

# Offset vertically if values are close to avoid overlap
y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
gap = abs(final_hmm - final_rules)
nudge = 1.2 if gap < y_range * 0.08 else 0

# rules goes below, hmm goes above when they're close
rules_offset = -nudge if final_hmm > final_rules else nudge
hmm_offset   =  nudge if final_hmm > final_rules else -nudge

ax.annotate(f"+{final_rules:.1f} bps",
            xy=(end_date, final_rules),
            xytext=(10, rules_offset * 6), textcoords="offset points",
            va="center", ha="left",
            fontsize=12, fontweight="bold", color=GRAY,
            clip_on=False)

ax.annotate(f"+{final_hmm:.1f} bps",
            xy=(end_date, final_hmm),
            xytext=(10, hmm_offset * 6), textcoords="offset points",
            va="center", ha="left",
            fontsize=12, fontweight="bold", color=BLUE,
            clip_on=False)

# ── Filtered-out marker legend entry ─────────────────────────────────────────
ax.scatter([], [], marker="X", color=RED_FADED, s=70,
           edgecolors="white", linewidths=0.7,
           label="Trades blocked by HMM filter (stress state)")

# ── Axes dressing ──────────────────────────────────────────────────────────────
ax.set_ylabel("Cumulative Net P&L (bps)", fontsize=13, color=NAVY, labelpad=10)
ax.set_xlim(dates[0], end_date + pd.Timedelta(days=30))

y_pad = 4
ax.set_ylim(min(cum_rules.min(), cum_hmm.min()) - y_pad,
            max(cum_rules.max(), cum_hmm.max()) + y_pad)
ax.yaxis.set_major_locator(mticker.MultipleLocator(5))
ax.tick_params(labelsize=11, colors="#444444", length=0)

ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax.xaxis.set_minor_locator(mdates.MonthLocator())
ax.tick_params(axis="x", which="minor", length=2, color="#DDDDDD")

for sp in ["top", "right"]:
    ax.spines[sp].set_visible(False)
for sp in ["left", "bottom"]:
    ax.spines[sp].set_color("#CCCCCC")
ax.yaxis.grid(True, color="#F2F2F2", linewidth=0.7, zorder=0)

# ── Legend ────────────────────────────────────────────────────────────────────
ax.legend(loc="upper left", fontsize=11, frameon=True,
          framealpha=0.95, edgecolor="#CCCCCC",
          handlelength=1.6, labelspacing=0.5)

# ── Title + subtitle ──────────────────────────────────────────────────────────
fig.text(0.07, 0.97,
         "Equity Curve: Regime Filtering Reduces Drawdown and Improves Consistency",
         ha="left", va="top",
         fontsize=14, fontweight="bold", color=NAVY)

fig.text(0.07, 0.925,
         "OOS Backtest: Jan 2024 – Mar 2026  ·  5Y OIS-Treasury  ·  Net of 1 bp Round-Trip Cost  ·  P&L booked at trade exit",
         ha="left", va="top", fontsize=10.5, color="#777777")

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, bbox_inches="tight", pad_inches=0.2, facecolor=BG)
plt.close(fig)
print(f"Saved → {OUT}")
print(f"  Rules final: +{final_rules:.1f} bps over {len(rules)} trades")
print(f"  HMM final:   +{final_hmm:.1f} bps over {len(hmm)} trades")
