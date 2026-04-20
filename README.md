# Relative Value Analysis of U.S. Treasury Yields and SOFR OIS Rates

COMPSCI 216 Final Project — Duke University

**Authors:** Chase Leibowitz (crl65), Dhruv Trivedi (dpt10), Jose Maldonado (jam348), Felipe Sanchez-Noguera (fs172)

---

## Overview

This project studies mean reversion in OIS–Treasury spreads at 2Y, 5Y, and 10Y maturities using 7+ years of daily data (January 2019 – April 2026). It combines classical statistical inference (t-tests, sign tests, Wilcoxon, bootstrap CIs, BH-FDR correction, two-way ANOVA) with an unsupervised Hidden Markov Model for regime detection and a supervised Random Forest classifier, and ends with an out-of-sample backtest of three trading strategies.

**Headline finding.** Mean reversion is real (100% of 162 robustness cells carry the predicted sign, 73% survive BH-FDR) and regime-dependent (partial η² = 0.28 for rate regime on the 5Y spread). The same HMM regime state that *lowers* Random Forest AUC by 0.12 as a continuous feature *raises* out-of-sample Sharpe by 0.12 when used as a binary trade-entry gate — functional form dominates the model choice.

The final report is `ois_treasury_mean_reversion.qmd` (Quarto → PDF). See Section 4 ("Results and Methods") for the main analysis and Appendices A–D for extended detail.

## Research questions

- **RQ1** — Do OIS-Treasury spreads mean-revert after extreme ±2σ z-score signals?
- **RQ2** — Is this result robust to the choice of rolling window, threshold, and forward horizon?
- **RQ3** — Does mean reversion differ across rate-direction and volatility regimes?
- **Applied extension** — Can an unsupervised HMM detect those regimes in a way that improves out-of-sample trading performance more than a supervised classifier can?

## Repository layout

```
COMPSCI216-Project/
├── main.py                    # Data + EDA + RQ1/RQ2/RQ3 pipeline
├── run_ml.py                  # HMM regime detection + Random Forest classifier
├── run_backtest.py            # OOS backtest of 3 strategies
├── ois_treasury_mean_reversion.qmd    # Final report source (Quarto)
├── ois_treasury_mean_reversion.pdf    # Rendered report
├── requirements.txt
│
├── data/
│   ├── raw/                   # LSEG OIS CSVs, MOVE CSV (unmodified vendor exports)
│   └── processed/             # Derived parquet files produced by main.py
│
├── src/
│   ├── data/
│   │   ├── fetch_fred.py           # FRED Treasury yields + EFFR
│   │   ├── fetch_sofr_futures.py   # LSEG OIS CSV loader
│   │   ├── process_sofr.py         # OIS scale validation + NaN handling
│   │   ├── load_move.py            # MOVE index loader
│   │   └── build_dataset.py        # Merge + spread + regime construction
│   ├── analysis/
│   │   ├── eda.py                  # Exploratory plots + summary stats
│   │   ├── signals.py              # Rolling z-scores + signal events
│   │   ├── stats_utils.py          # t-tests, bootstrap CIs, FDR, event extraction
│   │   ├── rq1.py / rq2.py / rq3.py
│   │   ├── rq_analysis.py          # Thin orchestrator
│   │   ├── hmm_regimes.py          # 2-state Gaussian HMM (Baum-Welch)
│   │   ├── rf_classifier.py        # Random Forest + ablation + SHAP
│   │   └── backtest.py             # 3-strategy OOS backtest
│   └── utils/config.py
│
├── outputs/
│   ├── figures/                # All PNGs referenced by the report
│   │   └── archive/            # Deprecated prototype figures (retained for audit)
│   ├── tables/                 # CSVs: RQ results, robustness grid, summary stats
│   ├── ml/                     # dataset_with_hmm.parquet, rf_model.pkl, metrics
│   ├── backtest_trades.csv
│   └── backtest_metrics.csv
│
├── reports/                    # Prior prototype report(s)
├── archive/                    # Deprecated prototype scripts and outputs
└── notebooks/                  # Exploration notebooks
```

## Data sources

| Source | Ticker / Series | Description | Role |
|--------|-----------------|-------------|------|
| FRED   | DGS2 / DGS5 / DGS10 | Treasury CMT yields | Matched-maturity benchmarks |
| FRED   | EFFR            | Effective Fed Funds | Rate-regime classifier |
| LSEG   | USDOIS2Y=PYNY, USDOIS5Y=PYNY, USDOIS10Y=PYNY | SOFR OIS par rates | Swap rates |
| LSEG   | .MOVE           | ICE BofA MOVE Index | Implied Treasury vol |

Final panel: 1,890 daily observations spanning 2019-01-01 → 2026-04-14. LSEG OIS rates are SOFR-based; EFFR is used solely as a rate-regime classifier.

