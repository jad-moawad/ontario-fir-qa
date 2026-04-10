"""
Quality assurance rules for Ontario FIR Schedule 22 data.

Each rule is a function that takes the loaded sheets dict and returns a
DataFrame of flagged rows. Every flag row carries:
  - rule_id:        short identifier for the rule
  - rule_name:      human-readable name
  - severity:       "error" (definite problem) or "warning" (needs review)
  - MunID, Municipality: which municipality the flag belongs to
  - detail:         a one-line explanation of what failed
  - plus any rule-specific columns
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# Provincial residential education tax rates by year (RT class, LT/ST tier).
# Source: Ontario Regulation 400/98 (Tax Matters - Tax Rates for School Purposes).
# The rate dropped from 0.00161 to 0.00153 between 2019 and 2020 and has
# held at 0.00153 since. Add new years here as data becomes available.
STD_RESIDENTIAL_EDUC_RATE: dict[int, float] = {
    2019: 0.00161,
    2020: 0.00153,
    2021: 0.00153,
    2022: 0.00153,
    2023: 0.00153,
}


def _rule_meta(rule_id: str, rule_name: str, severity: str):
    """Decorator that attaches rule metadata to a rule function."""
    def wrap(func):
        func.rule_id = rule_id
        func.rule_name = rule_name
        func.severity = severity
        return func
    return wrap


def _flag(df: pd.DataFrame, rule_id: str, rule_name: str,
          severity: str, detail_col: str = "detail") -> pd.DataFrame:
    """Attach rule metadata columns to a flagged-row DataFrame."""
    out = df.copy()
    out.insert(0, "rule_id", rule_id)
    out.insert(1, "rule_name", rule_name)
    out.insert(2, "severity", severity)
    return out


@_rule_meta("R01", "Template arithmetic integrity", "error")
def rule_01_template_arithmetic(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Rule 01: Within-row arithmetic integrity.

    For each GPL row: Phase-In Taxable Assessment x (tier rate) should
    equal the reported tax for that tier, within a tolerance of max($1,
    0.5% of expected). Also checks that the TOTAL rate and TOTAL taxes
    are the sum of their components.

    The FIR template enforces this via Excel formulas, so in a healthy
    file this rule should flag zero rows. Its purpose is to act as a
    canary for file corruption or manual overrides.
    """
    gpl = sheets["gpl"]
    active = gpl[gpl["Phase-In Taxable Assessment"].fillna(0) > 0].copy()
    flags: list[pd.DataFrame] = []

    # Tolerance: $1 absolute for individual tiers, $2 for TOTAL (absorbs
    # rounding-propagation when the template rounds each tier before
    # summing into TOTAL), or 0.5% relative, whichever is larger.
    tier_pairs = [
        ("LT/ST Tax Rate", "LT/ST Taxes", "LT_ST", 1.0),
        ("UT Tax Rate", "UT Taxes", "UT", 1.0),
        ("EDUC Tax Rate", "EDUC Taxes", "EDUC", 1.0),
        ("TOTAL Tax Rate", "TOTAL Taxes", "TOTAL", 2.0),
    ]

    for rate_col, tax_col, tier_label, abs_tol in tier_pairs:
        expected = active["Phase-In Taxable Assessment"] * active[rate_col].fillna(0)
        actual = active[tax_col].fillna(0)
        tol = np.maximum(abs_tol, 0.005 * np.abs(expected))
        mask = np.abs(actual - expected) > tol
        if mask.any():
            sub = active[mask].copy()
            sub["tier"] = tier_label
            sub["expected_tax"] = expected[mask].round(0)
            sub["actual_tax"] = actual[mask]
            sub["discrepancy"] = (actual[mask] - expected[mask]).round(0)
            sub["detail"] = (
                tier_label
                + " taxes differ from assessment * rate by $"
                + sub["discrepancy"].abs().astype(int).astype(str)
            )
            flags.append(sub[["MunID", "Municipality", "Property Class", "tier",
                              "expected_tax", "actual_tax", "discrepancy", "detail"]])

    # Component-sum checks (rates and taxes)
    rate_sum = (active["LT/ST Tax Rate"].fillna(0)
                + active["UT Tax Rate"].fillna(0)
                + active["EDUC Tax Rate"].fillna(0))
    rate_mask = np.abs(active["TOTAL Tax Rate"].fillna(0) - rate_sum) > 1e-7
    if rate_mask.any():
        sub = active[rate_mask].copy()
        sub["tier"] = "RATE_SUM"
        sub["expected_tax"] = np.nan
        sub["actual_tax"] = np.nan
        sub["discrepancy"] = np.nan
        sub["detail"] = "TOTAL tax rate does not equal sum of LT/ST + UT + EDUC rates"
        flags.append(sub[["MunID", "Municipality", "Property Class", "tier",
                          "expected_tax", "actual_tax", "discrepancy", "detail"]])

    if not flags:
        empty = pd.DataFrame(columns=["MunID", "Municipality", "Property Class",
                                      "tier", "expected_tax", "actual_tax",
                                      "discrepancy", "detail"])
        return _flag(empty, "R01", "Template arithmetic integrity", "error")

    result = pd.concat(flags, ignore_index=True)
    return _flag(result, "R01", "Template arithmetic integrity", "error")


