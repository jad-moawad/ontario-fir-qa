# Data Sources

This file lists all the URLs for downloading Ontario FIR data and supporting
references. All data is free and licensed under the Open Government Licence
Ontario, which permits publication in the project repo (though the project
should download rather than commit data files to keep the repo small).

## Primary FIR data portal

**FIR by Schedule and Year** (the download format the project uses).
Click individual schedule and year cells to download xlsx files:
https://efis.fma.csc.gov.on.ca/fir/index.php/en/open-data/fir-by-schedule-and-year/

**Main landing page** on Ontario Open Data:
https://data.ontario.ca/dataset/financial-information-return-fir-for-municipalities

**About the FIR** (background on the data collection process, template
structure, and submission deadlines):
https://efis.fma.csc.gov.on.ca/fir/index.php/en/financial-information-return-en/

## Schedules to download, in priority order

### Immediate priority (for cross-year rules)

- **Schedule 22 for 2022**: Save at `data/raw/2022/schedule_22.xlsx`.
  Unlocks Rules 08 through 10 (cross-year rules).
- **Schedule 22 for 2021**: Save at `data/raw/2021/schedule_22.xlsx`.
  Enables 3-year trend analysis.
- **Schedule 22 for 2020**: Save at `data/raw/2020/schedule_22.xlsx`.
  Enables 4-year trend analysis.

Note: 2024 Schedule 22 is partial as of the April 2026 download (only
about 95 of 444 municipalities posted so far). Handle gracefully if used.
2025 is not yet collected (deadline May 31, 2026).

### Medium priority (for peer-group and reconciliation rules)

- **Schedule 02 for 2023** (Municipal Data): Save at
  `data/raw/2023/schedule_02.xlsx`. Provides Tier, MSO region, upper-tier
  parent for peer grouping.
- **Schedule 80 for 2023** (Statistical Information): Save at
  `data/raw/2023/schedule_80.xlsx`. Provides population and household
  counts for peer grouping by size.
- **Schedule 20 for 2023** (Taxation Information): alternative source of
  tax rate data. Useful for cross-validation against Schedule 22.
- **Schedule 24 for 2023** (Payments-In-Lieu of Taxation): for PILT
  reconciliation rules.
- **Schedule 26 for 2023** (Taxation and Payments-In-Lieu Summary):
  master reconciliation target across all taxation schedules.

### Low priority (for completeness)

- Schedules 10, 12 (Revenues, Grants and Fees): for broader financial
  context, not directly needed for property tax QA.

## Download workflow

The FIR portal uses JavaScript-driven download links that can be tedious
to click one at a time. Options:

1. **Manual clicking** in the browser. Slow but foolproof. For 6
   (schedule, year) pairs that's 6 clicks.
2. **wget with the direct URL**. The download links follow a predictable
   pattern once you inspect one. Example command structure (verify the
   exact URL by right-clicking a download link in the browser):
   ```bash
   wget -O data/raw/2022/schedule_22.xlsx \
     "https://efis.fma.csc.gov.on.ca/fir/odsfir/MultiYearReport/{year}/{schedule}.xlsx"
   ```
3. **Ask Claude Code to download them** using its fetch capability and
   the URL pattern.

## Supporting references for methodology writeup

These are not data sources but are needed when writing the methodology
note and cover letter.

**Legal basis**:
- Municipal Act section 294(1): legal requirement for the FIR.
  https://www.ontario.ca/laws/statute/01m25

**Assessment quality and IAAO standards** (central to the project's
interview pitch):
- MPAC page on how they measure assessment quality using IAAO metrics:
  https://www.mpac.ca/en/AboutUs/HowMPACmeasuresqualityandaccuracyresidentialproperties
- MPAC 2022 Vertical Equity Review (excellent example of a ratio study
  writeup, useful as a template for the methodology note):
  https://www.mpac.ca/sites/default/files/docs/pdf/VerticalEquityReviewofResidentialAssessedValues.pdf

**Ontario tax policy regulations** (cited in rule docstrings):
- O. Reg. 400/98: provincial education tax rates by year and class
- O. Reg. 73/03: graduated tax rates for commercial and industrial
- O. Reg. 282/98: property class definitions
- O. Reg. 330/21: small business subclass (Bill 62)
- All regulations are searchable at https://www.ontario.ca/laws

## Ministry organizational context

For the cover letter and interview prep:

**Ministry of Finance organizational chart**:
- Provincial Local Finance Division
  - Property Tax Services Partnerships Branch
    - Data and Quality Assurance Unit (newly established, this is the
      team hiring)

**Related Crown corporations and agencies** that the team will interact
with:
- **MPAC** (Municipal Property Assessment Corporation): assesses all
  Ontario properties. Not a government agency; an independent non-profit
  corporation funded by municipalities.
- **Ministry of Municipal Affairs and Housing (MMAH)**: collects the
  FIR. The Data and Quality Assurance Unit at MoF works with FIR data
  that MMAH collects.
- **Assessment Review Board**: hears appeals of MPAC assessments.

## Licensing and attribution

All FIR data is licensed under the Open Government Licence Ontario:
https://www.ontario.ca/page/open-government-licence-ontario

This permits copying, modifying, publishing, and distributing the data,
including for commercial purposes, as long as the source is attributed.
The project repo should include an attribution line in the README.md:

> This project uses data from the Ontario Financial Information Return
> published by the Ministry of Municipal Affairs and Housing under the
> Open Government Licence Ontario.

Code in the project (the src/fir_qa/ directory) can be licensed
independently under MIT or Apache 2.0. Default recommendation is MIT for
permissive reuse.
