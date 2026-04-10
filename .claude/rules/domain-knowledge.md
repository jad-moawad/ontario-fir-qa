# Ontario Property Tax and FIR Domain Knowledge

This file captures the property tax domain knowledge needed to reason about
the Ontario FIR Schedule 22 data and to design quality assurance rules that
do not generate false positives.

## How Ontario property tax works at a high level

MPAC (Municipal Property Assessment Corporation) assesses every property in
Ontario and assigns it a Current Value Assessment (CVA). Municipalities set
tax rates by property class each year. The tax a property owes is CVA (or
the phase-in-adjusted assessment) multiplied by the sum of the relevant tax
rates. There are typically three tax rate components:

- LT/ST rate: lower-tier or single-tier municipal rate
- UT rate: upper-tier (regional) municipal rate, applies only where a region
  exists (e.g. Durham, York, Halton)
- EDUC rate: provincial education tax rate, set by Ontario regulation

TOTAL rate is the sum of these three. TOTAL taxes paid equals the taxable
assessment times the TOTAL rate.

## Tier structure

Ontario municipalities come in three flavors:

- **Lower-tier (LT)**: municipalities within a regional government (e.g.
  Oshawa within Durham Region). They levy their own LT rate and the region
  levies the UT rate on top.
- **Upper-tier (UT)**: the regional government itself (e.g. Durham R). UT
  rows in Schedule 22 report the UT rate and the UT portion of the levy.
  Critically, **upper-tier municipalities do NOT levy education taxes
  directly**, so their EDUC rate column is NaN. This is structurally correct
  and not a data quality issue.
- **Single-tier (ST)**: a municipality with no upper tier (e.g. Toronto,
  Ottawa, Hamilton). They levy both LT-equivalent and UT-equivalent rates in
  the same row.

When filtering for education tax rate checks, always restrict to
`Tier.isin(["LT", "ST"])` because UT rows will legitimately have NaN.

## Property classes and sub-classes (RTC/RTQ codes)

Schedule 22 uses two-letter RTC/RTQ codes to distinguish property classes
and sub-classes. A partial list based on observed 2023 data:

- **Residential**: RT (main, Full Occupied), RH (Full Occupied Shared PIL),
  R1 (Farm Awaiting Development Phase I), RD (Education Only), etc.
- **Multi-Residential**: MT (main), NT (New Multi-Residential)
- **Farmland**: FT (main)
- **Managed Forest**: TT
- **Commercial**: CT (main, Full Occupied), CU (Excess Land), CX (Vacant
  Land), CJ (Vacant Land Shared PIL), C7 (Small Scale On Farm Business),
  C0 (Small Scale on Farm Business Discounted)
- **Office Building**: DT
- **Shopping Centre**: ST (main), SU (Excess Land)
- **Parking Lot**: GT
- **Industrial**: IT (main), IH (Shared PIL), I1 (Farm Awaiting Dev),
  IU (Excess Land), IK (Excess Land Shared PIL), IX (Vacant Land),
  I7 (Small Scale On Farm)
- **Large Industrial**: LT (main), LU (Excess Land)
- **Pipeline**: PT

The most important insight: sub-classes have different tax rates and
different rules than their main class. A residential row with RTC/RTQ of R1
(Farm Awaiting Development Phase I) has a different education rate than a
normal residential row, and this is set by regulation, not an error.

**Rule 03 lesson**: a naive rule that said "residential education rate must
equal 0.00153" generated 138 false positives out of 710 residential rows
(19 percent noise). Filtering to `RTC/RTQ == "RT"` and `Tier in ("LT", "ST")`
reduced this to zero false positives. Always think about sub-classes and
tier when designing a rule.

## Tax ratios

Ontario's tax ratio system makes residential the reference class with ratio
1.00 by definition. Other classes have ratios set by the upper tier (or the
single tier municipality), typically:

- Residential: 1.00 (fixed by law)
- Multi-Residential: around 2.0 (varies)
- Commercial: around 1.5 to 2.6
- Industrial: around 2.0 to 3.2
- Farmland: 0.25 (fixed by law)
- Managed Forest: 0.25 (fixed by law)

Within a municipality, the LT/ST tax rate for a non-residential class should
equal the residential LT/ST rate multiplied by that class's tax ratio. This
is the "multiplicative identity" Rule 06 checks.

**Rule 06 lesson**: this identity has legitimate exceptions Ontario allows
which Rule 06 does not currently model:

- **Graduated tax rates** (O. Reg. 73/03): commercial and industrial
  properties can have different rates by value band within the same class.
- **Small business subclass rates** (Bill 62 / O. Reg. 330/21): optional
  reduced rates for small business properties.
