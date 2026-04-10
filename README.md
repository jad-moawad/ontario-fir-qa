# Ontario FIR Data Quality Framework

A domain-aware data quality framework for Ontario's Financial Information
Return (FIR) Schedule 22 property tax data. Portfolio project built for a
Senior Data and Quality Analyst application to the Ontario Ministry of
Finance, Property Tax Services Partnerships Branch (Job ID 242142). Uses the
actual data the ministry collects: 444 municipalities, five years
(2019-2023), roughly 35,000 GPL rows per multi-year run.

**Status: Phase 1 complete. Under active development; will be published when
stable.**

---

## Current state

8 QA rules (R01-R08) across 5 years. Zero false positives on strict
single-year arithmetic and rate checks. Six headline findings across the
2019-2023 dataset.

**Top three findings:**

1. Northeastern Manitoulin & The Islands (2023): Rule 08 flagged an 83%
   drop in total levy. Investigation showed every LT/ST and UT tax rate in
   the municipality's 2023 submission is exactly 0.0000; their entire
   municipal levy is absent from the filing.

2. 2022 Total sheet MunID corruption: R04 detected that 72 of 441 MunIDs
   in the 2022 Total sheet map to a different municipality name than the GPL
   sheet, making cross-sheet reconciliation unreliable for that year. The
   framework auto-detects this and skips R04 with a diagnostic row rather
   than flooding the report with 879 artifact flags.

3. Chatham-Kent M 2019 CVA defect: R05 flagged 33 rows from a 100,000-
   population municipality where the CVA Assessment column holds per-parcel
   placeholder values ($45,900 for a class with $6.57B in Phase-In
   assessment). Taxes are internally consistent with Phase-In; CVA is wrong.

---

## How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Single-year mode (runs R01-R07 on one Schedule 22 file):

```bash
PYTHONPATH=src python3 -m fir_qa.engine data/raw/2023/schedule_22.xlsx reports/2023
```

Expected output on 2023: R01-R04 0 flags, R05 9 flags, R06 95 flags, R07 1 flag.

Cross-year mode (runs R08+ across all years found under data/raw/):

```bash
PYTHONPATH=src python3 -m fir_qa.engine cross_year data/raw/ reports/cross_year
```

Expected output: R08 6 flags across 5 municipalities (2019-2023 dataset).

Reports are written as CSV files to the specified output directory.

---

## Data

FIR Schedule 22 data for 2019-2023 downloaded from the Ontario Open Data
portal under the Open Government Licence Ontario.

> This project uses data from the Ontario Financial Information Return
> published by the Ministry of Municipal Affairs and Housing under the
> Open Government Licence Ontario.
> https://www.ontario.ca/page/open-government-licence-ontario
