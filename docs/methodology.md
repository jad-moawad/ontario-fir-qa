# Methodology Note: Ontario FIR Data Quality Framework

**Project:** Portfolio project for Senior Data and Quality Analyst, Ontario Ministry of Finance, Property Tax Services Partnerships Branch (Job ID 242142)
**Data:** Ontario Financial Information Return, Schedule 22 (2019-2023), Schedule 26 (2019-2023)
**Framework version:** Phase 4 (Phases 0-2 complete; Phase 3 deferred)

---

## 1. Rule framework architecture

### 1.1 Rule function contract

Every rule is a Python function decorated with `@_rule_meta(rule_id, rule_name, severity)`. The decorator attaches those three values as function attributes. This design means the summary builder in `engine.py` can report rule names and severities even when a rule returns zero flags, which matters for the interview pitch: a rule that passes cleanly is not silence, it is a positive signal.

All rules return a pandas DataFrame with a fixed structure:

- Three metadata columns prepended: `rule_id`, `rule_name`, `severity`
- Rule-specific content columns (varies by rule)
- A `detail` column at the end with a plain-English explanation of each flag

A rule that finds nothing returns an empty DataFrame with this column schema intact. The engine distinguishes "passed" from "errored" by length, not by None or exception.

### 1.2 Three rule families

**Single-year rules (R01-R07)** take one sheets dict, run against a single year's Schedule 22, and return a flat DataFrame of flagged rows. The engine runs these per file; `run_all()` in `rules.py` dispatches to each and collects results by function name.

**Cross-year rules (R08)** take a dict of `{year: sheets}`. They can only fire when at least two years are loaded. The signature difference is intentional and enforced: cross-year rules cannot be accidentally called with a single year's data.

**Cross-schedule rules (R11-R13)** take `(sheets_22, sheets_26[, year])`. R11 requires the year argument because it needs to validate the Schedule 26 file for the correct reporting period. R12 and R13 operate on internal Schedule 22 structure only and do not need the year.

### 1.3 Tolerances

Tolerances are explicit constants, not implicit. Dollar comparisons use $1 (single-tier) or $2 (total, absorbing rounding propagation across tiers). Rate comparisons use 1e-7 for component sums and 0.5% relative for multiplicative-identity checks. Year-over-year levy changes use 25% as the anomaly threshold, calibrated against the empirical 2019-2023 distribution (p95 ranges from 4.4% in the COVID-suppressed 2020-2021 pair to 10.2% in the inflation-driven 2022-2023 pair).

---

## 2. Domain calibration: the learn-and-adapt protocol

Writing a QA rule against property tax data without domain knowledge produces a high false positive rate. The clearest example is Rule R03 (standard residential education rate). A naive implementation checking `EDUC rate == 0.00153` against all residential rows generated 138 false positives out of 710 rows (19% noise rate). The false positives broke into two categories:

- 86 rows: upper-tier municipalities, which do not levy education taxes directly. Their EDUC rate is NaN by design, not an error.
- 52 rows: R1 sub-class (Farm Awaiting Development Phase I), which carries its own education rate set separately by O. Reg. 400/98, not the standard residential rate.

Adding two filters (`RTC/RTQ == "RT"` and `Tier in ("LT", "ST")`) reduced false positives to zero while still catching any genuine misreported standard residential rate. This required reading the Ontario regulation, not just the data.

The development protocol for each new data year or schedule was:

1. Run existing rules on the new file and record flag counts.
2. Compare counts to the prior file. Investigate any count that jumped dramatically.
3. Spot-check five flagged rows manually to confirm they represent genuine anomalies in the new data.
4. Look for anomalies the existing rules do not catch.
5. Ask whether the new data changes any assumption from an earlier phase.

This protocol caught the 2022 Total sheet MunID corruption (Step 2: R04 produced 879 flags on 2022 vs 0 on 2023), the Chatham-Kent M 2019 CVA defect (Step 3: spot-checking R05 flags revealed per-parcel placeholder values), and the need to include SPC line 7010 in the R13 grand total chain (Step 5: York Region showed a persistent $3.8M gap exactly equal to the PIL adjustment line).

---

## 3. Case study: zero-tolerance corruption detection in R04

Rule R04 reconciles the sum of GPL taxes per municipality against Total sheet line 9299. When run against the 2022 Schedule 22 file, it produced 879 error flags across 122 municipalities rather than the near-zero count seen in all other years. Investigation revealed that the MunID column in the 2022 Total sheet is corrupted: MunID 11033 (Addington Highlands Tp in the GPL) appears on hundreds of line 9299 rows that should belong to completely different municipalities.