- **Transitional tax ratios**: during class reform, some classes phase in
  new ratios over multiple years.

This is why Rule 06 is a warning, not an error.

## Phase-In assessment

CVA is the full assessed value. Phase-In Taxable Assessment is what actually
gets taxed after any phase-in adjustment. Under Ontario's system, when
assessments increase, the increase is phased in over 4 years; decreases take
effect immediately. This means Phase-In should always be less than or equal
to CVA, never greater. Rule 05 checks this identity.

However, there are some structural exceptions that might cause Phase-In to
exceed CVA:

- Supplementary assessments for new construction added mid-year
- Mid-year reclassifications that split or merge properties
- Data entry errors in CVA that have not been corrected

Large excesses (e.g. Brant County Commercial Vacant Land with $13M excess)
are almost certainly real data errors. Small excesses may be structural.

## Schedule 22 sheet structure

Schedule 22 has five sheets that the loader knows about:

1. **SCHEDULE 22GPL** (General Purpose Levy): the main levy detail table.
   One row per (municipality, property class, sub-class, levy area). This
   is the richest sheet and the primary target for rules.
2. **SCHEDULE 22SRA-LT** (Special Rate Areas, Lower Tier): special levies
   applied only to specific geographic areas within a lower-tier
   municipality (e.g. urban service area levies).
3. **SCHEDULE 22SRA-UT** (Special Rate Areas, Upper Tier): same concept at
   the upper-tier level (e.g. region-wide waste collection levies).
4. **SCHEDULE 22SPC** (Special Purpose Charges): line-coded summary of
   special charges, includes grand totals.
5. **SCHEDULE 22Total**: roll-up totals per municipality, structured by
   numeric Line codes.

## Total sheet Line codes (CRITICAL)

The Total sheet uses numeric Line codes to distinguish aggregation levels.
These were reverse-engineered from Addington Highlands and Frontenac Islands:

- **9201**: GPL roll-up **per levy area**. A municipality split into
  multiple levy areas will have multiple 9201 rows. Frontenac Islands has
  one 9201 row for Howe Island and another for Wolfe Island.
- **9299**: GPL roll-up **after aggregation across levy areas**. One row
  per municipality. **This is the correct target** when reconciling GPL
  sums.
- **9401** and **9499**: SRA-LT roll-ups, before and after aggregation.
- **9601** and **9699**: SRA-UT roll-ups, before and after aggregation.

The SPC sheet has its own line codes:

- **9799**: Special Purpose Charges subtotal
- **9910**: Grand total across GPL plus SRA plus SPC (observed as the
  correct grand total)
- **9990**: Alternate grand total, equals 9910 in observed data

When building cross-sheet reconciliation rules, the full chain is:

```
GPL sum  + SRA-LT sum + SRA-UT sum + SPC (line 9799) = SPC line 9910
(9299)     (9499)       (9699)
```

## CVA Assessment column

The CVA Assessment column in GPL is the Current Value Assessment, the full
assessed value before any phase-in adjustment. It can be NaN when the
Phase-In assessment column is zero (exempt or unused sub-classes). It can
be greater than, equal to, or in rare cases less than Phase-In (see Rule 05
discussion above).

## Tax Rate Description column

This column distinguishes between the full-rate row and various
sub-category rows within the same property class:

- "Full Occupied": the main full-rate row for a class
- "Full Occupied, Shared PIL": shared Payment In Lieu row
- "Excess Land": reduced rate for excess land portions
- "Vacant Land": vacant land sub-class
- "Farm. Awaiting Devel. - Ph I": farm awaiting residential development
- "Education Only": education-only levy
- "Small Scale On Farm Business": on-farm business sub-class

When building rules that compare within a class, filter to "Full Occupied"
rows to compare like-for-like. Sub-class rows have their own multipliers
and should not be compared against the main class rate.

## Source regulations and references

- Municipal Act, section 294(1): legal basis for the FIR.
  https://www.ontario.ca/laws/statute/01m25
- O. Reg. 400/98: sets provincial education tax rates by year and class.
- O. Reg. 73/03: graduated tax rates for commercial and industrial.
- O. Reg. 282/98: classification rules for property classes.
- Bill 62 and O. Reg. 330/21: optional small business subclass rates.
- IAAO Standard on Ratio Studies: methodology for assessment quality
  metrics (ASR, COD, PRB, PRD). MPAC uses these for their own quality
  reporting.
- MPAC Assessment Roll Quality Reports: published per municipality,
  demonstrates the kind of output a Data and Quality Assurance Unit
  produces.
  https://www.mpac.ca/en/AboutUs/HowMPACmeasuresqualityandaccuracyresidentialproperties
