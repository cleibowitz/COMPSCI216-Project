"""
Central configuration for API keys, date ranges, and file paths.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------- Project paths ----------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# ---------- LSEG OIS CSV paths ----------
# Exported from LSEG Workspace: SOFR OIS par rates at 2Y, 5Y, 10Y maturities.
OIS_2Y_PATH = RAW_DATA_DIR / "sofr_ois_2y.csv"
OIS_5Y_PATH = RAW_DATA_DIR / "sof_ois_5y.csv"
OIS_10Y_PATH = RAW_DATA_DIR / "sofr_ois_10y.csv"

# ---------- LSEG MOVE index path ----------
# ICE BofA MOVE index (annualised bp of implied Treasury vol).
MOVE_PATH = RAW_DATA_DIR / "MOVE_index.csv"

# ---------- FRED API ----------
# Set your FRED API key in .env:
#   FRED_API_KEY=your_key_here
# Free keys available at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = os.environ.get("FRED_API_KEY")

# Treasury yield series + EFFR for regime classification
TREASURY_SERIES = {
    "DGS2": "2-Year Treasury Yield",
    "DGS5": "5-Year Treasury Yield",
    "DGS10": "10-Year Treasury Yield",
    "EFFR": "Effective Federal Funds Rate",
}

# ---------- Date range ----------
# Start from 2019 to align with LSEG OIS data coverage.
START_DATE = "2019-01-01"
END_DATE = "2026-04-15"

# ---------- Output ----------
FINAL_DATASET_PATH = PROCESSED_DATA_DIR / "final_dataset.parquet"
