# QA Rules Reference

This file documents each implemented rule in detail: what it checks, why it
is designed the way it is, what it currently flags, and what to watch out
for when modifying it.

## Rule metadata system

Every rule function is decorated with `@_rule_meta(rule_id, rule_name,
severity)` which attaches these as function attributes. This allows the
summary builder in engine.py to show rule names even when the rule returned
zero flags. When adding a new rule, always apply the decorator.

```python
@_rule_meta("R08", "Year-over-year levy change", "warning")
def rule_08_yoy_levy_change(sheets_by_year):
    ...
```

All rules return a pandas DataFrame with three metadata columns prepended
(rule_id, rule_name, severity), followed by rule-specific columns, and
ending with a `detail` column that contains a plain-English explanation
suitable for display in the dashboard.

## Rule 01: Template arithmetic integrity (error)

**What it checks**: For each GPL row with positive Phase-In Taxable
Assessment, verifies that Phase-In times each tier rate equals the reported
tax for that tier, within tolerance. Also checks that TOTAL rate equals the
sum of LT/ST, UT, and EDUC rates.

**Tolerance**: $1 absolute for LT/ST, UT, EDUC; $2 absolute for TOTAL (to
absorb rounding propagation when individual tiers are rounded before being
summed); or 0.5% relative, whichever is larger. Rate sum tolerance is 1e-7.

**Why the $2 TOTAL tolerance**: the first iteration used $1 for TOTAL and
flagged 7 rows. Investigation showed these were rounding artifacts: the
template computes each tier as `round(assessment * rate)` and then TOTAL as
`sum of rounded tiers`, while our check was `assessment * TOTAL_rate rounded`,
which can differ by $1 per tier summed. Widening to $2 absorbs this.

**Current status**: 0 flags on 2023 data. The FIR Excel template enforces
this via cell formulas, so healthy files flag zero rows. The rule exists as
a canary for file corruption or manual cell overrides.

**Modification warnings**: do not tighten the tolerance. If you think
something should flag here, you are probably looking at a rounding artifact.

## Rule 02: Residential tax ratio = 1.00 (error)

**What it checks**: Every row with Property Class "Residential" must have
Tax Ratio exactly equal to 1.0.

**Rationale**: Ontario's tax ratio system makes residential the reference
class with ratio 1.00 by definition of law (Municipal Act). Any residential
row with a different ratio is a data entry error.

**Current status**: 0 flags on 2023 data.

**Modification warnings**: the residential ratio is truly fixed; this rule
should never need exceptions. If it starts flagging things, investigate the
specific rows, do not loosen the rule.

## Rule 03: Standard residential education rate (error)

**What it checks**: Residential rows where Tier is LT or ST, RTC/RTQ is RT
(main class, not sub-classes), and Phase-In assessment is positive must
have EDUC tax rate exactly equal to the provincial standard (0.00153 for
2023).

**The filter is the rule**: this is the most important rule in the project
from a "demonstrating domain awareness" standpoint. A naive version without
the RTC/RTQ and Tier filters would generate 138 false positives out of 710
residential rows. The false positives break down as:

- 86 rows: Upper-tier municipalities with NaN EDUC rate (UT don't levy
  education taxes directly, this is structurally correct)
- 52 rows: R1 sub-class (Farm Awaiting Development Phase I) which has its
  own rate set by regulation, not the standard residential rate

With the proper filters, the rule generates zero false positives and still
catches real errors (any legitimately misreported standard residential rate
will be flagged).

**Current status**: 0 flags on 2023 data.

**Modification warnings**: The standard rate 0.00153 is hardcoded as
`STD_RESIDENTIAL_EDUC_RATE_2023`. When extending to multiple years, replace
with a year-keyed lookup dict. The rate changes over time per O. Reg.
400/98.

## Rule 04: GPL sum reconciles to Total sheet line 9299 (error)

**What it checks**: For each municipality, the sum of LT/ST, UT, EDUC, and
TOTAL taxes across all GPL rows equals the value on Total sheet line 9299
for that municipality, within $1 tolerance per tier.

**Why line 9299 and not 9201**: Line 9201 is the per-levy-area GPL roll-up,
and municipalities split into multiple levy areas have multiple 9201 rows.
Frontenac Islands (MunID 10002) has one 9201 row for Howe Island and
another for Wolfe Island, which together sum to the GPL total. Line 9299
is the post-aggregation roll-up with one row per municipality, which is
what we want to reconcile against.

