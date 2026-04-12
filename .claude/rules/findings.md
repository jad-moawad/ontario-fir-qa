# Current Findings and Interview Framing

This file captures what the framework has found so far and how to present
the project to the hiring manager at interview time.

## Summary of findings on 2023 Schedule 22

Engine run on `data/raw/2023/schedule_22.xlsx` produces:

```
R01  Template arithmetic integrity        error      0 flags
R02  Residential tax ratio = 1.00         error      0 flags
R03  Standard residential EDUC rate       error      0 flags
R04  GPL <-> Total sheet reconciliation   error      0 flags
R05  Phase-In <= CVA                      error      9 flags  (4 munis)
R06  Within-muni rate consistency         warning   95 flags  (30 munis)
R07  Property class coverage              warning    1 flag   (1 muni)

Total: 105 flags (9 errors, 96 warnings)
```

## Rule 05 detail: real anomalies in the data

The most striking finding is in Rule 05. Brant County alone has 5 flags
across different sub-classes, with Commercial Vacant Land showing $23.2M
CVA but $36.1M Phase-In, an excess of $12.9M. Other flagged municipalities
are Markstay-Warren M (Residential and Farmland), Ottawa C (Industrial IH),
and the rest of Brant County's classes.

These are genuinely anomalous and represent exactly the kind of finding a
Data and Quality Assurance Unit analyst would want to investigate. Possible
causes:

1. Mid-year reclassifications that updated Phase-In but not CVA
2. Supplementary assessments for new construction added during the year
3. Data entry errors in the CVA column
4. Merger or split of parcels during the year

None of these are automatically "bugs" in the FIR, but all of them are
things that should be flagged for human review, which is precisely the
purpose of an automated QA pipeline.

## Rule 06 interpretation

95 flags in Rule 06 is actually a feature, not a problem, as long as it is
framed correctly. The flags cluster around small systematic deviations
(roughly 2 percent) which is consistent with graduated tax rates and small
business rate reductions. The rule honestly acknowledges this limitation in
its docstring and is marked as a warning rather than an error.

In the interview, the right framing is: "I built the multiplicative
identity check because it is a powerful sanity check, then discovered that
Ontario allows legitimate deviations I had not modeled, so I downgraded the
rule to a warning and documented the known exceptions. A production version
would layer in a by-laws database to distinguish legitimate graduated rates
from actual errors."

## Rule 07 interpretation

Cockburn Island Tp is a tiny remote island community. Flagging it with only
2 property classes is technically correct (it is far below the median) but
is almost certainly not a data quality problem. This is the kind of flag
that shows up in any peer-group outlier system and requires a human to
confirm.

The correct framing for interview is: "Rule 07 is a soft warning that
surfaces candidates for manual review. It correctly identified Cockburn
Island Tp as an outlier. In this case the outlier is legitimate, which is
normal for this kind of rule. The value of the rule is that if Cockburn
Island were ever to start reporting more classes, any backslide to only 2
classes would be caught."

## What Rules 01 through 04 tell us

Rules 01 through 04 returning zero flags is the correct outcome for a
healthy well-maintained file. The FIR Excel template enforces arithmetic
identity via cell formulas, and the province legislates residential ratios
and education rates. In aggregate, these rules pass because the system
actually works well for the things the template can enforce.

The value of these rules is:

1. As a canary: if they ever start flagging things, something is broken
   (file corruption, manual cell overrides, regulation change not
   propagated).
2. As a baseline: they establish that the framework is working and the
   data is clean on the strict checks, so the warnings from Rules 05, 06,
   07 are not drowning in noise.
3. As documentation: each rule docstring references the specific Ontario
   regulation or template mechanism that enforces the identity, which
   demonstrates domain awareness.

## Headline findings in priority order for the interview

These are the findings most likely to land in a 10-minute interview
conversation. Listed in order of impact and narrative clarity.

### 1. Northeastern Manitoulin & The Islands: missing municipal levy in 2023

Rule 08 (year-over-year levy change) flagged an 83% drop in total levy
from $6.16M in 2022 to $1.05M in 2023. Investigation of the GPL rows
revealed that every LT/ST tax rate and every UT tax rate for the
municipality is exactly 0.0000 in the 2023 submission. The $1.05M
represents only the provincial education tax component. The entire
municipal levy is absent.