## Setup

Python 3.9 is required (the pinned `numpy==1.24.4` / `pandas==1.5.3` combination targets Python 3.9; `pyarrow < 15` is required for parquet compatibility with these versions).

```bash
# From the project root
python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**FRED API key.** Set `FRED_API_KEY` in a local `.env` file (loaded via `python-dotenv`). Obtain a free key at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html).

```
# .env
FRED_API_KEY=your_key_here
```

**LSEG CSVs.** The raw LSEG exports (`sofr_ois_2y.csv`, `sof_ois_5y.csv`, `sofr_ois_10y.csv`, `MOVE.csv`) are committed under `data/raw/`. No LSEG API calls are made at runtime.

## Reproducing the analysis

Run the three entry-point scripts in order:

```bash
# 1. Data pipeline, EDA, RQ1/RQ2/RQ3
python main.py

# 2. HMM regimes + Random Forest classifier (+ ablation + SHAP)
python run_ml.py

# 3. Out-of-sample backtest (3 strategies, 2024-01-02 onward)
python run_backtest.py
```

Each script prints a step-by-step log and writes all outputs to `data/processed/`, `outputs/figures/`, `outputs/tables/`, and `outputs/ml/`. Total wall-clock runtime is under 3 minutes on a 2021 MacBook Pro.

### Rendering the report

```bash
quarto render ois_treasury_mean_reversion.qmd
```

This produces `ois_treasury_mean_reversion.pdf`. The Quarto file uses a LaTeX PDF engine (default `xelatex` or `pdflatex`). Running raw `pandoc` on the `.qmd` file is **not** supported — Quarto-specific YAML options (e.g., `linestretch`) and short-code cross-references require the Quarto toolchain.

## Key methodological choices

| Decision | Value | Rationale |
|----------|-------|-----------|
| Rolling window for z-score | 60 business days | ~3 months; balances reactivity and stability |
| Signal threshold | \|z\| > 2 | Standard relative-value entry trigger |
| Non-overlap filter | 5-day minimum gap | Prevents double-counting the same economic episode |
| Forward horizons | 5, 10, 20 business days | RQ2 robustness; main-text table uses 10d |
| Multiple-comparisons control | Benjamini–Hochberg FDR, q < 0.05 | Across 18- and 162-cell panels |
| HMM specification | 2-state Gaussian, full covariance, Baum-Welch | Smallest model that separates stress/calm |
| HMM features | `spread_5y`, 60-day ΔEFFR | Bivariate, standardized |
| RF specification | 500 trees, max_depth=4, min_samples_leaf=5 | Deliberate regularization for n=85 |
| RF target | 5Y spread reverts ≥3 bps in 10 days | Binary classification |
| Train/test split | Time-based, 2019→2023-12-31 vs 2024+ | No shuffling — avoids look-ahead |
| Backtest costs | 1 bp round-trip, 0.5 bp per side | Stylized cleared-OIS execution |
| 2Y treatment in ML | Excluded | 23 LSEG quoting artifacts — see Appendix A |

## Key outputs

**Main-text figures** (all under `outputs/figures/`):
- `rq1_event_study.png` — RQ1 event study, all 6 maturity×direction panels
- `rq2_heatmap.png` — RQ2 p-value heatmap across window × threshold
- `rq3_move_scatter.png` — MOVE continuous moderator scatter
- `backtest_cumulative_v2.png` — Cumulative P&L, 3 strategies, HMM-regime shading

**Model artifact:** `outputs/ml/rf_model.pkl` (joblib-serialized fitted RF).

**Tables (CSV):** `outputs/tables/rq1_master.csv`, `rq2_grid.csv`, `rq3_part_a.csv`, `rq3_anova.csv`; `outputs/backtest_trades.csv`, `outputs/backtest_metrics.csv`.

## Limitations and scope

- OOS backtest window is 27 months with 29 signal events — directionally informative but not statistically conclusive. Sharpe differences between strategies should be read with wide uncertainty.
- ML training set is 85 total events, genuinely tight for a 10-feature classifier.
- 2Y spread retains 23 LSEG quoting artifacts in the classical analysis (excluded from ML).
- Transaction-cost assumption is a flat 1 bp round-trip; realistic execution would require size-dependent market-impact modeling.

## AI disclosure

AI tools (Claude Opus 4.6 via Claude Code; Claude Sonnet 4.6 via claude.ai; ChatGPT for early scoping) were used for code generation, pipeline orchestration, and report drafting. Every methodological decision was reviewed and authorized by the human authors, and every reported number was re-run from the delivered code. See Section 7 of the report for the full disclosure.

---

*This README was generated by [Claude Code](https://claude.ai/code).*
