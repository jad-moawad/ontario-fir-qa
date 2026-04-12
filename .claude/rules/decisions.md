# Decision Log

---

## 2026-04-10: Schedule 26 architecture: S26-1 line 9199 matches SPC line 9990 (not 9910)

**Finding**: When comparing Schedule 26-1 line 9199 ("TOTAL before Adj.") to
Schedule 22 SPC, the correct reconciliation target is SPC line 9990, not SPC
line 9910. SPC line 9990 equals 9910 plus SRA surcharges (the 8xxx lines in
SPC). St Catharines illustrates this clearly: SPC 9910 = $275.5M but SPC 9990
= $338.1M, with the $62.5M difference being SRA-based surcharges (lines 8035,
8097, 9890). S26-1 line 9199 = $338.1M, matching 9990 exactly.

Testing across all four clean years (2019, 2020, 2021, 2023) confirms zero
discrepancies at $2 tolerance using S26 9199 vs SPC 9990. Testing with SPC
9910 instead produced 307 discrepancies for 2023 alone, all false positives.

**Column mapping confirmed**: In Schedule 26-1, the numeric data columns are:
col 03 = TOTAL Taxes, col 04 = LT/ST Taxes, col 05 = UT Taxes, col 06 = EDUC.
This was reverse-engineered by matching S26-1 line 10 (Residential) values for
Addington Highlands to the GPL residential RT row for the same municipality.

---

## 2026-04-10: 2022 SPC sheet is also corrupted (same defect as Total sheet)

**Finding**: The MunID column corruption in the 2022 Schedule 22 file that
was previously documented in the Total sheet also affects the SPC sheet. The
2022 SPC sheet has 138 MunIDs mapping to multiple municipality names, with
325 of 441 unique MunIDs in the line 9990 data. This is confirmed by running
the same zero-tolerance MunID pre-check on the SPC sheet.

Schedule 26 for 2022 is NOT corrupted (S26-1 has 441 unique MunIDs with zero
name collisions). The corruption is specific to the Schedule 22 internal
summary sheets (Total and SPC) and does not extend to Schedule 26, which is
collected as a separate FIR submission.

**Consequence for R11**: R11 (S26 vs SPC reconciliation) cannot run on 2022
because the SPC reference value is unreliable. The rule emits a diagnostic
skip row naming the 138 corrupted MunIDs. The phrase "Schedule 26 data is
clean for this year" is included in the skip message to highlight that the
external cross-check could theoretically be run, but we have no trustworthy
SPC value to compare against.

---

## 2026-04-10: R13 grand total chain must include SPC line 7010 (PIL adjustment)

**Finding**: The initial R13 implementation without SPC line 7010 produced 8
discrepancies in 2019 and 11 in 2020. The largest was York Region (19000) with
a $3.8M gap in both years. Inspection of York's SPC sheet revealed line 7010
with TOTAL = $3,805,332 in 2019, exactly equal to the gap.

Line 7010 is the "Payments-In-Lieu PIL Adjustments" line in SPC. It records
adjustments for shared PIL properties (properties where PILT is split across
multiple municipalities). This adjustment is added to compute SPC line 9910
but is NOT included in line 9799 (the SPC subtotal). The correct identity is:

    GPL(9299) + SRA-LT(9499) + SRA-UT(9699) + SPC(9799) + SPC(7010) = SPC(9910)

After including line 7010, R13 produces zero discrepancies across all four
clean years (2019, 2020, 2021, 2023). Rule 07 from the roadmap described the
identity without line 7010; the correct formula required exploration of the
data to discover.

---

## 2026-04-10: Phase 2 rules are canaries, not headline finders

**Observation**: R11, R12, and R13 all produce zero flags on clean data. This
is by design: they confirm that the FIR's internal arithmetic is consistent
and that Schedule 22 agrees with the external Schedule 26 filing. The absence
of flags is itself a quality signal.

**Interview framing**: The correct framing is "these rules establish a
reconciliation baseline. If any future year's submission breaks this chain,
the framework will surface it immediately. The 2022 year is a concrete
example of what detection looks like: R11 correctly skips 2022 and reports
why, instead of flooding the report with misleading error flags."

The INTERESTING finding from Phase 2 is the extension of the 2022 corruption
to the SPC sheet, and the discovery that Schedule 26 (a different filing)
is clean for the same year. This creates a natural narrative: the corruption
is in Schedule 22's summary layer only, not in the underlying data.

---

