"""
Cross-schedule QA rules for Ontario FIR Schedule 22 and Schedule 26 data.

These rules compare data across multiple schedules within the same year and
therefore require both a Schedule 22 sheets dict and a Schedule 26 path (or
its loaded sheets). The function signatures use a dedicated decorator parallel
to rules.py and cross_year_rules.py.

Cross-schedule rules are run via:

    python -m fir_qa.engine cross_schedule data/raw/ reports/cross_schedule

The runner discovers schedule_22.xlsx and schedule_26.xlsx pairs, loads them,
and dispatches to these rules.
"""

from __future__ import annotations

import pandas as pd


def _cs_rule_meta(rule_id: str, rule_name: str, severity: str):
    """Decorator that attaches rule metadata to a cross-schedule rule function."""
    def wrap(func):
        func.rule_id = rule_id
        func.rule_name = rule_name
        func.severity = severity
        return func
    return wrap


def _flag(df: pd.DataFrame, rule_id: str, rule_name: str,
          severity: str) -> pd.DataFrame:
    """Attach rule metadata columns to a flagged-row DataFrame."""
    out = df.copy()
    out.insert(0, "rule_id", rule_id)
    out.insert(1, "rule_name", rule_name)
    out.insert(2, "severity", severity)
    return out


@_cs_rule_meta("R11", "Schedule 26 vs S22 grand total", "error")
def rule_11_s26_vs_spc_grand_total(
    sheets_22: dict[str, pd.DataFrame],
    sheets_26: dict[str, pd.DataFrame],
    year: int,
) -> pd.DataFrame:
    """
    Rule 11: Schedule 26-1 line 9199 (TOTAL before Adj.) must match SPC
    line 9990 (grand total including SRA adjustments) per municipality.

    ARCHITECTURE: Schedule 26 and Schedule 22 are separate FIR filings
    submitted through different mechanisms. Schedule 26 is a taxation and
    PILT summary collected by the Ministry, while Schedule 22 is the
    detailed levy submission. When a municipality's S26-1 total disagrees
    with its S22 SPC total, one of the two filings contains an error.

    COLUMN MAPPING: In Schedule 26-1, columns are coded as "26 xxxx NN":
      - col 03 = TOTAL Taxes
      - col 04 = LT/ST Taxes
      - col 05 = UT Taxes
      - col 06 = EDUC Taxes
    The S22 SPC sheet uses plain column names (TOTAL Taxes, LT/ST Taxes, etc).

    LINE SELECTION: S26-1 line 9199 ("TOTAL before Adj.") is chosen as the
    reconciliation target because it matches SPC line 9990 across all clean
    years. SPC line 9910 does NOT work: it excludes SRA surcharges (8xxx
    lines) that appear in SPC line 9990 but not in 9910. Verified for 2019,
    2020, 2021, and 2023 (zero discrepancies at $2 tolerance). The 2022 SPC
    sheet has 138 MunIDs with corrupted names (same structural defect as the
    2022 Total sheet), which this rule detects and skips.

    CORRUPTION DETECTION: If the SPC sheet has any MunID mapping to multiple
    municipality names, the rule is skipped for that year with a diagnostic
    row. This is the same zero-tolerance approach used in R04.

    SEVERITY: Error. The S26 submission is legally separate from S22 and a
    discrepancy cannot be explained by rounding alone.
    """
    spc = sheets_22["spc"]
    s26_1 = sheets_26.get("s26_1")

    cols = ["MunID", "Municipality", "tier", "s26_value", "spc_value",
            "discrepancy", "detail"]
    empty = pd.DataFrame(columns=cols)

    if s26_1 is None or s26_1.empty:
        skip_row = pd.DataFrame([{
            "MunID": None,
            "Municipality": None,
            "tier": "ALL",
            "s26_value": None,
            "spc_value": None,
            "discrepancy": None,
            "detail": f"R11 SKIPPED: Schedule 26 data not available for {year}",
        }])
        return _flag(skip_row, "R11", "Schedule 26 vs S22 grand total", "error")

    # Corruption pre-check: SPC MunID-to-name consistency
    if "Municipality" in spc.columns:
        mun_check = spc.groupby("MunID")["Municipality"].nunique()
        corrupted = mun_check[mun_check > 1]
        if len(corrupted) > 0:
            gpl = sheets_22.get("gpl", pd.DataFrame())
            gpl_id_name = gpl.groupby("MunID")["Municipality"].first() if len(gpl) > 0 else pd.Series(dtype=str)
            sample_parts = []
            for mid in list(corrupted.index[:3]):
                gpl_name = gpl_id_name.get(mid, "unknown")
                sample_parts.append(f"MunID {mid}: GPL={gpl_name!r}")
            detail = (
                f"R11 SKIPPED: SPC sheet MunID column appears corrupted "
                f"({len(corrupted)} MunIDs map to multiple municipality names). "
                "Schedule 26 data is clean for this year. Sample: "
                + "; ".join(sample_parts)
            )
            skip_row = pd.DataFrame([{
                "MunID": None,
                "Municipality": None,
                "tier": "ALL",
                "s26_value": None,
                "spc_value": None,
                "discrepancy": None,
                "detail": detail,
            }])
            return _flag(skip_row, "R11", "Schedule 26 vs S22 grand total", "error")

    # S26-1 line 9199 per municipality
    s26_9199 = s26_1[s26_1["Line"] == 9199].copy()
    if s26_9199.empty:
        skip_row = pd.DataFrame([{
            "MunID": None, "Municipality": None, "tier": "ALL",
            "s26_value": None, "spc_value": None, "discrepancy": None,
            "detail": f"R11 SKIPPED: line 9199 not found in Schedule 26-1 for {year}",
        }])
        return _flag(skip_row, "R11", "Schedule 26 vs S22 grand total", "error")

    # SPC line 9990 per municipality
    spc_9990 = spc[spc["Line"] == 9990].copy()
    if spc_9990.empty:
        skip_row = pd.DataFrame([{
            "MunID": None, "Municipality": None, "tier": "ALL",
            "s26_value": None, "spc_value": None, "discrepancy": None,
            "detail": f"R11 SKIPPED: line 9990 not found in SPC sheet for {year}",
        }])
        return _flag(skip_row, "R11", "Schedule 26 vs S22 grand total", "error")

    # Column mapping for S26-1 tiers
    tier_map = [
        ("26 xxxx 03", "TOTAL Taxes", "TOTAL"),
        ("26 xxxx 04", "LT/ST Taxes", "LT/ST"),
        ("26 xxxx 05", "UT Taxes", "UT"),
        ("26 xxxx 06", "EDUC Taxes", "EDUC"),
    ]

    s26_idx = s26_9199.set_index("MunID")
    spc_idx = spc_9990.set_index("MunID")
    common = s26_idx.index.intersection(spc_idx.index)

    mun_names = s26_idx.reindex(common)["Municipality"]

    flag_rows = []
    # Tolerance: $2 per tier (absorbs rounding propagation across multiple tiers)
    tol = 2

    for s26_col, spc_col, tier_label in tier_map:
        if s26_col not in s26_idx.columns or spc_col not in spc_idx.columns:
            continue
        s26_vals = pd.to_numeric(s26_idx.reindex(common)[s26_col], errors="coerce").fillna(0)
        spc_vals = pd.to_numeric(spc_idx.reindex(common)[spc_col], errors="coerce").fillna(0)
        diffs = (s26_vals - spc_vals).abs()
        flagged_ids = common[diffs > tol]

        for mid in flagged_ids:
            s26_val = float(s26_vals[mid])
            spc_val = float(spc_vals[mid])
            disc = s26_val - spc_val
            flag_rows.append({
                "MunID": mid,
                "Municipality": mun_names.get(mid, str(mid)),
                "tier": tier_label,
                "s26_value": round(s26_val, 0),
                "spc_value": round(spc_val, 0),
                "discrepancy": round(disc, 0),
                "detail": (
                    f"{tier_label} taxes: S26 reports ${s26_val:,.0f}, "
                    f"SPC reports ${spc_val:,.0f} "
                    f"(discrepancy ${abs(disc):,.0f})"
                ),
            })

    if not flag_rows:
        return _flag(empty, "R11", "Schedule 26 vs S22 grand total", "error")

    result = pd.DataFrame(flag_rows)[cols]
    return _flag(result, "R11", "Schedule 26 vs S22 grand total", "error")


