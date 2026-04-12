"""
Run QA rules on FIR Schedule 22 data and write reports to disk.

Single-year mode (existing behaviour):

    python -m fir_qa.engine data/raw/2023/schedule_22.xlsx reports/2023

    Writes to the output directory:
        summary.csv       one row per rule with flag counts
        <rule_id>_flags.csv  detailed flag rows for each rule that fired

Cross-year mode (new in Phase 1):

    python -m fir_qa.engine cross_year data/raw/ reports/cross_year

    Discovers all schedule_22.xlsx files under data/raw/ by scanning for
    files matching */schedule_22.xlsx one level deep, loads each, and runs
    cross-year rules across all available years.

    Writes to the output directory:
        cross_year_summary.csv       one row per rule with flag counts
        <rule_id>_flags.csv          detailed flag rows for each rule

Cross-schedule mode (new in Phase 2):

    python -m fir_qa.engine cross_schedule data/raw/ reports/cross_schedule

    Discovers all (schedule_22.xlsx, schedule_26.xlsx) pairs under data/raw/
    and runs cross-schedule rules (R11 through R13) on each year. Produces
    per-year reports plus a combined summary.

    Writes to the output directory:
        cross_schedule_summary.csv      one row per (year, rule) with flag counts
        <year>_<rule_id>_flags.csv      detailed flag rows for each year/rule
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from fir_qa.loader import load_schedule_22, load_schedule_26
from fir_qa.rules import run_all, ALL_RULES
from fir_qa.cross_year_rules import run_all_cross_year, ALL_CROSS_YEAR_RULES
from fir_qa.cross_schedule_rules import (
    run_all_cross_schedule,
    ALL_CROSS_SCHEDULE_RULES,
)


def build_summary(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build a one-row-per-rule summary DataFrame."""
    # Build a lookup from function name to the rule function itself so
    # we can read metadata attributes even when a rule returned an
    # empty DataFrame.
    by_name = {f.__name__: f for f in ALL_RULES}
    rows = []
    for func_name, df in results.items():
        func = by_name[func_name]
        if len(df) == 0:
            rows.append({
                "rule_id": func.rule_id,
                "rule_name": func.rule_name,
                "severity": func.severity,
                "n_flags": 0,
                "n_municipalities": 0,
            })
        else:
            rows.append({
                "rule_id": df["rule_id"].iloc[0],
                "rule_name": df["rule_name"].iloc[0],
                "severity": df["severity"].iloc[0],
                "n_flags": len(df),
                "n_municipalities": df["Municipality"].nunique(),
            })
    return pd.DataFrame(rows)


def run(input_path: str | Path, output_dir: str | Path) -> pd.DataFrame:
    """Run all rules against one Schedule 22 file and write outputs."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sheets = load_schedule_22(input_path)
    results = run_all(sheets)

    summary = build_summary(results)
    summary.to_csv(output_dir / "summary.csv", index=False)

    for func_name, df in results.items():
        if len(df) == 0:
            continue
        rule_id = df["rule_id"].iloc[0]
        df.to_csv(output_dir / f"{rule_id}_flags.csv", index=False)

    return summary


def print_summary(summary: pd.DataFrame, source: Path) -> None:
    total = int(summary["n_flags"].sum())
    errors = int(
        summary.loc[summary["severity"] == "error", "n_flags"].sum()
    )
    warnings = int(
        summary.loc[summary["severity"] == "warning", "n_flags"].sum()
    )

    print("=" * 72)
    print(f"Ontario FIR Schedule 22 QA Report")
    print(f"Source: {source}")
    print("=" * 72)
    print()
    print(summary.to_string(index=False))
    print()
    print(f"Total flags:     {total}")
    print(f"  errors:        {errors}")
    print(f"  warnings:      {warnings}")
    print()


def build_cross_year_summary(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build a one-row-per-rule summary DataFrame for cross-year results."""
    by_name = {f.__name__: f for f in ALL_CROSS_YEAR_RULES}
    rows = []
    for func_name, df in results.items():
        func = by_name[func_name]
        if len(df) == 0:
            rows.append({
                "rule_id": func.rule_id,
                "rule_name": func.rule_name,
                "severity": func.severity,
                "n_flags": 0,
                "n_municipalities": 0,
            })
        else:
            rows.append({
                "rule_id": df["rule_id"].iloc[0],
                "rule_name": df["rule_name"].iloc[0],
                "severity": df["severity"].iloc[0],
                "n_flags": len(df),
                # A flag spans two years; count distinct municipality IDs.
                "n_municipalities": df["Municipality"].nunique(),
            })
    return pd.DataFrame(rows)