Non-obvious choices made during development, with reasoning. This is the
most valuable artifact for the interview: it proves the developer thought
through tradeoffs rather than following a checklist.

---

## 2026-04-10: Chatham-Kent M 2019 CVA Assessment values are a headline data defect

**Symptom**: R05 flagged 33 rows from Chatham-Kent M in the 2019 data, more
than any other municipality across all five years. Every property class row
for Chatham-Kent M showed Phase-In Taxable Assessment in the billions while
CVA Assessment was a small number (e.g. $45,900 for residential RT, $296,200
for farmland).

**Verification**: The TOTAL Taxes column is internally consistent with
Phase-In at the correct 2019 rates (residential RT: $6.57B x 0.01261 =
$82.8M, which matches the reported taxes exactly). CVA is the column at
fault, not Phase-In or the tax computation. By 2023, Chatham-Kent M's CVA
and Phase-In are both $7.23B for residential RT, correctly equal and in
plausible range for a municipality of this size.

**Interpretation**: The 2019 CVA Assessment column for Chatham-Kent M
appears to contain per-parcel or per-levy-area placeholder values rather
than the rolled-up class-level CVA totals the schedule requires. This is
a data submission error, not a template or loader issue.

**Significance**: Chatham-Kent M is a large single-tier amalgamated
municipality with a population of roughly 100,000, not a small remote
township. A submission error of this magnitude in a municipality of this
size is a genuine data quality finding. It is the third headline finding
for the interview alongside the 2023 Brant County $12.9M Phase-In excess
and the 2022 Total sheet MunID column corruption.

**Effect on cross-year rules**: R05 correctly flags these rows. Rule 08
(year-over-year levy change) is unaffected because it uses TOTAL Taxes,
which is computed from Phase-In and is correct. The CVA defect does not
distort levy-based analysis.

---

## 2026-04-10: 21 RTC/RTQ sub-class codes present in 2019 but absent in 2023

During the learn-and-adapt diagnosis before Rule 08, comparing the 2019
and 2023 GPL sheets found 21 RTC/RTQ codes in 2019 that do not appear in
2023 and 8 codes in 2023 that do not appear in 2019.

The 2019-only codes are: CD, IS, J7, JH, JT, JU, JX, KT, KU, S9, X7,
X9, XH, XK, XU, XX, YH, YT, YU, ZT, ZU. These correspond to three
property classes that also only appear in 2019: Large Ind. NConstr.,
Office Build. NConstr., and Shopp. Centre NConstr. These "new construction"
sub-classes were apparently reorganized or absorbed into other codes between
2019 and 2023.

The 2023-only codes include small business variants (C0, I0, C8, I8)
introduced under Bill 62 / O. Reg. 330/21 around 2021, which is consistent
with the regulation timeline.

**Significance for future rules**: Any rule that checks property class
coverage or counts RTC/RTQ codes across years must account for this
reorganization. A cross-year coverage check would spuriously flag
municipalities that reported Large Ind. NConstr. in 2019 as "losing a
class" by 2023. The roadmap's Rule 10 (municipality coverage continuity)
and any future class-coverage rules should carry an explicit exclusion list
for retired sub-class codes, or compare only against the codes present in
the current year rather than a fixed reference set.

---

## 2026-04-10: 2022->2023 broad-based levy increase is a province-wide economic signal

**Quantitative signal**: In the 2022->2023 year-pair, 330 of 432
municipalities (76%) showed total levy growth above 4%, with a median of
5.3% and a p95 of 10.2%. This is roughly double the pace of the 2021->2022
pair (median 3.5%, p95 6.9%) and more than triple the COVID-suppressed
2020->2021 pair (median 1.7%, p95 4.4%). The 2019->2020 pair had a similar
median (3.9%) but a tighter spread (p95 8.0%).

**Interpretation**: The 2022->2023 acceleration is consistent with two
reinforcing economic forces: (1) inflation-driven municipal operating cost
increases pushing councils to raise rates in 2023, and (2) post-COVID
assessment catch-up as MPAC's phased-in 2016 assessment values fully
matured and new development assessments added during the pandemic years
began to flow through to the levy. The broad geographic distribution (not
clustered in a single tier or region) rules out a local policy explanation.
The 2022 Total sheet MunID corruption was confirmed not to be a cause:
spot-checked municipalities showed 2022 as a smooth continuation of prior
trends, with 2023 elevated.

