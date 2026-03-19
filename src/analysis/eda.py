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
    "spread_2y": "Spread 2Y (SOFR30D - DGS2)",
    "spread_5y": "Spread 5Y (SOFR90D - DGS5)",
    "spread_10y": "Spread 10Y (SOFR180D - DGS10)",
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
            "SOFR", "SOFR30DAYAVG", "SOFR90DAYAVG", "SOFR180DAYAVG",
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

    return df


if __name__ == "__main__":
    df = load_dataset()
    run_eda(df)