**Current status**: 0 flags on 2023 data, after the fix from line 9201 to
line 9299.

**Modification warnings**: When extending to SRA and SPC reconciliation,
use the analogous post-aggregation lines: 9499 for SRA-LT, 9699 for
SRA-UT, 9910 for the grand total.

## Rule 05: Phase-In <= CVA (error)

**What it checks**: Phase-In Taxable Assessment must not exceed CVA
Assessment by more than $1. The phase-in mechanism in Ontario only reduces
assessments (when they go up, the increase is phased in over 4 years;
decreases take effect immediately), so Phase-In should always be at most
equal to CVA.

**Current status**: 9 flags across 4 municipalities on 2023 data. Notable
finding: Brant County Commercial Vacant Land (CX) shows CVA of $23.2M but
Phase-In of $36.1M, an excess of $12.9M. Brant County alone accounts for
5 of the 9 flags across different sub-classes. The other flagged
municipalities are Markstay-Warren M, Ottawa C, and one other.

**Interpretation**: The large excesses (millions of dollars) are almost
certainly real data errors, caused by mid-year reclassifications,
supplementary assessments not reflected in CVA, or data entry errors.
Smaller excesses could be structural. A future refinement is to classify
flags by magnitude.

**Modification warnings**: Do not relax the tolerance beyond $1. The whole
point of the rule is to find real anomalies.

## Rule 06: Within-municipality rate consistency (warning)

**What it checks**: For each (municipality, levy area), the LT/ST tax rate
of a non-residential "Full Occupied" row should approximately equal the
residential LT/ST "Full Occupied" rate multiplied by that class's tax
ratio. Tolerance is 0.5% relative difference.

**Why warning not error**: Ontario allows several legitimate deviations
from this multiplicative identity which this rule does not model:

- Graduated tax rates (O. Reg. 73/03) for commercial and industrial
- Optional small business subclass rates (Bill 62 / O. Reg. 330/21)
- Transitional tax ratios during class reform

Because of these known exceptions, flagged rows should be reviewed against
local by-laws rather than treated as definitive errors.

**Current status**: 95 flags across 30 municipalities on 2023 data, all
with small systematic differences around 2 percent. This is consistent
with graduated rates or small business reductions, supporting the warning
designation.

**Modification warnings**: Do not delete this rule despite the high flag
count. The honest calibration (warning with documented limitations) is
itself a demonstration of understanding false positive management, which
is a key skill for QA work. A future refinement is to add a "known
exceptions" mechanism that accepts a CSV of (municipality, property class)
pairs to exclude from flagging.

## Rule 07: Property class coverage (warning)

**What it checks**: For each municipality, counts the number of distinct
property classes with positive Phase-In assessment. Flags municipalities
whose count is less than half the median count for their tier (LT, ST, or
UT).

**Current status**: 1 flag on 2023 data, Cockburn Island Tp with 2 classes
against a single tier median of 6. Cockburn Island is a tiny remote
island; the flag is almost certainly a legitimate reflection of the
community's limited property base, not a data error.

**Modification warnings**: The threshold (half the median) is arbitrary.
Consider replacing with a more principled statistical approach (e.g.
below the 10th percentile of the tier distribution) when adding peer-group
outlier rules.

## Design patterns to reuse

When adding new rules, follow these patterns:

1. **Filter to the applicable rows first**, then check the identity. Don't
   check-then-filter.
2. **Use explicit tolerances**, not exact equality, for any comparison
   involving float arithmetic.
3. **Name the detail column clearly**. The detail string should read as a
   complete sentence that a non-technical reviewer can understand.
4. **Return an empty DataFrame with the right column schema** when the
   rule passes, not None or a bare empty DataFrame.
5. **Apply the `@_rule_meta` decorator** so the engine summary works
   correctly.
6. **Document limitations honestly in the docstring**, especially the
   legitimate exceptions the rule does not handle.
7. **Prefer warnings over errors** when there are known false positives.
   An error-level rule with known false positives is worse than a
   warning-level rule with the same behavior.

## Tolerance conventions

- **Dollar amounts**: $1 absolute (for single-tier tax comparisons) or $2
  absolute (for TOTAL tax which sums rounded tiers). Alternatively 0.5%
  relative, whichever is larger.
- **Tax rates**: 1e-7 absolute for component sums. 0.5% relative for
  within-municipality multiplicative identity checks.
- **Integer counts**: zero tolerance, exact equality.