**Significance for interview framing**: This finding illustrates that the
QA framework can detect not only individual municipal errors but also
province-wide economic signals embedded in the FIR data. A Data and Quality
Assurance Unit that monitors this kind of province-wide distribution shift
year-over-year can alert policy staff early when levy growth is unusually
concentrated or unusually broad, independent of any individual submission
review. This positions the framework as an analytical tool, not merely a
validation checklist.

---

## 2026-04-10: Rule 08 threshold calibrated at 25%; 2022->2023 noise is economic, not a data artifact

**Threshold calibration**: The year-over-year levy change threshold of 25%
was chosen by examining the empirical distribution of consecutive-year
percent changes across all four adjacent pairs in the 2019-2023 dataset:

```
Pair        median   p95    max absolute   flags at 25%
2019->2020    3.9%   8.0%     12.5%             0
2020->2021    1.7%   4.4%     21.0%             0
2021->2022    3.5%   6.9%     37.4%             1
2022->2023    5.3%  10.2%     83.0%             5-6
```

At 25%, the rule catches only genuinely anomalous moves. The bulk of
municipalities fall in the 1-8% range; nothing above 25% outside the
flagged set. The constant YOY_LEVY_CHANGE_THRESHOLD is defined at the top
of cross_year_rules.py for easy tuning if the rule proves too noisy or
too quiet after review.

**2022->2023 noise investigation**: The 2022->2023 pair has roughly double
the p95 spread of the other three pairs (10.2% vs 4-8%). Three hypotheses
were tested: (1) the 2022 Total sheet MunID corruption caused
resubmissions that introduced artificial jumps; (2) inflation-driven rate
increases in 2023; (3) post-COVID assessment catch-up.

Spot-checking five municipalities in the ordinary 4-8% band for 2022->2023
(Beckwith Tp, Bracebridge T, Kitchener C, Newmarket T, Woodstock C) showed
smooth monotonically increasing trends in all five, with 2022 behaving as
a normal continuation of the prior trend. No municipality showed 2022 as
an outlier flanked by two normal years, which would be the signature of a
restatement artifact. Hypothesis 1 is ruled out.

The broad-based nature of the 2022->2023 shift (330 of 432 municipalities
above 4% growth, versus 40 of 444 in the COVID-suppressed 2020->2021 pair)
is consistent with hypotheses 2 and 3 acting together. This does not affect
Rule 08 because the 2022 Total sheet corruption is limited to the MunID
column, which Rule 08 never reads: it uses TOTAL Taxes from GPL only.

---

## 2026-04-10: R04 cannot be run reliably on the 2022 Total sheet

**Symptom**: Running R04 (GPL to Total sheet reconciliation) on
`data/raw/2022/schedule_22.xlsx` produced 879 error flags across 122
municipalities. The same rule produces 0 flags on 2023, 2021, and 2019
data, and 3 flags (1 municipality) on 2020 data.

**Root cause**: The MunID column in the 2022 Total sheet is corrupted.
MunID 11033 (which belongs to Addington Highlands Tp in the GPL sheet)
appears on hundreds of line 9299 rows covering nearly every municipality
in the province: Brampton, Guelph, Cornwall, Ottawa, and so on. The
correct data for each municipality exists in the Total sheet but is filed
under the wrong MunID, so every MunID-based join between GPL and Total
sheet fails for those municipalities.

**Evidence**:
- 72 of 441 municipalities have a different name on the same MunID when
  comparing the 2022 GPL sheet to the 2022 Total sheet.
- Cornwall C (GPL MunID 1012, Total Taxes $91.9M in GPL) has its Total
  sheet line 9201 row stored under MunID 11033, not MunID 1012.
- The 2022 GPL sheet itself is clean: all 432 MunIDs common to both 2022
  and 2023 GPL have consistent municipality names with zero exceptions.
- This corruption is specific to 2022. The Total sheet MunID column is
  reliable for 2019, 2020, 2021, and 2023.

**Consequence**:
- R04 flags for 2022 are all artifacts of the Total sheet defect, not
  genuine reconciliation failures. R04 should be skipped for 2022, or
  its output should carry an explicit caveat that the Total sheet MunID
  column cannot be trusted for that year.
- Cross-year rules (R08 through R10) must be built on GPL data only,
  joining by MunID. For 2022, the Total sheet is unusable for MunID-based
  joins.
- This finding is itself a genuine data quality flag: it demonstrates the
  kind of structural defect that an automated QA framework should surface
  for the ministry's attention.

---

## 2026-04-10: R04 uses zero-tolerance MunID corruption detection, not a threshold

