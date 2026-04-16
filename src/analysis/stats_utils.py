"""
Shared statistical helpers for RQ1/RQ2/RQ3 analysis.

The event-extraction and test-battery functions below are the core
building blocks. All downstream RQ analyses call these helpers and
then format/visualize the results.

Conventions
-----------
- Spread values are in percentage points (pp). The battery converts
  means and CIs to basis points (bps = pp * 100) for presentation.
- A "signal event" is a bar where |z_t| > threshold. Overlapping
  events (within min_gap bars of a prior event) are dropped to
  avoid counting the same economic episode multiple times.
"""

from typing import Tuple

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests


# ---------------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------------

def compute_z_scores(
    df: pd.DataFrame,
    spread_cols=("spread_2y", "spread_5y", "spread_10y"),
    window: int = 60,
) -> pd.DataFrame:
    """
    Add rolling-window z-score columns named z_2y / z_5y / z_10y (etc.).

    Returns a copy of df with the z-score columns added; existing
    columns are overwritten so callers can re-run with different windows.
    """
    out = df.copy()
    for col in spread_cols:
        tenor = col.replace("spread_", "")
        m = out[col].rolling(window=window, min_periods=window).mean()
        s = out[col].rolling(window=window, min_periods=window).std()
        out[f"z_{tenor}"] = (out[col] - m) / s
    return out


def _drop_overlapping_positions(positions: np.ndarray, min_gap: int) -> np.ndarray:
    """Greedy: keep first, skip any event within min_gap bars of last kept."""
    kept = []
    last = -np.inf
    for p in positions:
        if p - last > min_gap:
            kept.append(p)
            last = p
    return np.array(kept, dtype=int)