Verification: neighbouring municipalities Assiginack Tp (LT/ST 0.0151)
and Gore Bay T (LT/ST 0.0177) have normal rates in 2023. The municipality
also consolidated from three levy areas to one in 2023, consistent with
a restructuring or transition-year filing. Total Phase-In CVA actually
increased from roughly $320M to $537M across all classes, so the
assessment base did not collapse. The zero-rate submission is either a
data quality failure (rates not entered) or a restructuring transition
freeze that the FIR data does not explain on its own.

Significance: this is the most actionable finding in the dataset. A
single automated check caught a case where a municipality's entire
municipal tax levy is unaccounted for in their FIR submission. No
single-year rule could detect this; it required cross-year comparison.

One-sentence interview framing: "Rule 08 found a municipality that filed
its 2023 FIR with zero municipal tax rates on every property class, so
their entire levy was missing from the submission. That's the kind of
thing that takes a year to notice without automated cross-year checking."

---

### 2. 2022 Total sheet MunID corruption: structural data defect across 122 municipalities

Running the GPL-to-Total-sheet reconciliation rule (R04) on the 2022
Schedule 22 file produced 879 error flags across 122 municipalities.
Investigation showed the Total sheet's MunID column is corrupted: MunID
11033 (Addington Highlands Tp in the GPL) appears on hundreds of line
9299 rows covering almost every municipality in the province. 72 of 441
MunIDs map to a different municipality name in the Total sheet than in
the GPL sheet.

Verification: the 2022 GPL data is clean (all 432 MunIDs common to 2022
and 2023 have consistent names, zero exceptions). The corruption is
confined to the 2022 Total sheet. Years 2019, 2020, 2021, and 2023 pass
R04 cleanly (2020 has one legitimate 3-flag finding for Mattawa T).

Response: R04 now includes a zero-tolerance pre-check. Any file where a
single MunID maps to different names across GPL and Total sheet triggers
a skip with a diagnostic row naming the corrupted count and a sample.
This took the 2022 report from 879 misleading error flags to one clean
diagnostic row.

One-sentence interview framing: "The reconciliation rule detected that
the 2022 Total sheet has corrupted municipality IDs, so instead of
flooding the report with 879 false positives, the framework now detects
the corruption automatically, skips the rule for that year, and explains
why."

---

### 3. Chatham-Kent M 2019: catastrophically wrong CVA column

Rule 05 (Phase-In <= CVA) flagged 33 rows from Chatham-Kent M in 2019,
with the residential RT row showing CVA of $45,900 against Phase-In of
$6.57B, an apparent excess of $6.57B. Investigation confirmed the
Phase-In and taxes are internally consistent at the correct 2019 rates
($6.57B x 0.01261 = $82.8M, matching reported taxes exactly). CVA is
the defective column. By 2023, both CVA and Phase-In are correctly
$7.23B for residential RT.

Verification: the 2019 CVA values for Chatham-Kent M are clearly
per-parcel or per-levy-area placeholders erroneously left in a field
that should hold rolled-up class-level CVA totals. This affects every
property class in the municipality. Toronto C in the same year shows
a normal CVA of ~$547B.

Significance: Chatham-Kent M is a 100,000-population single-tier
municipality, not a small remote township. A submission error of this
kind at this scale is material.

One-sentence interview framing: "The Phase-In vs CVA rule found that
Chatham-Kent's 2019 CVA column has per-parcel placeholder values instead
of class-level totals, a data submission error that left $6.5 billion of
assessed value effectively unverified in that year's filing."

---

### 4. Brant County 2023: $12.9M Phase-In excess over CVA

Rule 05 flagged Brant County Commercial Vacant Land with CVA of $23.2M
but Phase-In of $36.1M, an excess of $12.9M. Brant County accounts for
5 of the 9 Rule 05 flags in 2023 across multiple sub-classes.

Possible causes: mid-year reclassification that updated Phase-In without
updating CVA, supplementary assessment for new construction, or data
entry error.

One-sentence interview framing: "The Phase-In check caught Brant County
reporting $12.9M more in taxable assessment than its current value on
commercial vacant land, which should be impossible under Ontario's
phase-in mechanism."

---