def run_cross_year(data_dir: str | Path, output_dir: str | Path) -> pd.DataFrame:
    """
    Discover all schedule_22.xlsx files under data_dir, load them, run
    cross-year rules, and write outputs to output_dir.

    Expects files at <data_dir>/<year>/schedule_22.xlsx. Years are inferred
    from the parent directory name; non-integer directory names are skipped.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sheets_by_year: dict[int, dict[str, pd.DataFrame]] = {}
    for xlsx in sorted(data_dir.glob("*/schedule_22.xlsx")):
        try:
            year = int(xlsx.parent.name)
        except ValueError:
            continue
        sheets_by_year[year] = load_schedule_22(xlsx)

    if len(sheets_by_year) < 2:
        print(f"Cross-year rules require at least 2 years of data; "
              f"found {len(sheets_by_year)} under {data_dir}")
        return pd.DataFrame()

    years = sorted(sheets_by_year.keys())
    print("=" * 72)
    print("Ontario FIR Schedule 22 Cross-Year QA Report")
    print(f"Data directory: {data_dir}")
    print(f"Years loaded:   {years}")
    print("=" * 72)
    print()

    results = run_all_cross_year(sheets_by_year)
    summary = build_cross_year_summary(results)
    summary.to_csv(output_dir / "cross_year_summary.csv", index=False)

    for func_name, df in results.items():
        if len(df) == 0:
            continue
        rule_id = df["rule_id"].iloc[0]
        df.to_csv(output_dir / f"{rule_id}_flags.csv", index=False)

    total = int(summary["n_flags"].sum())
    warnings = int(
        summary.loc[summary["severity"] == "warning", "n_flags"].sum()
    )
    print(summary.to_string(index=False))
    print()
    print(f"Total flags:     {total}")
    print(f"  warnings:      {warnings}")
    print()
    print(f"Reports written to: {output_dir}/")
    return summary


def build_cross_schedule_summary(
    results_by_year: dict[int, dict[str, pd.DataFrame]]
) -> pd.DataFrame:
    """Build a one-row-per-(year, rule) summary for cross-schedule results."""
    by_name = {f.__name__: f for f in ALL_CROSS_SCHEDULE_RULES}
    rows = []
    for year, results in sorted(results_by_year.items()):
        for func_name, df in results.items():
            func = by_name[func_name]
            if len(df) == 0:
                rows.append({
                    "year": year,
                    "rule_id": func.rule_id,
                    "rule_name": func.rule_name,
                    "severity": func.severity,
                    "n_flags": 0,
                    "n_municipalities": 0,
                })
            else:
                # A skip row has MunID=None; count real flags only
                real_flags = df[df["MunID"].notna()]
                rows.append({
                    "year": year,
                    "rule_id": df["rule_id"].iloc[0],
                    "rule_name": df["rule_name"].iloc[0],
                    "severity": df["severity"].iloc[0],
                    "n_flags": len(real_flags),
                    "n_municipalities": (
                        real_flags["MunID"].nunique() if len(real_flags) > 0 else 0
                    ),
                })
    return pd.DataFrame(rows)


def run_cross_schedule(data_dir: str | Path, output_dir: str | Path) -> pd.DataFrame:
    """
    Discover all (schedule_22.xlsx, schedule_26.xlsx) pairs under data_dir,
    run cross-schedule rules on each year, and write outputs.

    Years are inferred from the parent directory name (must be an integer).
    A year is skipped if schedule_22.xlsx is missing. If schedule_26.xlsx
    is missing for a year, R11 emits a skip row but R12 and R13 still run
    against schedule_22 alone.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    year_dirs = []
    for p in sorted(data_dir.iterdir()):
        if not p.is_dir():
            continue
        try:
            year = int(p.name)
        except ValueError:
            continue
        s22_path = p / "schedule_22.xlsx"
        if not s22_path.exists():
            continue
        year_dirs.append((year, p))

    print("=" * 72)
    print("Ontario FIR Cross-Schedule QA Report (Phase 2)")
    print(f"Data directory: {data_dir}")
    print(f"Years found:    {[y for y, _ in year_dirs]}")
    print("=" * 72)
    print()

    results_by_year: dict[int, dict[str, pd.DataFrame]] = {}

    for year, year_dir in year_dirs:
        s22_path = year_dir / "schedule_22.xlsx"
        s26_path = year_dir / "schedule_26.xlsx"

        print(f"Loading {year}...")
        sheets_22 = load_schedule_22(s22_path)
        sheets_26 = load_schedule_26(s26_path) if s26_path.exists() else {}

        results = run_all_cross_schedule(sheets_22, sheets_26, year)
        results_by_year[year] = results

        for func_name, df in results.items():
            if len(df) == 0:
                continue
            rule_id = df["rule_id"].iloc[0]
            out_path = output_dir / f"{year}_{rule_id}_flags.csv"
            df.to_csv(out_path, index=False)

    summary = build_cross_schedule_summary(results_by_year)
    summary.to_csv(output_dir / "cross_schedule_summary.csv", index=False)

    # Print summary
    print(summary.to_string(index=False))
    print()
    total_real_flags = int(summary["n_flags"].sum())
    total_errors = int(
        summary.loc[summary["severity"] == "error", "n_flags"].sum()
    )
    print(f"Total real flags:  {total_real_flags}")
    print(f"  errors:          {total_errors}")
    print()
    print(f"Reports written to: {output_dir}/")
    return summary


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "cross_year":
        run_cross_year(sys.argv[2], sys.argv[3])
        return 0

    if len(sys.argv) == 4 and sys.argv[1] == "cross_schedule":
        run_cross_schedule(sys.argv[2], sys.argv[3])
        return 0

    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    source = Path(sys.argv[1])
    out = Path(sys.argv[2])
    summary = run(source, out)
    print_summary(summary, source)
    print(f"Reports written to: {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