@_cs_rule_meta("R12", "SRA-LT vs Total sheet line 9499", "error")
def rule_12_sra_lt_reconciliation(
    sheets_22: dict[str, pd.DataFrame],
    year: int,
) -> pd.DataFrame:
    """
    Rule 12: SRA-LT row sums must match Total sheet line 9499.

    Line 9499 of the Total sheet is the post-aggregation total for all
    Special Rate Area (lower-tier) levies. It plays the same role for
    SRA-LT that line 9299 plays for the GPL: a single post-aggregation
    row per municipality that the SRA-LT row sums should reconcile to.

    The Total sheet MunID corruption that affects 2022 is detected here
    using the same zero-tolerance pre-check as R04 and R11.

    SEVERITY: Error. SRA-LT levies are legislated special charges for
    specific service areas (e.g. urban service areas, water service
    areas). A reconciliation failure here means the summary total
    misrepresents what was actually levied.
    """
    sra_lt = sheets_22["sra_lt"]
    total = sheets_22["total"]

    cols = ["MunID", "Municipality", "tier", "sra_sum", "total_line_9499",
            "discrepancy", "detail"]
    empty = pd.DataFrame(columns=cols)

    # Corruption pre-check on Total sheet
    if "Municipality" in total.columns:
        gpl = sheets_22.get("gpl", pd.DataFrame())
        if len(gpl) > 0:
            gpl_id_name = gpl.groupby("MunID")["Municipality"].first()
            total_id_name = total.groupby("MunID")["Municipality"].first()
            common_ids = gpl_id_name.index.intersection(total_id_name.index)
            mismatches = common_ids[gpl_id_name[common_ids] != total_id_name[common_ids]]
            if len(mismatches) > 0:
                skip_row = pd.DataFrame([{
                    "MunID": None, "Municipality": None, "tier": "ALL",
                    "sra_sum": None, "total_line_9499": None, "discrepancy": None,
                    "detail": (
                        f"R12 SKIPPED: Total sheet MunID column corrupted "
                        f"({len(mismatches)} MunIDs have mismatched names) for {year}"
                    ),
                }])
                return _flag(skip_row, "R12", "SRA-LT vs Total sheet line 9499", "error")

    # SRA-LT sums per municipality
    tax_cols = ["LT/ST Taxes", "UT Taxes", "EDUC Taxes", "TOTAL Taxes"]
    existing_tax_cols = [c for c in tax_cols if c in sra_lt.columns]
    if not existing_tax_cols:
        return _flag(empty, "R12", "SRA-LT vs Total sheet line 9499", "error")

    sra_sums = (
        sra_lt.groupby(["MunID", "Municipality"], dropna=False)[existing_tax_cols]
        .sum(min_count=1)
        .fillna(0)
        .reset_index()
    )

    # Total sheet line 9499
    line_9499 = total[total["Line"] == 9499][
        ["MunID", "Municipality"] + [c for c in tax_cols if c in total.columns]
    ].copy().fillna(0)

    if line_9499.empty:
        return _flag(empty, "R12", "SRA-LT vs Total sheet line 9499", "error")

    merged = sra_sums.merge(
        line_9499, on="MunID", how="outer", suffixes=("_sra", "_9499")
    ).fillna(0)

    flag_rows = []
    for tier in existing_tax_cols:
        if f"{tier}_sra" not in merged.columns or f"{tier}_9499" not in merged.columns:
            continue
        diff = merged[f"{tier}_sra"] - merged[f"{tier}_9499"]
        mask = diff.abs() > 1
        if mask.any():
            sub = merged[mask].copy()
            mun_col = "Municipality_sra" if "Municipality_sra" in sub.columns else "Municipality"
            for _, row in sub.iterrows():
                mun_name = row.get(mun_col, str(row["MunID"]))
                flag_rows.append({
                    "MunID": row["MunID"],
                    "Municipality": mun_name,
                    "tier": tier,
                    "sra_sum": round(float(row[f"{tier}_sra"]), 0),
                    "total_line_9499": round(float(row[f"{tier}_9499"]), 0),
                    "discrepancy": round(float(diff.loc[row.name]), 0),
                    "detail": (
                        f"{tier}: SRA-LT sum ${row[f'{tier}_sra']:,.0f} "
                        f"vs Total line 9499 ${row[f'{tier}_9499']:,.0f}"
                    ),
                })

    if not flag_rows:
        return _flag(empty, "R12", "SRA-LT vs Total sheet line 9499", "error")

    result = pd.DataFrame(flag_rows)[cols]
    return _flag(result, "R12", "SRA-LT vs Total sheet line 9499", "error")


