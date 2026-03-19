"""
Rolling z-score signal construction for Treasury-SOFR spreads.

Z-scores normalize spreads relative to their recent history, making
them comparable across maturities and time periods.

    z = (spread - rolling_mean) / rolling_std

Interpretation:
  z > +2  →  spread is unusually wide  (SOFR rich vs. Treasuries)
  z < -2  →  spread is unusually tight (SOFR cheap vs. Treasuries)
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

from src.utils.config import PROCESSED_DATA_DIR

FIGURES_DIR = Path(__file__).resolve().parents[2] / "outputs" / "figures"

SPREAD_COLS = ["spread_2y", "spread_5y", "spread_10y"]
WINDOW = 60  # rolling window in business days (~3 months)


def compute_z_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling mean, rolling std, and z-score columns for each spread.

    New columns per spread (e.g. for spread_2y):
      - spread_2y_roll_mean
      - spread_2y_roll_std
      - z_2y
    """
    for col in SPREAD_COLS:
        tenor = col.replace("spread_", "")  # "2y", "5y", "10y"

        roll_mean = df[col].rolling(window=WINDOW, min_periods=WINDOW).mean()
        roll_std = df[col].rolling(window=WINDOW, min_periods=WINDOW).std()

        df[f"{col}_roll_mean"] = roll_mean
        df[f"{col}_roll_std"] = roll_std

        # Z-score: how many std devs the current spread is from its rolling mean
        df[f"z_{tenor}"] = (df[col] - roll_mean) / roll_std

    return df


def print_signal_stats(df: pd.DataFrame) -> None:
    """Print summary statistics for z-score columns."""
    z_cols = ["z_2y", "z_5y", "z_10y"]
    stats = df[z_cols].describe()
    print("\n--- Z-Score Summary Statistics ---")
    print(stats.to_string())

    # Count how often signals breach +/-2 thresholds
    print("\n--- Threshold Breach Counts ---")
    for col in z_cols:
        data = df[col].dropna()
        n_above = (data > 2).sum()
        n_below = (data < -2).sum()
        pct_above = n_above / len(data) * 100
        pct_below = n_below / len(data) * 100
        print(f"  {col}: >{'+2':>3} = {n_above:>4} ({pct_above:.1f}%)  |  "
              f"<{'-2':>3} = {n_below:>4} ({pct_below:.1f}%)")


def plot_z_scores(df: pd.DataFrame) -> None:
    """
    Time series of z-scores with +/-2 threshold bands highlighted.
    Shaded regions mark periods where the signal is in extreme territory.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    z_cols = {
        "z_2y": "Z-Score: 2Y Spread",
        "z_5y": "Z-Score: 5Y Spread",
        "z_10y": "Z-Score: 10Y Spread",
    }

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    for ax, (col, title) in zip(axes, z_cols.items()):
        data = df[col].dropna()
        ax.plot(data.index, data, linewidth=0.8, color="steelblue")

        # Threshold lines
        ax.axhline(+2, color="red", linestyle="--", linewidth=0.7, label="+2 (rich)")
        ax.axhline(-2, color="green", linestyle="--", linewidth=0.7, label="-2 (cheap)")
        ax.axhline(0, color="gray", linestyle="-", linewidth=0.4)

        # Shade extreme regions
        ax.fill_between(data.index, 2, data.clip(lower=2),
                        alpha=0.2, color="red")
        ax.fill_between(data.index, -2, data.clip(upper=-2),
                        alpha=0.2, color="green")

        ax.set_ylabel("Z-Score")
        ax.set_title(title)
        ax.legend(loc="upper right", fontsize=8)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "z_score_time_series.png", dpi=150)
    plt.close(fig)
    print("  Saved z_score_time_series.png")


def save_signals_dataset(df: pd.DataFrame) -> Path:
    """Save the full dataset (with signals) to parquet."""
    out_path = PROCESSED_DATA_DIR / "final_dataset_with_signals.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=True)
    print(f"  Saved signals dataset to {out_path}")
    return out_path


def run_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute z-scores, print stats, plot, and save."""
    print("\n" + "=" * 60)
    print("Signals: Computing rolling z-scores (window=60)")
    print("=" * 60)
    df = compute_z_scores(df)

    print_signal_stats(df)

    print("\n" + "=" * 60)
    print("Signals: Generating z-score plots")
    print("=" * 60)
    plot_z_scores(df)

    save_signals_dataset(df)

    return df


if __name__ == "__main__":
    from src.analysis.eda import load_dataset

    df = load_dataset()
    df = run_signals(df)
    print(df[["spread_2y", "z_2y", "spread_5y", "z_5y", "spread_10y", "z_10y"]].tail(10))
