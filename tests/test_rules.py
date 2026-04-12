"""
Smoke tests for the Ontario FIR QA framework.

These tests verify that every rule loads data, runs without raising, and
returns a DataFrame with the correct metadata columns. They do not assert
specific flag counts (those are documented in CLAUDE.md and findings.md)
because counts are expected to evolve as rules are refined.

Run with:
    PYTHONPATH=src pytest tests/test_rules.py -v
"""

import inspect

import pandas as pd
import pytest

from fir_qa.loader import load_schedule_22, load_schedule_26
from fir_qa.rules import ALL_RULES, run_all
from fir_qa.cross_year_rules import ALL_CROSS_YEAR_RULES, run_all_cross_year
from fir_qa.cross_schedule_rules import ALL_CROSS_SCHEDULE_RULES, run_all_cross_schedule

SCHEDULE_22_2023 = "data/raw/2023/schedule_22.xlsx"
SCHEDULE_26_2023 = "data/raw/2023/schedule_26.xlsx"
YEARS = [2019, 2020, 2021, 2022, 2023]
REQUIRED_META_COLS = {"rule_id", "rule_name", "severity"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sheets_2023():
    return load_schedule_22(SCHEDULE_22_2023)


@pytest.fixture(scope="session")
def sheets_by_year():
    return {y: load_schedule_22(f"data/raw/{y}/schedule_22.xlsx") for y in YEARS}


@pytest.fixture(scope="session")
def sheets_26_2023():
    return load_schedule_26(SCHEDULE_26_2023)


# ---------------------------------------------------------------------------
# Single-year rules (R01 through R07)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rule_fn", ALL_RULES, ids=[f.rule_id for f in ALL_RULES])
def test_single_year_rule_returns_dataframe(rule_fn, sheets_2023):
    """Every single-year rule must return a DataFrame without raising."""
    result = rule_fn(sheets_2023)
    assert isinstance(result, pd.DataFrame), (
        f"{rule_fn.rule_id} returned {type(result)}, expected DataFrame"
    )


@pytest.mark.parametrize("rule_fn", ALL_RULES, ids=[f.rule_id for f in ALL_RULES])
def test_single_year_rule_has_metadata_columns(rule_fn, sheets_2023):
    """Every rule result must have rule_id, rule_name, and severity columns."""
    result = rule_fn(sheets_2023)
    missing = REQUIRED_META_COLS - set(result.columns)
    assert not missing, (
        f"{rule_fn.rule_id} result is missing columns: {missing}"
    )


@pytest.mark.parametrize("rule_fn", ALL_RULES, ids=[f.rule_id for f in ALL_RULES])
def test_single_year_rule_metadata_is_consistent(rule_fn, sheets_2023):
    """Metadata column values must match the function's own attributes."""
    result = rule_fn(sheets_2023)
    if len(result) > 0:
        assert result["rule_id"].iloc[0] == rule_fn.rule_id
        assert result["rule_name"].iloc[0] == rule_fn.rule_name
        assert result["severity"].iloc[0] == rule_fn.severity


def test_run_all_returns_all_rules(sheets_2023):
    """run_all must return one entry per rule."""
    results = run_all(sheets_2023)
    assert len(results) == len(ALL_RULES)


def test_known_flag_counts_2023(sheets_2023):
    """
    Assert known flag counts on 2023 data as a regression guard.
    These numbers are documented in CLAUDE.md and findings.md. If a rule
    change causes them to shift, this test will catch it.
    """
    results = run_all(sheets_2023)
    counts = {
        df["rule_id"].iloc[0]: len(df)
        for df in results.values()
        if len(df) > 0
    }
    assert counts.get("R01", 0) == 0
    assert counts.get("R02", 0) == 0
    assert counts.get("R03", 0) == 0
    assert counts.get("R04", 0) == 0
    assert counts.get("R05", 0) == 9
    assert counts.get("R06", 0) == 95
    assert counts.get("R07", 0) == 1


# ---------------------------------------------------------------------------
# Cross-year rules (R08)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rule_fn", ALL_CROSS_YEAR_RULES, ids=[f.rule_id for f in ALL_CROSS_YEAR_RULES]
)
def test_cross_year_rule_returns_dataframe(rule_fn, sheets_by_year):
    result = rule_fn(sheets_by_year)
    assert isinstance(result, pd.DataFrame)


@pytest.mark.parametrize(
    "rule_fn", ALL_CROSS_YEAR_RULES, ids=[f.rule_id for f in ALL_CROSS_YEAR_RULES]
)
def test_cross_year_rule_has_metadata_columns(rule_fn, sheets_by_year):
    result = rule_fn(sheets_by_year)
    missing = REQUIRED_META_COLS - set(result.columns)
    assert not missing, f"{rule_fn.rule_id} missing columns: {missing}"


def test_r08_known_flag_count(sheets_by_year):
    """R08 must produce exactly 6 flags on the 2019-2023 dataset."""
    from fir_qa.cross_year_rules import rule_08_yoy_levy_change
    result = rule_08_yoy_levy_change(sheets_by_year)
    assert len(result) == 6, f"R08 returned {len(result)} flags, expected 6"


# ---------------------------------------------------------------------------
# Cross-schedule rules (R11, R12, R13)
# ---------------------------------------------------------------------------

def _call_cross_schedule(rule_fn, sheets_22, sheets_26, year):
    """Call a cross-schedule rule with the right number of positional args.

    R11 accepts (sheets_22, sheets_26, year); R12 and R13 accept only
    (sheets_22, sheets_26) because they do not need the year number.
    """
    sig = inspect.signature(rule_fn)
    n_params = len(sig.parameters)
    if n_params >= 3:
        return rule_fn(sheets_22, sheets_26, year)
    return rule_fn(sheets_22, sheets_26)


@pytest.mark.parametrize(
    "rule_fn",
    ALL_CROSS_SCHEDULE_RULES,
    ids=[f.rule_id for f in ALL_CROSS_SCHEDULE_RULES],
)
def test_cross_schedule_rule_returns_dataframe(rule_fn, sheets_2023, sheets_26_2023):
    result = _call_cross_schedule(rule_fn, sheets_2023, sheets_26_2023, 2023)
    assert isinstance(result, pd.DataFrame)


@pytest.mark.parametrize(
    "rule_fn",
    ALL_CROSS_SCHEDULE_RULES,
    ids=[f.rule_id for f in ALL_CROSS_SCHEDULE_RULES],
)
def test_cross_schedule_rule_has_metadata_columns(
    rule_fn, sheets_2023, sheets_26_2023
):
    result = _call_cross_schedule(rule_fn, sheets_2023, sheets_26_2023, 2023)
    missing = REQUIRED_META_COLS - set(result.columns)
    assert not missing, f"{rule_fn.rule_id} missing columns: {missing}"


def test_cross_schedule_clean_years_produce_zero_real_flags(
    sheets_by_year, sheets_26_2023
):
    """R11-R13 must produce zero real flags on 2023 data."""
    sheets_26 = {"2023": load_schedule_26(SCHEDULE_26_2023)}
    results = run_all_cross_schedule(
        sheets_by_year[2023],
        load_schedule_26(SCHEDULE_26_2023),
        2023,
    )
    for func_name, df in results.items():
        real_flags = df[df["MunID"].notna()] if "MunID" in df.columns else df
        assert len(real_flags) == 0, (
            f"{func_name} produced {len(real_flags)} real flags on 2023, expected 0"
        )
