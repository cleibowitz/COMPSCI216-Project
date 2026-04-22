"""
Presentation bar chart — mean reversion by rate regime, 5Y / 10-day horizon.
Panel A: z < -2  (cheap spreads)
Panel B: z > +2  (rich spreads)
Values sourced from outputs/tables/rq3_partA_rate_regime.csv
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "outputs" / "figures" / "rq3_regime_bars.png"

# ── Data (from rq3_partA_rate_regime.csv) ─────────────────────────────────────
REGIMES  = ["Rising\nRates", "Falling /\nStable"]

CHEAP_VALS = [5.40,   1.67]    # z < -2  | rising, falling/stable
RICH_VALS  = [-10.84, -0.89]   # z > +2  | rising, falling/stable

CHEAP_NS   = [13, 35]
RICH_NS    = [11, 26]

# p-values for regime split (from rq3_partA_rate_twosample.csv)
P_CHEAP = 0.001    # significant
P_RICH  = 0.131    # not significant

# ── Style ──────────────────────────────────────────────────────────────────────
RISING_CLR  = "#1A3A5C"    # dark navy
FALLING_CLR = "#A8B8C8"    # muted steel blue-grey
NAVY        = "#0B2545"
BG          = "white"

BAR_WIDTH   = 0.46
X           = np.array([0, 1])
FONTSIZE_LABEL  = 15
FONTSIZE_TICK   = 13
FONTSIZE_TITLE  = 14
FONTSIZE_VAL    = 13.5

# ── Figure ─────────────────────────────────────────────────────────────────────
fig, (ax_a, ax_b) = plt.subplots(2, 1, figsize=(9, 11), facecolor=BG)
fig.subplots_adjust(left=0.16, right=0.93, top=0.83, bottom=0.08, hspace=0.55)


def style_ax(ax):
    ax.set_facecolor(BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(axis="both", labelsize=FONTSIZE_TICK, colors="#333333", length=0)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())


def draw_panel(ax, vals, ns, p_val, y_lo, y_hi, y_step,
               title_line1, title_line2, title_color, sig_tag):
    colors = [RISING_CLR, FALLING_CLR]

    bars = ax.bar(X, vals, width=BAR_WIDTH, color=colors,
                  zorder=3, linewidth=0)

    # Zero line
    ax.axhline(0, color="#555555", linewidth=1.2, linestyle="--",
               alpha=0.7, zorder=2)

    # Value labels
    for xi, (val, n, bar) in enumerate(zip(vals, ns, bars)):
        positive = val >= 0
        sign = "+" if positive else "−"
        label = f"{sign}{abs(val):.2f} bps"

        # Offset: above bar if positive, below if negative
        offset = (y_hi - y_lo) * 0.04
        y_txt  = val + offset if positive else val - offset
        va     = "bottom" if positive else "top"

        ax.text(xi, y_txt, label,
                ha="center", va=va,
                fontsize=FONTSIZE_VAL, fontweight="bold",
                color=colors[xi], zorder=4)

    # x-axis
    ax.set_xticks(X)
    ax.set_xticklabels(REGIMES, fontsize=FONTSIZE_LABEL, color="#333333",
                       fontweight="bold", linespacing=1.4)
    ax.set_xlim(-0.55, 1.55)

    # y-axis
    ax.set_ylim(y_lo, y_hi)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(y_step))
    ax.set_ylabel("Mean 10-Day Forward Change (bps)",
                  fontsize=12, color=NAVY, labelpad=10)

    # Light horizontal grid on y only
    ax.yaxis.grid(True, color="#EBEBEB", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    style_ax(ax)

    # Significance tag below title
    ax.set_title(
        f"{title_line1}\n{title_line2}",
        fontsize=FONTSIZE_TITLE, fontweight="bold",
        color=title_color, pad=10, linespacing=1.5,
    )

    # Significance badge — top-right corner, always clear of bars
    badge_clr = "#1A6B3C" if p_val < 0.05 else "#888888"
    ax.text(0.97, 0.97, sig_tag,
            transform=ax.transAxes,
            ha="right", va="top",
            fontsize=11, color=badge_clr,
            style="italic")


# ── Panel A — cheap spreads (z < -2) ──────────────────────────────────────────
draw_panel(
    ax_a,
    vals     = CHEAP_VALS,
    ns       = CHEAP_NS,
    p_val    = P_CHEAP,
    y_lo     = -0.5,
    y_hi     = 8.0,
    y_step   = 2,
    title_line1 = "Cheap Spreads (z < −2)",
    title_line2 = "Stronger Reversion in Rising Rate Regimes",
    title_color = "#1A6B3C",
    sig_tag  = f"p = {P_CHEAP:.3f}  ✓ significant",
)

# ── Panel B — rich spreads (z > +2) ───────────────────────────────────────────
draw_panel(
    ax_b,
    vals     = RICH_VALS,
    ns       = RICH_NS,
    p_val    = P_RICH,
    y_lo     = -14.0,
    y_hi     = 2.5,
    y_step   = 3,
    title_line1 = "Rich Spreads (z > +2)",
    title_line2 = "Directional Pattern Holds; Effect Less Significant",
    title_color = "#9B2318",
    sig_tag  = f"p = {P_RICH:.3f}  — not significant",
)

# ── Legend ─────────────────────────────────────────────────────────────────────
from matplotlib.patches import Patch
legend_items = [
    Patch(facecolor=RISING_CLR,  edgecolor="none", label="Rising Rates"),
    Patch(facecolor=FALLING_CLR, edgecolor="none", label="Falling / Stable"),
]
# ── Super-title ────────────────────────────────────────────────────────────────
fig.text(0.545, 0.998,
         "RQ3 — Rate Regime Drives Mean Reversion Magnitude",
         ha="center", va="top",
         fontsize=16, fontweight="bold", color=NAVY)

fig.text(0.545, 0.972,
         "5Y OIS-Treasury Spread  ·  10-Day Forward Horizon",
         ha="center", va="top",
         fontsize=12, color="#666666")

fig.legend(handles=legend_items, loc="upper center",
           bbox_to_anchor=(0.545, 0.942),
           ncol=2, fontsize=13, frameon=False,
           handlelength=1.4, handleheight=1.0, columnspacing=2.0)

# ── Save ──────────────────────────────────────────────────────────────────────
fig.savefig(OUT, dpi=200, bbox_inches="tight", pad_inches=0.25, facecolor=BG)
plt.close(fig)
print(f"Saved → {OUT}")
print(f"  Panel A: rising={CHEAP_VALS[0]:+.2f}, falling={CHEAP_VALS[1]:+.2f} bps")
print(f"  Panel B: rising={RICH_VALS[0]:+.2f},  falling={RICH_VALS[1]:+.2f} bps")
