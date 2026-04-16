"""
Exploratory Data Analysis for Treasury-SOFR relative value spreads.

Produces univariate statistics, histograms, time series plots,
bivariate scatter plots, and a correlation matrix heatmap.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path

from src.utils.config import FINAL_DATASET_PATH

# Spread definitions: column name -> human-readable label
SPREAD_COLS = {
    "spread_2y": "Spread 2Y (OIS 2Y - DGS2)",
    "spread_5y": "Spread 5Y (OIS 5Y - DGS5)",
    "spread_10y": "Spread 10Y (OIS 10Y - DGS10)",
}

# Which Treasury yield to pair with each spread for bivariate analysis
SPREAD_YIELD_PAIRS = {
    "spread_2y": "DGS2",
    "spread_5y": "DGS5",
    "spread_10y": "DGS10",
}

FIGURES_DIR = Path(__file__).resolve().parents[2] / "outputs" / "figures"


def load_dataset() -> pd.DataFrame:
    """Load the merged dataset from parquet, ensuring a sorted DatetimeIndex."""
    df = pd.read_parquet(FINAL_DATASET_PATH)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


def univariate_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute summary statistics for each spread."""
    stats = df[list(SPREAD_COLS.keys())].agg(["mean", "std", "min", "max", "skew"])
    print("\n--- Univariate Spread Statistics ---")
    print(stats.to_string())
    return stats


def plot_histograms(df: pd.DataFrame) -> None:
    """Histogram for each spread — shows the distribution of the spread level."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), sharey=False)
    for ax, (col, label) in zip(axes, SPREAD_COLS.items()):
        data = df[col].dropna()
        ax.hist(data, bins=50, edgecolor="black", alpha=0.7)
        ax.axvline(data.mean(), color="red", linestyle="--", label=f"mean={data.mean():.3f}")
        ax.set_title(label)
        ax.set_xlabel("Spread (pp)")
        ax.set_ylabel("Frequency")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "spread_histograms.png", dpi=150)
    plt.close(fig)
    print("  Saved spread_histograms.png")


def plot_time_series(df: pd.DataFrame) -> None:
    """Time series of each spread — reveals regime changes and trends."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    for ax, (col, label) in zip(axes, SPREAD_COLS.items()):
        ax.plot(df.index, df[col], linewidth=0.8)
        ax.axhline(0, color="gray", linestyle="--", linewidth=0.5)
        ax.set_ylabel("Spread (pp)")
        ax.set_title(label)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "spread_time_series.png", dpi=150)
    plt.close(fig)
    print("  Saved spread_time_series.png")


def plot_bivariate(df: pd.DataFrame) -> None:
    """
    Scatter: spread vs. corresponding Treasury yield.
    Helps visualize whether spreads widen/tighten at certain yield levels.
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, (spread_col, yield_col) in zip(axes, SPREAD_YIELD_PAIRS.items()):
        clean = df[[spread_col, yield_col]].dropna()
        ax.scatter(clean[yield_col], clean[spread_col], s=3, alpha=0.4)
        ax.set_xlabel(f"{yield_col} Yield (%)")
        ax.set_ylabel(f"{spread_col} (pp)")
        ax.set_title(f"{spread_col} vs {yield_col}")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "spread_vs_yield_scatter.png", dpi=150)
    plt.close(fig)
    print("  Saved spread_vs_yield_scatter.png")


def plot_correlation_matrix(df: pd.DataFrame) -> None:
    """
    Correlation heatmap across yields, SOFR rates, and spreads.
    Useful for spotting redundancy and co-movement.
    """
    cols = ["DGS2", "DGS5", "DGS10",
            "ois_2y", "ois_5y", "ois_10y",
            "spread_2y", "spread_5y", "spread_10y"]
    # Only include columns that exist in the data
    cols = [c for c in cols if c in df.columns]
    corr = df[cols].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                square=True, linewidths=0.5, ax=ax)
    ax.set_title("Correlation Matrix")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "correlation_matrix.png", dpi=150)
    plt.close(fig)
    print("  Saved correlation_matrix.png")


def plot_spread_move_overview(df: pd.DataFrame) -> None:
    """
    Four-panel overview: the three OIS-Treasury spreads plus the MOVE index.

    Layout (4 rows, shared x-axis):
      Row 1: spread_2y  (OIS 2Y - DGS2)
      Row 2: spread_5y  (OIS 5Y - DGS5)
      Row 3: spread_10y (OIS 10Y - DGS10)
      Row 4: MOVE index (bp)

    Spread panels include a dashed zero line.
    MOVE panel shades the high-vol regime (above rolling 60-day median).
    """
    if "MOVE" not in df.columns:
        print("  WARNING: MOVE column not found, skipping overview plot.")
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    fig.subplots_adjust(hspace=0.12)

    spread_meta = [
        ("spread_2y",  "OIS 2Y − DGS2 (pp)",  "steelblue"),
        ("spread_5y",  "OIS 5Y − DGS5 (pp)",  "darkorange"),
        ("spread_10y", "OIS 10Y − DGS10 (pp)", "seagreen"),
    ]

    for ax, (col, ylabel, color) in zip(axes[:3], spread_meta):
        data = df[col].dropna()
        ax.plot(data.index, data, linewidth=0.8, color=color)
        ax.axhline(0, color="black", linestyle="--", linewidth=0.5, alpha=0.6)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.yaxis.set_label_coords(-0.06, 0.5)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="x", labelbottom=False)

    # MOVE panel
    ax_move = axes[3]
    move = df["MOVE"].dropna()
    ax_move.plot(move.index, move, linewidth=0.8, color="firebrick", label="MOVE")

    # Rolling 60-day median as a reference line
    move_median = move.rolling(60, min_periods=60).median()
    ax_move.plot(move_median.index, move_median, linewidth=1.0,
                 color="black", linestyle="--", alpha=0.7, label="60d median")

    # Shade high-vol periods (MOVE above its 60-day median)
    above = move > move_median
    ax_move.fill_between(move.index, move.min() * 0.95, move,
                         where=above, alpha=0.12, color="firebrick",
                         label="High-vol (MOVE > 60d median)")

    ax_move.set_ylabel("MOVE index (bp)", fontsize=9)
    ax_move.yaxis.set_label_coords(-0.06, 0.5)
    ax_move.xaxis.set_major_locator(mdates.YearLocator())
    ax_move.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_move.legend(fontsize=8, loc="upper right")

    fig.suptitle("OIS–Treasury Spreads and MOVE Volatility Index", fontsize=12, y=1.01)

    out_path = FIGURES_DIR / "spread_move_overview.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved spread_move_overview.png")


def run_eda(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full EDA suite and return the dataset (unchanged)."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("EDA: Univariate Statistics")
    print("=" * 60)
    univariate_stats(df)

    print("\n" + "=" * 60)
    print("EDA: Generating Plots")
    print("=" * 60)
    plot_histograms(df)
    plot_time_series(df)
    plot_bivariate(df)
    plot_correlation_matrix(df)
    plot_spread_move_overview(df)

    return df


if __name__ == "__main__":
    df = load_dataset()
    run_eda(df)