@_rule_meta("R02", "Residential tax ratio = 1.00", "error")
def rule_02_residential_tax_ratio(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Rule 02: Residential tax ratio must equal 1.00.

    Under Ontario's property tax system, the residential class is the
    reference class and its tax ratio is fixed at 1.00 by definition.
    Any residential row with a different ratio is a data entry error.

    This rule restricts to RTC/RTQ code RT (main residential class).
    Sub-classes such as R1 (Farm Awaiting Development Phase I) retain
    farmland's 0.25 ratio by regulation and are excluded here.
    """
    gpl = sheets["gpl"]
    res = gpl[
        (gpl["Property Class"] == "Residential") & (gpl["RTC/RTQ"] == "RT")
    ].copy()
    mask = res["Tax Ratio"].notna() & (res["Tax Ratio"] != 1.0)
    flagged = res[mask].copy()
    flagged["detail"] = (
        "Residential tax ratio is "
        + flagged["Tax Ratio"].round(4).astype(str)
        + ", expected 1.0000"
    )
    cols = ["MunID", "Municipality", "Tier", "RTC/RTQ",
            "Tax Rate Description", "Tax Ratio", "detail"]
    return _flag(flagged[cols], "R02", "Residential tax ratio = 1.00", "error")


@_rule_meta("R03", "Standard residential EDUC rate", "error")
def rule_03_residential_educ_rate(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Rule 03: Standard residential education rate.

    The provincial residential education tax rate is set by Ontario
    Regulation 400/98 and is uniform across the province for the main
    residential class. The rate is looked up from STD_RESIDENTIAL_EDUC_RATE
    using the Year column in the data, so the rule handles multi-year runs
    without hardcoding a single year's value.

    If the data's year is not in the lookup table, the rule is skipped
    rather than applying a potentially wrong rate.

    This rule only applies to:
      - Lower-tier and single-tier municipalities (upper-tier do not
        levy education taxes directly, so their EDUC rate is NaN).
      - RTC/RTQ code RT (main residential class). Sub-classes like R1
        (Farm Awaiting Development Phase 1) have their own rates set
        under separate regulations.
      - Rows with taxable assessment > 0.
    """
    gpl = sheets["gpl"]

    empty_cols = ["MunID", "Municipality", "Tier", "RTC/RTQ",
                  "Phase-In Taxable Assessment", "EDUC Tax Rate", "detail"]
    empty = pd.DataFrame(columns=empty_cols)

    year_vals = gpl["Year"].dropna()
    if year_vals.empty:
        return _flag(empty, "R03", "Standard residential EDUC rate", "error")
    year = int(year_vals.mode().iloc[0])
    expected_rate = STD_RESIDENTIAL_EDUC_RATE.get(year)
    if expected_rate is None:
        return _flag(empty, "R03", "Standard residential EDUC rate", "error")

    mask = (
        (gpl["Property Class"] == "Residential")
        & (gpl["Tier"].isin(["LT", "ST"]))
        & (gpl["RTC/RTQ"] == "RT")
        & (gpl["Phase-In Taxable Assessment"].fillna(0) > 0)
    )
    candidates = gpl[mask].copy()
    wrong = candidates[
        candidates["EDUC Tax Rate"].round(6) != expected_rate
    ].copy()
    wrong["detail"] = (
        "Residential EDUC rate is "
        + wrong["EDUC Tax Rate"].round(6).astype(str)
        + f", expected {expected_rate} for {year}"
    )
    return _flag(wrong[empty_cols], "R03", "Standard residential EDUC rate", "error")


@_rule_meta("R04", "GPL <-> Total sheet reconciliation", "error")
def rule_04_gpl_total_reconciliation(
    sheets: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Rule 04: GPL sum reconciles to Total sheet line 9299.

    For every municipality, the sum of LT/ST, UT, EDUC and TOTAL taxes
    across all rows in the GPL sheet must equal the value reported on
    line 9299 of the Total sheet.

    Line 9299 is the template's post-aggregation GPL total: a single
    row per municipality that sums across all levy areas. (Line 9201
    can have multiple rows per municipality when a municipality is
    split into several levy areas, e.g. Frontenac Islands has one line
    9201 row for Howe Island and another for Wolfe Island.)

    Any mismatch indicates a broken roll-up, a missing GPL row, or a
    duplicate row that got double-counted.
    """
    gpl = sheets["gpl"]
    total = sheets["total"]

    # Zero-tolerance pre-check: every MunID that appears in both GPL and
    # Total sheet must map to the same municipality name. A MunID is a
    # unique key; any name mismatch means the Total sheet's MunID column
    # is corrupted and a join-based reconciliation would produce spurious
    # results. Skip the rule and emit a single diagnostic row instead.
    gpl_id_name = gpl.groupby("MunID")["Municipality"].first()
    total_id_name = total.groupby("MunID")["Municipality"].first()
    common_ids = gpl_id_name.index.intersection(total_id_name.index)
    mismatches = common_ids[gpl_id_name[common_ids] != total_id_name[common_ids]]
    if len(mismatches) > 0:
        sample_parts = [
            f"MunID {mid}: GPL={gpl_id_name[mid]!r} Total={total_id_name[mid]!r}"
            for mid in mismatches[:3]
        ]
        detail = (
            f"R04 SKIPPED: Total sheet MunID column appears corrupted "
            f"({len(mismatches)} of {len(gpl_id_name)} MunIDs map to a different "
            f"municipality name than the GPL sheet). Sample: "
            + "; ".join(sample_parts)
        )
        skip_row = pd.DataFrame([{
            "MunID": None,
            "Municipality": None,
            "tier": "ALL",
            "gpl_sum": None,
            "total_line_9299": None,
            "discrepancy": None,
            "detail": detail,
        }])
        return _flag(skip_row, "R04", "GPL <-> Total sheet reconciliation", "error")

    gpl_sum = (
        gpl.groupby(["MunID", "Municipality"], dropna=False)[
            ["LT/ST Taxes", "UT Taxes", "EDUC Taxes", "TOTAL Taxes"]
        ]
        .sum(min_count=1)
        .fillna(0)
        .reset_index()
    )

    tot = total[total["Line"] == 9299][
        ["MunID", "Municipality", "LT/ST Taxes", "UT Taxes", "EDUC Taxes", "TOTAL Taxes"]
    ].copy()
    tot = tot.fillna(0)

    merged = gpl_sum.merge(
        tot, on=["MunID", "Municipality"], how="outer", suffixes=("_gpl", "_tot")
    ).fillna(0)

    flags_rows = []
    for tier in ["LT/ST Taxes", "UT Taxes", "EDUC Taxes", "TOTAL Taxes"]:
        diff = merged[f"{tier}_gpl"] - merged[f"{tier}_tot"]
        mask = diff.abs() > 1  # allow $1 rounding
        if mask.any():
            sub = merged[mask].copy()
            sub["tier"] = tier
            sub["gpl_sum"] = sub[f"{tier}_gpl"]
            sub["total_line_9299"] = sub[f"{tier}_tot"]
            sub["discrepancy"] = diff[mask]
            sub["detail"] = (
                tier
                + ": GPL sum $"
                + sub["gpl_sum"].round(0).astype(int).astype(str)
                + " vs Total line 9299 $"
                + sub["total_line_9299"].round(0).astype(int).astype(str)
            )
            flags_rows.append(sub[["MunID", "Municipality", "tier", "gpl_sum",
                                   "total_line_9299", "discrepancy", "detail"]])

    if not flags_rows:
        empty = pd.DataFrame(columns=["MunID", "Municipality", "tier",
                                      "gpl_sum", "total_line_9299",
                                      "discrepancy", "detail"])
        return _flag(empty, "R04", "GPL <-> Total sheet reconciliation", "error")

    result = pd.concat(flags_rows, ignore_index=True)
    return _flag(result, "R04", "GPL <-> Total sheet reconciliation", "error")


@_rule_meta("R05", "Phase-In <= CVA", "error")
def rule_05_phase_in_vs_cva(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Rule 05: Phase-In Taxable Assessment must not exceed CVA Assessment.

    In Ontario's assessment system, Current Value Assessment (CVA) is
    the full assessed value of a property and Phase-In Taxable
    Assessment is the portion currently being taxed after any phase-in
    adjustment. The phase-in mechanism can only reduce or leave equal,
    never increase. Any row where Phase-In > CVA by more than a $1
    rounding tolerance is a data error.
    """
    gpl = sheets["gpl"]
    work = gpl.copy()
    # Rule only applies when both values are present and non-zero
    mask = (
        work["CVA Assessment"].notna()
        & work["Phase-In Taxable Assessment"].notna()
        & (work["CVA Assessment"] > 0)
    )
    candidates = work[mask].copy()
    diff = candidates["Phase-In Taxable Assessment"] - candidates["CVA Assessment"]
    bad = candidates[diff > 1].copy()
    bad["excess"] = (
        bad["Phase-In Taxable Assessment"] - bad["CVA Assessment"]
    ).round(0)
    bad["detail"] = (
        "Phase-In assessment exceeds CVA by $"
        + bad["excess"].astype(int).astype(str)
    )
    cols = ["MunID", "Municipality", "Property Class", "RTC/RTQ",
            "CVA Assessment", "Phase-In Taxable Assessment", "excess", "detail"]
    return _flag(bad[cols], "R05", "Phase-In <= CVA", "error")


@_rule_meta("R06", "Within-municipality rate consistency", "warning")
def rule_06_within_muni_rate_consistency(
    sheets: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Rule 06: Within-municipality tax rate consistency (warning).

    For each municipality and each non-residential property class, the
    LT/ST tax rate should approximately equal the residential LT/ST
    tax rate multiplied by that class's tax ratio.

    LIMITATION: Ontario allows several legitimate deviations from this
    identity that this rule does not yet model:
      - Graduated tax rates for commercial and industrial properties
        (O. Reg. 73/03) where a municipality sets different rates for
        different value bands within the same class.
      - Optional reduced rates for small business properties under
        Bill 62 / O. Reg. 330/21.
      - Transitional tax ratios during class reform.

    Because of these known exceptions, the rule is marked as a warning
    rather than an error. Flagged rows should be reviewed against the
    municipality's by-laws and regulations, not treated as definitive
    data entry errors.

    The rule uses the residential RT "Full Occupied" rate as the
    anchor and compares within (MunID, Levy Area) so that
    municipalities split into multiple levy areas are handled
    correctly.
    """
    gpl = sheets["gpl"]
    work = gpl.copy()
    work = work[work["Phase-In Taxable Assessment"].fillna(0) > 0]
    work = work[work["LT/ST Tax Rate"].fillna(0) > 0]
    work = work[work["Tax Ratio"].fillna(0) > 0]

    # Find residential RT (main class) base rate per (MunID, Levy Area).
    # Filter to "Full Occupied" descriptions to get the anchor rate; this
    # avoids anchoring on sub-classes like "Excess Land" that have
    # reduced rates.
    base_mask = (
        (work["Property Class"] == "Residential")
        & (work["RTC/RTQ"] == "RT")
        & (work["Tax Rate Description"].str.contains("Full Occupied", na=False))
    )
    base = (
        work[base_mask]
        .groupby(["MunID", "Levy Area"], dropna=False)["LT/ST Tax Rate"]
        .first()
        .reset_index()
        .rename(columns={"LT/ST Tax Rate": "base_lt_rate"})
    )

    merged = work.merge(base, on=["MunID", "Levy Area"], how="left")
    merged = merged[merged["base_lt_rate"].notna()]

    # Only check rows with "Full Occupied" description so we compare
    # like-for-like; sub-class rates (excess land, vacant land) follow
    # different multipliers.
    merged = merged[
        merged["Tax Rate Description"].str.contains("Full Occupied", na=False)
    ]

    expected = merged["base_lt_rate"] * merged["Tax Ratio"]
    actual = merged["LT/ST Tax Rate"]
    # Relative tolerance: 0.5% absorbs rounding in the published rates
    rel_diff = (actual - expected).abs() / expected.replace(0, np.nan)
    merged = merged.assign(expected_rate=expected, rel_diff=rel_diff)
    bad = merged[merged["rel_diff"] > 0.005].copy()
    bad["detail"] = (
        bad["Property Class"].astype(str)
        + " LT rate "
        + bad["LT/ST Tax Rate"].round(6).astype(str)
        + " does not equal residential base "
        + bad["base_lt_rate"].round(6).astype(str)
        + " * tax ratio "
        + bad["Tax Ratio"].round(4).astype(str)
        + " = "
        + bad["expected_rate"].round(6).astype(str)
    )
    cols = ["MunID", "Municipality", "Property Class", "Tax Ratio",
            "base_lt_rate", "LT/ST Tax Rate", "expected_rate", "detail"]
    return _flag(bad[cols], "R06", "Within-municipality rate consistency", "warning")


@_rule_meta("R07", "Property class coverage", "warning")
def rule_07_property_class_coverage(
    sheets: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """
    Rule 07: Property class coverage outliers.

    For each municipality, count the number of distinct property
    classes reported (considering only rows with positive taxable
    assessment). Flag municipalities whose count is less than half the
    median count for their tier. Very small counts may indicate missing
    schedules or incomplete reporting.

    This is a warning, not an error: some small rural townships
    legitimately have only residential and farmland, so the flag means
    "worth a look", not "definitely wrong".
    """
    gpl = sheets["gpl"]
    active = gpl[gpl["Phase-In Taxable Assessment"].fillna(0) > 0]

    counts = (
        active.groupby(["MunID", "Municipality", "Tier"], dropna=False)[
            "Property Class"
        ]
        .nunique()
        .reset_index()
        .rename(columns={"Property Class": "n_classes"})
    )
    tier_median = counts.groupby("Tier")["n_classes"].median().to_dict()
    counts["tier_median"] = counts["Tier"].map(tier_median)
    counts["threshold"] = counts["tier_median"] * 0.5
    bad = counts[counts["n_classes"] < counts["threshold"]].copy()
    bad["detail"] = (
        "Only "
        + bad["n_classes"].astype(str)
        + " property classes reported (tier "
        + bad["Tier"].astype(str)
        + " median is "
        + bad["tier_median"].astype(int).astype(str)
        + ")"
    )
    cols = ["MunID", "Municipality", "Tier", "n_classes", "tier_median", "detail"]
    return _flag(bad[cols], "R07", "Property class coverage", "warning")


ALL_RULES = [
    rule_01_template_arithmetic,
    rule_02_residential_tax_ratio,
    rule_03_residential_educ_rate,
    rule_04_gpl_total_reconciliation,
    rule_05_phase_in_vs_cva,
    rule_06_within_muni_rate_consistency,
    rule_07_property_class_coverage,
]


def run_all(sheets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Run every rule and return results keyed by rule_id."""
    return {rule.__name__: rule(sheets) for rule in ALL_RULES}