The detection mechanism that replaced the naive reconciliation is a zero-tolerance pre-check:

1. For each MunID that appears in both the GPL and Total sheets, compare the municipality name.
2. If any single MunID maps to a different name across the two sheets, skip the reconciliation for that year.
3. Emit a single diagnostic row that states the mismatch count and names three affected municipalities.

The threshold is zero, not a percentage, for a principled reason: a MunID is a unique key. There is no "acceptable" mismatch rate. Even one mismatch means the join between sheets is untrustworthy. A threshold of, say, 10% would be an arbitrary number that invites edge cases; zero tolerance removes the number from the codebase entirely.

This approach transformed the 2022 report from 879 misleading error flags to one informative diagnostic row. The diagnostic row also confirmed that the 2022 GPL sheet itself is clean (all 432 MunIDs common to 2022 and 2023 have consistent names, zero exceptions). The cross-schedule rules (R11-R13) subsequently confirmed that the 2022 Schedule 26 is also clean, placing the corruption squarely in the Schedule 22 summary layer.

---

## 4. IAAO ratio study vocabulary: future work

The framework currently operates on municipality-level aggregate data. The most significant extension would be an IAAO-standard assessment ratio study using parcel-level data, which MPAC publishes through its Assessment Roll.

An assessment ratio is the ratio of assessed value to sale price for a sold property. Three metrics from IAAO Standard on Ratio Studies are the industry standard for assessing quality and vertical equity:

**Coefficient of Dispersion (COD).** Measures uniformity: how tightly the ratios cluster around the median. IAAO standards require COD below 15% for residential property and below 20% for income-producing property.

```
COD = 100 * mean(|ratio_i - median_ratio|) / median_ratio
```

**Price-Related Differential (PRD).** Detects vertical inequity between low-value and high-value properties. Values above 1.03 suggest regressive assessment (lower-value properties over-assessed relative to higher-value ones); below 0.98 suggests progressive assessment. IAAO standard: 0.98 to 1.03.

```
PRD = mean_ratio / (sum(ratio_i * sale_price_i) / sum(sale_price_i))
```

**Price-Related Bias (PRB).** Also measures vertical equity, via regression of the ratio on log-sale-price. A negative coefficient indicates regressivity (ratios fall as prices rise). IAAO standard: coefficient between -0.05 and +0.05.

```
PRB = slope of OLS regression: ratio_i ~ log(sale_price_i)
```

MPAC publishes municipality-level ratio study results in its Assessment Roll Quality Reports. A natural extension of this framework would be a `ratio_study.py` module that reproduces MPAC's published COD/PRD/PRB values from parcel-level data and enables ad-hoc deep dives by property class, year, or geographic area. The municipality structure already in place (MunID keys, tier metadata from Schedule 02) would slot directly into such a module.

The reason this is future work rather than current implementation is that parcel-level assessment-to-sale data is not part of the publicly available FIR dataset. It requires a data-sharing agreement with MPAC or access to MPAC's internal data through the ministry.

---

## 5. Reference list

**Ontario legislation and regulations:**

- Municipal Act, 2001, s.294(1): legal requirement for municipalities to file the FIR annually. https://www.ontario.ca/laws/statute/01m25
- O. Reg. 400/98: Provincial education tax rates by year and property class. The standard residential rate is 0.00153 for 2020-2023 and 0.00161 for 2019.
- O. Reg. 73/03: Optional graduated tax rates for commercial and industrial properties.
- O. Reg. 282/98: Property classification rules (defines residential, commercial, industrial, farmland, managed forest, and sub-classes).
- O. Reg. 330/21 (Bill 62): Optional small business subclass rates. Introduced the C0 and I0 RTC/RTQ codes visible in 2022 and 2023 data but absent in 2019-2020 data.

**Assessment methodology:**

- IAAO Standard on Ratio Studies. International Association of Assessing Officers. The industry standard for assessment uniformity and vertical equity metrics. https://www.iaao.org/
- MPAC Vertical Equity Review of Residential Assessed Values (2022). Example of an applied ratio study writeup. https://www.mpac.ca/sites/default/files/docs/pdf/VerticalEquityReviewofResidentialAssessedValues.pdf
- MPAC Assessment Roll Quality Reports. Published per municipality; demonstrates the kind of output a Data and Quality Assurance Unit produces. https://www.mpac.ca/en/AboutUs/HowMPACmeasuresqualityandaccuracyresidentialproperties

**Data source:**

- Ontario Financial Information Return, published by the Ministry of Municipal Affairs and Housing under the Open Government Licence Ontario. https://efis.fma.csc.gov.on.ca/fir/index.php/en/open-data/fir-by-schedule-and-year/