### 5. Rule 08 rate-increase flags: three municipalities with 30-52% LT/ST rate jumps

Three of the six Rule 08 flags (Huron East M, North Huron Tp,
Black River-Matheson Tp) were explained by investigation as large
single-year LT/ST rate increases:

- Huron East M: LT/ST rate 0.004450 to 0.006759 (+51.9%); assessment
  grew only 2.9%. The entire $4.2M levy increase is rate-driven.
- North Huron Tp: LT/ST rate 0.010076 to 0.013443 (+33.4%); assessment
  grew 4.1%.
- Black River-Matheson Tp: LT/ST rate 0.012740 to 0.017061 (+33.9%);
  assessment grew 2.8%.

All three are in Northern Ontario or Huron County. Whether these reflect
deliberate multi-year catch-up rate increases or data entry errors
requires review of council budget minutes. The framework surfaces them
correctly as anomalies warranting human review.

Brethour Tp's two-year pattern (+37.4%, then -26.3%) was confirmed as a
supplementary assessment reversal: residential Phase-In doubled from
$8.56M to $17.24M in 2022 then returned to $8.11M in 2023, with tax
rates stable throughout at ~1.04%.

One-sentence interview framing: "Three small municipalities showed
30-50% jumps in their LT/ST tax rates in a single year. The rule can't
distinguish between a legitimate catch-up decision and a data entry
error, but it surfaces them for a human to check the council minutes."

---

### 6. Province-wide 2022->2023 levy acceleration

Across all 432 municipalities, the 2022->2023 year-pair shows median
levy growth of 5.3% with 330 of 432 municipalities (76%) above 4%.
This is roughly double the pace of 2021->2022 (median 3.5%) and triple
the COVID-suppressed 2020->2021 (median 1.7%).

Investigation confirmed this is a real economic signal, not a data
artifact from the 2022 Total sheet corruption. Spot-checked
municipalities show 2022 as a smooth continuation of prior trends with
2023 uniformly elevated, consistent with inflation-driven rate increases
and post-COVID assessment catch-up across the province.

Significance: the framework detects not only individual errors but
also province-wide distributional shifts that would be invisible in any
single-year review.

One-sentence interview framing: "The cross-year analysis shows that
2023 was an unusually high-growth year for property tax levies
province-wide, which matters for a QA unit because it sets the context
for interpreting individual municipality flags: a 10% jump in 2023 is
less suspicious than a 10% jump in 2021."

---

## Interview framing (top level)

Frame the project as "a proof of concept for what the Data and Quality
Assurance Unit might build on day one, using the actual data the Ministry
collects." Key points to emphasize:

1. **Domain awareness**. Use Rule 03 as the story. A naive version
   generated 138 false positives out of 710 rows. Understanding
   sub-classes and tier structure reduced this to zero. This single
   example demonstrates that you understand what makes property tax QA
   different from generic data QA.

2. **Honest calibration**. Rule 06 has known false positives and is
   marked warning, not error, with documented limitations. This
   demonstrates that you think about false positive management, which
   is the hardest part of QA work.

3. **Cross-sheet reconciliation**. Rule 04 reconciles GPL sums against
   Total sheet line 9299 (not 9201, a lesson learned from Frontenac
   Islands). This kind of check is the backbone of any real QA pipeline
   because it catches situations where a levy was reported on one sheet
   but not rolled up correctly.

4. **Real finding**. Rule 05 caught Brant County's $12.9M excess of
   Phase-In over CVA on Commercial Vacant Land. This is a real anomaly
   that a human should investigate.

5. **Coachable framing**. Explicitly say "this is a proof of concept, I
   welcome critique of the rule set." Brand new team means the hiring
   manager is thinking about culture fit as much as technical skill.
   Showing that you expect to iterate signals collaborative mindset.

## Phase 2 findings: cross-schedule reconciliation

Phase 2 implemented three cross-schedule rules (R11, R12, R13) using Schedule
26 data for all five years. Results:

```
R11  Schedule 26 vs S22 grand total    error   0 flags (4 years clean; 2022 SKIP)
R12  SRA-LT vs Total sheet line 9499   error   0 flags (4 years clean; 2022 SKIP)
R13  Grand total chain reconciliation  error   0 flags (4 years clean; 2022 SKIP)
```

