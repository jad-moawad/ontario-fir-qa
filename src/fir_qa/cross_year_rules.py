"""
Cross-year QA rules for Ontario FIR Schedule 22 data.

Each rule here compares data across multiple years and therefore requires
a dict of {year: sheets} rather than a single year's sheets dict. The
function signatures, decorator, and return format are intentionally
parallel to rules.py so the engine can dispatch to either module cleanly.

Cross-year rules are run via:

    python -m fir_qa.engine cross_year data/raw/ reports/cross_year
"""

from __future__ import annotations

import pandas as pd


# Year-over-year total levy change threshold (relative, symmetric).
# Calibrated against the empirical distribution of 2019-2023 consecutive-year
# percent changes: p95 ranges from 4.4% (2020->2021, the COVID-suppressed year)
# to 10.2% (2022->2023). At 25%, the rule catches only genuinely anomalous
# moves without generating noise from ordinary assessment-cycle growth or the
# province-wide inflation-driven rate increases seen in 2022->2023.
YOY_LEVY_CHANGE_THRESHOLD = 0.25


def _cy_rule_meta(rule_id: str, rule_name: str, severity: str):
    """Decorator that attaches rule metadata to a cross-year rule function."""
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


@_cy_rule_meta("R08", "Year-over-year total levy change", "warning")
def rule_08_yoy_levy_change(
    sheets_by_year: dict[int, dict[str, pd.DataFrame]],
    threshold: float = YOY_LEVY_CHANGE_THRESHOLD,
) -> pd.DataFrame:
    """
    Rule 08: Flag municipalities with an unusually large year-over-year
    change in total property tax levy.

    For each consecutive pair of years present in sheets_by_year, computes
    the percent change in TOTAL Taxes per municipality. Flags any
    municipality whose absolute percent change exceeds the threshold
    (default 25%).

    METRIC: Sum of TOTAL Taxes from the GPL sheet per municipality. This is
    used rather than an effective-rate metric (levy / Phase-In) because
    TOTAL Taxes is internally consistent even when the CVA Assessment column
    is defective, as found in Chatham-Kent M 2019 where CVA was erroneous
    but TOTAL Taxes matched Phase-In at the correct rates. The GPL sheet is
    used directly, avoiding any dependency on the Total sheet, which has a
    known MunID column corruption in the 2022 file.

    GRANULARITY: Per municipality total levy. Class-level year-over-year
    changes belong in Rule 09, which operates at (municipality, property
    class) granularity.

    MISSING MUNICIPALITIES: Municipalities present in one year but absent
    in the adjacent year are silently skipped here. Rule 10 handles
    municipality coverage continuity as a separate concern.

    SEVERITY: Warning (not error). Large levy changes have legitimate
    causes including new major development, annexed territory, or industrial
    closure, all of which require human review before concluding there is a
    data error.
    """
    years = sorted(sheets_by_year.keys())
    cols = ["MunID", "Municipality", "year_from", "year_to",
            "levy_from", "levy_to", "pct_change", "detail"]

    if len(years) < 2:
        return _flag(pd.DataFrame(columns=cols),
                     "R08", "Year-over-year total levy change", "warning")

    # Build per-municipality TOTAL levy sum for each year.
    levy_by_year: dict[int, pd.Series] = {}
    for year in years:
        gpl = sheets_by_year[year]["gpl"]
        levy_by_year[year] = (
            gpl.groupby("MunID")["TOTAL Taxes"].sum()
        )

    # Build municipality name lookup. Later years take precedence so that
    # names reflect current nomenclature rather than potentially stale older
    # names for municipalities that were renamed.
    mun_names: dict[int, str] = {}
    for year in years:
        gpl = sheets_by_year[year]["gpl"]
        for mid, name in gpl.groupby("MunID")["Municipality"].first().items():
            mun_names[mid] = name

    flag_rows = []
    for y1, y2 in zip(years[:-1], years[1:]):
        s1 = levy_by_year[y1]
        s2 = levy_by_year[y2]
        common = s1.index.intersection(s2.index)
        # Restrict to municipalities with a positive levy in both years.
        # Zero-levy rows in either year are meaningless as a denominator
        # and would produce infinite or undefined percent changes.
        both_positive = common[(s1[common] > 0) & (s2[common] > 0)]
        pct = (s2[both_positive] - s1[both_positive]) / s1[both_positive]
        flagged_ids = both_positive[pct.abs() > threshold]

        for mid in flagged_ids:
            lev1 = float(s1[mid])
            lev2 = float(s2[mid])
            p = float(pct[mid]) * 100
            sign = "+" if p >= 0 else ""
            flag_rows.append({
                "MunID": mid,
                "Municipality": mun_names.get(mid, str(mid)),
                "year_from": y1,
                "year_to": y2,
                "levy_from": round(lev1, 0),
                "levy_to": round(lev2, 0),
                "pct_change": round(p, 2),
                "detail": (
                    f"TOTAL levy changed by {sign}{p:.1f}% from {y1} to {y2} "
                    f"(${lev1:,.0f} to ${lev2:,.0f})"
                ),
            })

    if not flag_rows:
        return _flag(pd.DataFrame(columns=cols),
                     "R08", "Year-over-year total levy change", "warning")

    result = pd.DataFrame(flag_rows)[cols]
    return _flag(result, "R08", "Year-over-year total levy change", "warning")


ALL_CROSS_YEAR_RULES = [rule_08_yoy_levy_change]


def run_all_cross_year(
    sheets_by_year: dict[int, dict[str, pd.DataFrame]],
) -> dict[str, pd.DataFrame]:
    """Run every cross-year rule and return results keyed by function name."""
    return {rule.__name__: rule(sheets_by_year) for rule in ALL_CROSS_YEAR_RULES}