@_cs_rule_meta("R13", "Grand total chain reconciliation", "error")
def rule_13_grand_total_chain(
    sheets_22: dict[str, pd.DataFrame],
    year: int,
) -> pd.DataFrame:
    """
    Rule 13: Grand total chain reconciliation within Schedule 22.

    Checks that the following identity holds per municipality:

        Total line 9299 (GPL roll-up)
      + Total line 9499 (SRA-LT roll-up)
      + Total line 9699 (SRA-UT roll-up)
      + SPC line 9799 (special purpose charges subtotal)
      + SPC line 7010 (PIL adjustment, when present)
      = SPC line 9910 (grand total before SRA surcharges)

    SPC line 7010 is included because it represents PIL adjustments that
    are part of the grand total but are not rolled into line 9799. Verified
    by inspecting York Region 2019, where omitting line 7010 produced a
    $3.8M discrepancy that line 7010 exactly explained. After including 7010,
    the rule produces zero flags across all four clean years (2019, 2020,
    2021, 2023).

    The 2022 Total sheet MunID corruption is detected and skipped, as in R04
    and R12.

    SEVERITY: Error. The grand total chain is the highest-level integrity
    check within Schedule 22. A failure here means the schedule's own
    internal arithmetic does not close, which is independent of any external
    comparison.
    """
    spc = sheets_22["spc"]
    total = sheets_22["total"]

    cols = ["MunID", "Municipality", "computed_total", "reported_9910",
            "discrepancy", "detail"]
    empty = pd.DataFrame(columns=cols)

    # Corruption pre-check: Total sheet MunID consistency
    gpl = sheets_22.get("gpl", pd.DataFrame())
    if "Municipality" in total.columns and len(gpl) > 0:
        gpl_id_name = gpl.groupby("MunID")["Municipality"].first()
        total_id_name = total.groupby("MunID")["Municipality"].first()
        common_ids = gpl_id_name.index.intersection(total_id_name.index)
        mismatches = common_ids[gpl_id_name[common_ids] != total_id_name[common_ids]]
        if len(mismatches) > 0:
            skip_row = pd.DataFrame([{
                "MunID": None, "Municipality": None,
                "computed_total": None, "reported_9910": None,
                "discrepancy": None,
                "detail": (
                    f"R13 SKIPPED: Total sheet MunID column corrupted "
                    f"({len(mismatches)} MunIDs have mismatched names) for {year}"
                ),
            }])
            return _flag(skip_row, "R13", "Grand total chain reconciliation", "error")

    # Also check SPC for corruption
    if "Municipality" in spc.columns:
        spc_mun_check = spc.groupby("MunID")["Municipality"].nunique()
        spc_corrupted = spc_mun_check[spc_mun_check > 1]
        if len(spc_corrupted) > 0:
            skip_row = pd.DataFrame([{
                "MunID": None, "Municipality": None,
                "computed_total": None, "reported_9910": None,
                "discrepancy": None,
                "detail": (
                    f"R13 SKIPPED: SPC sheet MunID column corrupted "
                    f"({len(spc_corrupted)} MunIDs have multiple names) for {year}"
                ),
            }])
            return _flag(skip_row, "R13", "Grand total chain reconciliation", "error")

    for df in [total, spc]:
        if "TOTAL Taxes" in df.columns:
            df["TOTAL Taxes"] = pd.to_numeric(df["TOTAL Taxes"], errors="coerce")

    # Pull each component: use TOTAL Taxes column only for the chain check
    def get_line(df: pd.DataFrame, line_num: int) -> pd.Series:
        sub = df[df["Line"] == line_num].set_index("MunID")
        col = "TOTAL Taxes"
        if col in sub.columns:
            return pd.to_numeric(sub[col], errors="coerce").fillna(0)
        return pd.Series(dtype=float)

    t9299 = get_line(total, 9299)
    t9499 = get_line(total, 9499)
    t9699 = get_line(total, 9699)
    spc9799 = get_line(spc, 9799)
    spc7010 = get_line(spc, 7010)
    spc9910 = get_line(spc, 9910)

    if t9299.empty or spc9910.empty:
        return _flag(empty, "R13", "Grand total chain reconciliation", "error")

    all_munis = t9299.index
    computed = pd.Series(0.0, index=all_munis)
    for component in [t9299, t9499, t9699, spc9799, spc7010]:
        if component.empty:
            continue
        common = all_munis.intersection(component.index)
        computed[common] += component[common]

    reported = spc9910.reindex(all_munis).fillna(0)
    diffs = (computed - reported).abs()

    # Municipality name lookup from GPL or Total
    if len(gpl) > 0:
        mun_names = gpl.groupby("MunID")["Municipality"].first()
    elif "Municipality" in total.columns:
        mun_names = total.groupby("MunID")["Municipality"].first()
    else:
        mun_names = pd.Series(dtype=str)

    flagged_ids = all_munis[diffs > 2]
    if len(flagged_ids) == 0:
        return _flag(empty, "R13", "Grand total chain reconciliation", "error")

    flag_rows = []
    for mid in flagged_ids:
        comp = float(computed[mid])
        rep = float(reported[mid])
        disc = comp - rep
        flag_rows.append({
            "MunID": mid,
            "Municipality": mun_names.get(mid, str(mid)),
            "computed_total": round(comp, 0),
            "reported_9910": round(rep, 0),
            "discrepancy": round(disc, 0),
            "detail": (
                f"Computed grand total ${comp:,.0f} vs SPC line 9910 "
                f"${rep:,.0f} (discrepancy ${abs(disc):,.0f})"
            ),
        })

    result = pd.DataFrame(flag_rows)[cols]
    return _flag(result, "R13", "Grand total chain reconciliation", "error")


ALL_CROSS_SCHEDULE_RULES = [
    rule_11_s26_vs_spc_grand_total,
    rule_12_sra_lt_reconciliation,
    rule_13_grand_total_chain,
]


def run_all_cross_schedule(
    sheets_22: dict[str, pd.DataFrame],
    sheets_26: dict[str, pd.DataFrame],
    year: int,
) -> dict[str, pd.DataFrame]:
    """Run every cross-schedule rule and return results keyed by function name."""
    results = {}
    results[rule_11_s26_vs_spc_grand_total.__name__] = rule_11_s26_vs_spc_grand_total(
        sheets_22, sheets_26, year
    )
    results[rule_12_sra_lt_reconciliation.__name__] = rule_12_sra_lt_reconciliation(
        sheets_22, year
    )
    results[rule_13_grand_total_chain.__name__] = rule_13_grand_total_chain(
        sheets_22, year
    )
    return results