Zero flags on clean data is the expected result. These are canary rules that
confirm Schedule 22's internal arithmetic closes and that the external
Schedule 26 filing agrees with the S22 grand total.

The 2022 skip rows are the Phase 2 finding. The corruption already documented
in the 2022 Total sheet extends to the 2022 SPC sheet (138 MunIDs mapping to
multiple names in SPC, matching the 150 in Total). Schedule 26 for 2022 is
clean (441 unique MunIDs, zero name collisions), confirming the corruption
is confined to Schedule 22's internal summary sheets.

A non-obvious discovery in Phase 2: the grand total chain (R13) requires
including SPC line 7010 (PIL adjustments) to close correctly. Without it,
York Region (2019) shows a $3.8M gap that exactly equals line 7010. The line
represents adjustments for shared PIL properties and is added to 9910 but not
included in 9799. This is the kind of detail a QA team would learn through
investigation, not documentation.

## Phase 2 interview framing

The cross-schedule rules demonstrate three things:

1. **External validation**: Schedule 26 is a separate FIR filing submitted
   through a different mechanism. Using it as an external cross-check against
   Schedule 22 is the most credible reconciliation possible, because neither
   schedule can "fix" the other's errors retroactively.

2. **Corruption scope confirmation**: The 2022 corruption is in Schedule 22's
   summary layer. Schedule 26 for 2022 is clean. This matters because it tells
   a ministry analyst "the source data is probably fine; the problem is in how
   the summary was generated or exported."

3. **Honest calibration continues**: Three rules producing zero flags on clean
   data is not a failure. It is exactly what a well-maintained system should
   produce. The rules exist so that if a future submission breaks the chain,
   the framework surfaces it rather than letting it go unnoticed.

---

## What to bring to the interview

- A laptop open to the GitHub repo (once it is published)
- The reports/ directory with CSVs for all 5 years, cross_year/, and cross_schedule/
- A printed or displayed methodology note summarizing the rule set
- Specific numbers ready: "11 rules across 5 years (2019-2023), up to 444
  municipalities. Zero false positives on strict single-year checks.
  Cross-year analysis caught a municipality filing with zero municipal
  tax rates in 2023, a 2022 file with corrupted MunID columns in both the
  Total sheet and SPC sheet (confirmed clean in Schedule 26), Brant County's
  $12.9M Phase-In excess, and three municipalities with 30-50% rate jumps.
  Cross-schedule reconciliation (R11-R13) confirms Schedule 26 and Schedule
  22 agree province-wide for all clean years."
- A prepared answer to "what would you do next": see roadmap.md

## Questions you might get asked

"Why didn't you flag the Rule 06 discrepancies as errors?" -> "Because
Ontario allows graduated rates under O. Reg. 73/03 and small business
reductions under Bill 62, which would generate legitimate deviations
from the multiplicative identity. I'd rather under-call than over-call;
a warning with documented limitations is more useful to an analyst than
an error that cries wolf."

"How would you extend this to the other schedules?" -> "The loader is
already set up to handle arbitrary schedules; I just need to add
per-schedule reconciliation rules. The most valuable next step is
cross-year rules which catch unexplained jumps, because single-year
data can't detect those. After that, peer-group outlier rules using
Schedule 02 and Schedule 80 for peer metadata."

"What would you do with parcel-level data?" -> "Implement an IAAO ratio
study: compute assessment-to-sale ratio, coefficient of dispersion, and
price-related bias per municipality, then compare against MPAC's
published standards. The framework already has the municipality
structure in place; the ratio study would be a new module that consumes
parcel-level sales data joined against assessment data. MPAC publishes
municipality-level ratio study results already, so the work would be
building a pipeline that reproduces those and enables ad-hoc deep dives."

"How long did this take?" -> Be honest. Something like "about X
weekends of focused work, because I wanted to ship something I'd be
proud of rather than something rushed."

"Why this project and not something closer to your research
background?" -> "Three reasons. First, it's aimed at this exact job:
using the data your ministry collects, running the kinds of checks
your new unit will run. Second, it lets me demonstrate both the data
engineering side and the domain side of my skill set in one artifact.
Third, I learned a lot about Ontario property tax in the process,
which I think is useful regardless of whether I get this job."
