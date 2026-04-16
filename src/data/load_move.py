"""
Load the ICE BofA MOVE index from an LSEG Workspace CSV export.

The MOVE CSV has a different column layout than the OIS files:
  header row: Exchange Date, Close, Net, %Chg, Open, Low, High
We only need Exchange Date (col 0) and Close (col 1).

MOVE is reported as annualised basis-points of implied Treasury
volatility (e.g. 87.5 means ~87.5 bp/year).  No unit conversion needed.
"""

import pandas as pd
from pathlib import Path

from src.utils.config import MOVE_PATH


def load_move_index(path: Path = MOVE_PATH) -> pd.Series:
    """
    Parse the LSEG MOVE index CSV and return a daily Close series.

    Returns
    -------
    pd.Series
        MOVE index (bp), indexed by date, sorted ascending.  Name: 'MOVE'.
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Locate header row that starts with "Exchange Date,"
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Exchange Date,"):
            header_idx = i
            break

    if header_idx is None:
        raise ValueError(f"Could not locate 'Exchange Date,' header row in {path}")

    df = pd.read_csv(
        path,
        skiprows=header_idx,
        encoding="utf-8-sig",
        usecols=[0, 1],
        header=0,
        names=["date", "MOVE"],
    )

    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
    df = df.dropna(subset=["date"])
    df["MOVE"] = pd.to_numeric(df["MOVE"], errors="coerce")
    s = df.set_index("date")["MOVE"].dropna().sort_index()
    s.name = "MOVE"

    print(f"  MOVE index: {len(s)} observations  |  "
          f"range {s.index.min().date()} to {s.index.max().date()}  |  "
          f"[{s.min():.1f}, {s.max():.1f}] bp")

    return s


if __name__ == "__main__":
    s = load_move_index()
    print(s.tail(5))
