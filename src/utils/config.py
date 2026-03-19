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

# ---------- FRED API ----------
# Set your FRED API key in .env:
#   FRED_API_KEY=your_key_here
# Free keys available at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = os.environ.get("FRED_API_KEY")

# Treasury yield series
TREASURY_SERIES = {
    "DGS2": "2-Year Treasury Yield",
    "DGS5": "5-Year Treasury Yield",
    "DGS10": "10-Year Treasury Yield",
}

# SOFR series (all available for free on FRED)
SOFR_SERIES = {
    "SOFR": "SOFR Overnight Rate",
    "SOFR30DAYAVG": "SOFR 30-Day Average",
    "SOFR90DAYAVG": "SOFR 90-Day Average",
    "SOFR180DAYAVG": "SOFR 180-Day Average",
    "EFFR": "Effective Federal Funds Rate",
}

# ---------- Date range ----------
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"

# ---------- Output ----------
FINAL_DATASET_PATH = PROCESSED_DATA_DIR / "final_dataset.parquet"