def extract_signal_events(
    df: pd.DataFrame,
    spread_col: str,
    z_col: str,
    threshold: float,
    direction: str,
    horizon: int,
    min_gap: int = 5,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return forward spread changes after non-overlapping signal events.

    Parameters
    ----------
    direction : "positive" (z > +threshold) or "negative" (z < -threshold)
    horizon   : forward horizon in bars
    min_gap   : minimum bars between consecutive kept events

    Returns
    -------
    fwd_changes : 1-D np.ndarray of spread[t+h] - spread[t] (in pp)
    event_pos   : 1-D np.ndarray of integer positions where events fired
    """
    z = df[z_col].values
    spread = df[spread_col].values

    if direction == "positive":
        mask = z > threshold
    elif direction == "negative":
        mask = z < -threshold
    else:
        raise ValueError("direction must be 'positive' or 'negative'")

    positions = np.where(np.nan_to_num(mask, nan=False))[0]
    positions = _drop_overlapping_positions(positions, min_gap=min_gap)

    fwd_changes = []
    kept = []
    n = len(spread)
    for p in positions:
        if p + horizon < n:
            v0, vh = spread[p], spread[p + horizon]
            if np.isfinite(v0) and np.isfinite(vh):
                fwd_changes.append(vh - v0)
                kept.append(p)

    return np.array(fwd_changes, dtype=float), np.array(kept, dtype=int)


# ---------------------------------------------------------------------------
# Statistical test battery
# ---------------------------------------------------------------------------

def bootstrap_mean_ci(
    sample: np.ndarray,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float]:
    """Vectorized percentile bootstrap CI for the mean."""
    if len(sample) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(sample), size=(n_boot, len(sample)))
    boot_means = sample[idx].mean(axis=1)
    low = np.percentile(boot_means, 100 * alpha / 2)
    high = np.percentile(boot_means, 100 * (1 - alpha / 2))
    return (float(low), float(high))


def run_stat_battery(sample: np.ndarray, n_bootstrap: int = 1000) -> dict:
    """
    Run the full test battery on a 1-D array of forward changes (in pp).

    Returns a dict with:
      n, mean_bps, std_pp, t_stat, t_pvalue,
      sign_p, wilcoxon_p, cohen_d,
      ci_low_bps, ci_high_bps, boot_low_bps, boot_high_bps
    """
    sample = np.asarray(sample, dtype=float)
    sample = sample[np.isfinite(sample)]
    n = len(sample)

    out = {
        "n": n, "mean_bps": np.nan, "std_pp": np.nan,
        "t_stat": np.nan, "t_pvalue": np.nan,
        "sign_p": np.nan, "wilcoxon_p": np.nan, "cohen_d": np.nan,
        "ci_low_bps": np.nan, "ci_high_bps": np.nan,
        "boot_low_bps": np.nan, "boot_high_bps": np.nan,
    }
    if n < 2:
        return out

    mean = float(np.mean(sample))
    std = float(np.std(sample, ddof=1))
    se = std / np.sqrt(n) if std > 0 else np.nan

    out["mean_bps"] = mean * 100.0
    out["std_pp"] = std
    out["cohen_d"] = mean / std if std > 0 else np.nan

    # Parametric 95% CI
    if np.isfinite(se):
        t_crit = stats.t.ppf(0.975, n - 1)
        out["ci_low_bps"] = (mean - t_crit * se) * 100.0
        out["ci_high_bps"] = (mean + t_crit * se) * 100.0

    # One-sample t-test
    t_stat, t_p = stats.ttest_1samp(sample, 0.0)
    out["t_stat"] = float(t_stat)
    out["t_pvalue"] = float(t_p)

    # Sign test via binomtest
    n_pos = int(np.sum(sample > 0))
    n_nonzero = int(np.sum(sample != 0))
    if n_nonzero > 0:
        st = stats.binomtest(n_pos, n_nonzero, p=0.5, alternative="two-sided")
        out["sign_p"] = float(st.pvalue)

    # Wilcoxon signed-rank test
    if np.any(sample != 0):
        try:
            _, w_p = stats.wilcoxon(sample, alternative="two-sided",
                                     zero_method="wilcox")
            out["wilcoxon_p"] = float(w_p)
        except ValueError:
            pass

    # Bootstrap percentile CI
    b_lo, b_hi = bootstrap_mean_ci(sample, n_boot=n_bootstrap)
    out["boot_low_bps"] = b_lo * 100.0
    out["boot_high_bps"] = b_hi * 100.0

    return out


# ---------------------------------------------------------------------------
# Multiple-testing correction
# ---------------------------------------------------------------------------

def bh_correct(pvalues, q: float = 0.05):
    """Benjamini-Hochberg FDR. Returns (adjusted_p, reject_flags)."""
    pvalues = np.asarray(pvalues, dtype=float)
    adjusted = np.full_like(pvalues, np.nan)
    reject = np.zeros_like(pvalues, dtype=bool)
    valid = np.isfinite(pvalues)
    if valid.sum() > 0:
        r, p_adj, _, _ = multipletests(pvalues[valid], alpha=q, method="fdr_bh")
        adjusted[valid] = p_adj
        reject[valid] = r
    return adjusted, reject


def sig_stars(p: float) -> str:
    """Conventional star notation for p-values."""
    if not np.isfinite(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    if p < 0.10:
        return "."
    return ""


# ---------------------------------------------------------------------------
# Maturity / tenor conventions used by the RQ modules
# ---------------------------------------------------------------------------

MATURITIES = ("2y", "5y", "10y")
SPREAD_COLS = tuple(f"spread_{t}" for t in MATURITIES)
Z_COLS = tuple(f"z_{t}" for t in MATURITIES)
DIRECTIONS = ("negative", "positive")   # z < -thr, z > +thr

DIR_LABEL = {"negative": "z<-thr", "positive": "z>+thr"}

# Expected sign of forward change under mean reversion
#   After z > +thr (spread too high) → forward change should be NEGATIVE
#   After z < -thr (spread too low)  → forward change should be POSITIVE
EXPECTED_SIGN = {"positive": -1, "negative": +1}
