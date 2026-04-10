"""
Loader for Ontario FIR Schedule 22 (Municipal and School Board Taxation) files.

Handles the quirks of the raw xlsx format published by the Ministry of
Municipal Affairs and Housing:
  - Header row is on the 5th row (pandas header index 4)
  - First column is an internal ID that needs to be dropped
  - Column names contain embedded newlines
  - Numeric columns arrive as strings with mixed types
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


NUMERIC_COLUMNS = [
    "CVA Assessment",
    "Phase-In Taxable Assessment",
    "LT/ST Tax Rate",
    "UT Tax Rate",
    "EDUC Tax Rate",
    "TOTAL Tax Rate",
    "LT/ST Taxes",
    "UT Taxes",
    "EDUC Taxes",
    "TOTAL Taxes",
    "Tax Ratio",
    "% Full Rate",
]

GPL_SHEET = "SCHEDULE 22GPL"
SRA_LT_SHEET = "SCHEDULE 22SRA-LT"
SRA_UT_SHEET = "SCHEDULE 22SRA-UT"
SPC_SHEET = "SCHEDULE 22SPC"
TOTAL_SHEET = "SCHEDULE 22Total"


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_sheet(path: str | Path, sheet: str, header_row: int = 4) -> pd.DataFrame:
    """Load a single Schedule 22 sheet with the standard cleanup applied."""
    df = pd.read_excel(path, sheet_name=sheet, header=header_row)
    return _clean_columns(df)


def load_schedule_22(path: str | Path) -> dict[str, pd.DataFrame]:
    """Load all relevant sheets from a Schedule 22 file."""
    return {
        "gpl": load_sheet(path, GPL_SHEET),
        "sra_lt": load_sheet(path, SRA_LT_SHEET),
        "sra_ut": load_sheet(path, SRA_UT_SHEET),
        "spc": load_sheet(path, SPC_SHEET),
        "total": load_sheet(path, TOTAL_SHEET),
    }
