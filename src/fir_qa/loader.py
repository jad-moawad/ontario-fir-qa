"""
Loader for Ontario FIR Schedule 22 (Municipal and School Board Taxation) and
Schedule 26 (Taxation and Payments-In-Lieu Summary) files.

Handles the quirks of the raw xlsx format published by the Ministry of
Municipal Affairs and Housing:
  - Header row is on the 5th row (pandas header index 4)
  - First column is an internal ID that needs to be dropped
  - Column names contain embedded newlines
  - Numeric columns arrive as strings with mixed types

Schedule 26 has the same header-row-4 format as Schedule 22. Its column
codes follow the pattern "26 xxxx NN" where NN identifies the tier:
  03 = TOTAL Taxes
  04 = LT/ST Taxes
  05 = UT Taxes
  06 = EDUC Taxes

These are coerced to numeric by _clean_columns_s26.
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

S26_SHEET_1 = "SCHEDULE 26-1"
S26_SHEET_2 = "SCHEDULE 26-2"
S26_SHEET_3 = "SCHEDULE 26-3"


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _clean_columns_s26(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a Schedule 26 sheet: drop unnamed first column, coerce numerics."""
    df = df.copy()
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
    # Coerce all "26 xxxx NN" columns and the Line column to numeric
    for col in df.columns:
        if col.startswith("26 xxxx") or col == "Line":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "MunID" in df.columns:
        df["MunID"] = pd.to_numeric(df["MunID"], errors="coerce")
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


def load_schedule_26(path: str | Path) -> dict[str, pd.DataFrame]:
    """
    Load all sheets from a Schedule 26 file.

    Schedule 26 has three data sheets and a Legend sheet. Only the three
    data sheets are loaded here; the Legend contains only MSO and tier code
    definitions and is not needed for QA rules.

    Returns a dict with keys s26_1, s26_2, s26_3.
    """
    path = Path(path)
    result: dict[str, pd.DataFrame] = {}
    for key, sheet_name in [("s26_1", S26_SHEET_1),
                             ("s26_2", S26_SHEET_2),
                             ("s26_3", S26_SHEET_3)]:
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, header=4)
            result[key] = _clean_columns_s26(df)
        except Exception:
            result[key] = pd.DataFrame()
    return result