When checking whether the 2022 Total sheet is safe to use for reconciliation,
the pre-check compares municipality names for every MunID that appears in
both the GPL and Total sheets. If any single MunID maps to a different name
across the two sheets, the rule is skipped for that year.

The earlier draft used a 10% threshold. That was rejected because: (a) a
MunID is a unique key and there is no "acceptable" mismatch rate; (b) a
threshold is an arbitrary number that will eventually trip on an edge case;
(c) removing the threshold also removes the number from the codebase, which
is the kind of thing interviewers notice. Zero tolerance is the correct
semantic: healthy data has literally zero mismatches.

The rule emits a single "R04 SKIPPED" error row when corruption is detected,
rather than silently suppressing R04. This ensures the report shows something
for R04 every year, and the skip reason (mismatch count plus a 3-municipality
sample) is visible to the analyst.

---

## 2026-04-10: Chose line 9299 over 9201 for GPL reconciliation

When reconciling GPL sums against the Total sheet, use line 9299 (the
post-levy-area-aggregation roll-up), not line 9201 (the per-levy-area
roll-up).

**Reason**: Municipalities split into multiple levy areas (e.g. Frontenac
Islands has separate rows for Howe Island and Wolfe Island) generate
multiple 9201 rows. Joining on 9201 therefore double-counts those
municipalities and produces spurious mismatches. Line 9299 is one row per
municipality after aggregation and is the correct reconciliation target.

---

## 2026-04-10: R02 restricted to RTC/RTQ = "RT" (main residential class only)

The original R02 filtered on `Property Class == "Residential"` with no
sub-class restriction. This caused a false positive on 2020 data: Morris-
Turnberry M had an R1 sub-class (Farm Awaiting Development Phase I) row with
a tax ratio of 0.25 rather than 1.00.

R1 retains farmland's 0.25 ratio by regulation while the property awaits
residential development. The 0.25 ratio is correct for R1 and is not a data
entry error. The fix is identical to the one already applied to R03: restrict
the check to RTC/RTQ = "RT" (the main, full residential class) and exclude
all sub-class codes.

After the fix, R02 produces 0 flags across all five years (2019-2023), which
is the correct result: the 1.00 residential ratio is law-enforced and the
FIR template enforces it for the main class.

---

## 2026-04-10: R03 replaced hardcoded 2023 rate with year-keyed lookup dict

The original R03 compared EDUC rates against a single constant
(STD_RESIDENTIAL_EDUC_RATE_2023 = 0.00153). Running R03 on 2019 data
produced 424 false positives across 414 municipalities because the
provincial residential education tax rate was 0.00161 in 2019, dropping
to 0.00153 in 2020 where it has remained through 2023.

The fix replaces the constant with STD_RESIDENTIAL_EDUC_RATE, a dict keyed
by year. The rule reads the year from the GPL data's Year column
(mode of non-null values) and looks up the expected rate. If the year is not
in the dict, the rule returns zero flags rather than applying a wrong rate.

The correct rates were confirmed by finding the mode of EDUC Tax Rate across
all RT LT/ST rows with positive Phase-In assessment for each year:
2019: 0.00161, 2020-2023: 0.00153. Source: O. Reg. 400/98.

After the fix, R03 produces 0 flags for 2020-2023 and 1 flag for 2019
(Ramara Tp at 0.001611, which is 1e-6 above the provincial rate and is a
genuine data anomaly, not a false positive).

---

## 2026-04-10: R06 downgraded to warning, not error

The within-municipality rate consistency check (LT/ST rate for a
non-residential class should equal the residential LT/ST rate times the
tax ratio) has documented exceptions that the rule does not model:
graduated tax rates (O. Reg. 73/03) and optional small business subclass
reductions (Bill 62, O. Reg. 330/21). Marking these as errors would
generate systematic false positives and train the analyst to ignore the
report. Warning with a documented limitation is the correct calibration.

---

## 2026-04-10: Rule 03 filter restricts to RTC/RTQ = "RT" and Tier in LT, ST

A naive residential education rate check generated 138 false positives
out of 710 residential rows (20 percent noise rate). The two sources of
false positives are:
- 86 rows: upper-tier municipalities with NaN EDUC rate (structurally
  correct: UT municipalities do not levy education taxes directly).
- 52 rows: R1 sub-class (Farm Awaiting Development Phase I) which has
  its own rate set by regulation, distinct from the standard residential
  rate.

Filtering to RTC/RTQ == "RT" and Tier in ("LT", "ST") reduces false
positives to zero while still catching any genuine misreported standard
residential rate.
