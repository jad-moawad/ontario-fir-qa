# Ontario FIR Data Quality Framework

A domain-aware data quality framework for Ontario's Financial Information Return (FIR) Schedule 22 property tax data. Built as a portfolio project for a Senior Data and Quality Analyst application to the Ontario Ministry of Finance, Property Tax Services Partnerships Branch. The framework demonstrates what an automated QA pipeline for the ministry's own data might look like: 11 rules across five years (2019-2023), up to 444 municipalities, zero false positives on strict arithmetic checks, and cross-year anomaly detection that caught a municipality filing its entire municipal levy as zero.

**Live dashboard:** https://ontario-fir.streamlit.app

---

## Headline findings

### 1. Northeastern Manitoulin & The Islands (2023): missing municipal levy

Rule R08 (year-over-year levy change) flagged an 83% drop in total levy from $6.16M in 2022 to $1.05M in 2023. Investigation showed that every LT/ST and UT tax rate in the municipality's 2023 submission is exactly 0.0000 across all property classes. The $1.05M represents only the provincial education tax component; the entire municipal levy is absent. No single-year rule can detect this; it required cross-year comparison.

### 2. 2022 Total sheet MunID corruption

Rule R04 (GPL-to-Total-sheet reconciliation) detected that 72 of 441 municipality IDs in the 2022 Schedule 22 Total sheet map to a different municipality name than the GPL sheet. Rather than flood the report with 879 artifact flags, the framework auto-detects the corruption and emits a single diagnostic row explaining the defect. Schedule 26 for 2022 is clean (confirmed by cross-schedule rules R11-R13), placing the corruption squarely in Schedule 22's summary layer.

### 3. Chatham-Kent M 2019: CVA Assessment column defect

Rule R05 (Phase-In <= CVA) flagged 33 rows from a 100,000-population municipality. The residential RT row shows CVA of $45,900 against Phase-In of $6.57B. Investigation confirmed the Phase-In and tax values are internally consistent at the correct 2019 rates ($6.57B x 0.01261 = $82.8M, matching reported taxes exactly). The CVA column holds per-parcel placeholder values instead of class-level totals, leaving $6.5B of assessed value effectively unverifiable in that year's filing.

### 4. Brant County 2023: $12.9M Phase-In excess over CVA

Rule R05 flagged Brant County's Commercial Vacant Land row with CVA of $23.2M but Phase-In of $36.1M. Phase-In should never exceed CVA under Ontario's assessment phase-in mechanism; the $12.9M excess is either a mid-year reclassification, a supplementary assessment that updated Phase-In without updating CVA, or a data entry error. Brant County accounts for five of the nine R05 flags in 2023.

---

## Dashboard

The Streamlit dashboard visualizes all findings. Navigate to any municipality to see its levy trend over 2019-2023 and every flag it carries across all rules. The Summary page includes a province-wide levy change histogram that makes the 2022-2023 acceleration immediately visible.

---

## How it works

Install dependencies:

```bash
pip install -r requirements.txt
```

Single-year mode (R01-R07 on one Schedule 22 file):

```bash
PYTHONPATH=src python3 -m fir_qa.engine data/raw/2023/schedule_22.xlsx reports/2023
```

Expected on 2023 data: R01-R04 zero flags, R05 nine flags, R06 95 flags, R07 one flag.

Cross-year mode (R08 across all years under data/raw/):

```bash
PYTHONPATH=src python3 -m fir_qa.engine cross_year data/raw/ reports/cross_year
```

Expected on 2019-2023 data: R08 six flags across five municipalities.

Cross-schedule mode (R11-R13, reconciling Schedule 22 against Schedule 26):

```bash
PYTHONPATH=src python3 -m fir_qa.engine cross_schedule data/raw/ reports/cross_schedule
```

Expected on clean years: zero real flags. 2022 emits diagnostic skip rows (SPC sheet MunID corruption).

Run tests:

```bash
PYTHONPATH=src pytest tests/test_rules.py -v
```

Launch dashboard locally:

```bash
streamlit run streamlit_app.py
```

---

## Rules implemented

| Rule | Name | Severity | What it checks |
|------|------|----------|----------------|
| R01 | Template arithmetic integrity | error | Phase-In times rate equals reported tax for each tier; TOTAL rate equals sum of components |
| R02 | Residential tax ratio = 1.00 | error | Every residential RT row must carry tax ratio 1.00 (fixed by the Municipal Act) |
| R03 | Standard residential education rate | error | LT/ST residential RT rows must carry the provincial education rate for that year (O. Reg. 400/98) |
| R04 | GPL to Total sheet reconciliation | error | Per-municipality GPL tax sums match Total sheet line 9299; auto-detects MunID column corruption |
| R05 | Phase-In assessment <= CVA | error | Phase-In Taxable Assessment must not exceed Current Value Assessment (Ontario phase-in mechanism) |
| R06 | Within-municipality rate consistency | warning | Non-residential LT/ST rates should equal residential rate times tax ratio; known exceptions for graduated rates (O. Reg. 73/03) and small business subclass (Bill 62) |
| R07 | Property class coverage | warning | Flags municipalities reporting unusually few property classes relative to their tier median |
| R08 | Year-over-year total levy change | warning | Flags municipalities with total levy changes exceeding 25% between consecutive years |
| R11 | Schedule 26 vs S22 grand total | error | Schedule 26-1 line 9199 must match Schedule 22 SPC line 9990 per municipality |
| R12 | SRA-LT reconciliation | error | Sum of SRA-LT rows per municipality must match Total sheet line 9499 |
| R13 | Grand total chain reconciliation | error | GPL (9299) + SRA-LT (9499) + SRA-UT (9699) + SPC (9799) + SPC (7010) = SPC line 9910 |

---

## Limitations and future work

**R06 known false positives.** The within-municipality rate consistency check generates 95 warnings on 2023 data, all from legitimate systematic deviations: graduated commercial/industrial rates (O. Reg. 73/03) and optional small business reductions (Bill 62). The rule is correctly marked warning rather than error. A production version would layer in a by-laws database to distinguish legitimate deviations from actual errors.

**Phase 3 (peer-group outlier rules) deferred.** Schedules 02 and 80 for 2023 are present in the repo but not yet consumed by any rule. The planned rules (R14: effective residential rate vs peer-group median, R15: commercial-to-residential rate ratio vs peer-group) were deferred in favour of completing the Phase 4 dashboard and documentation before the April 2026 application deadline. See `.claude/rules/decisions.md` for the full reasoning.

**Cross-year coverage ends at R08.** Rules R09 (year-over-year effective rate change by class) and R10 (municipality coverage continuity) are specified in the roadmap but not yet implemented.

**No parcel-level ratio study.** The framework operates on municipality-level aggregate data from Schedule 22. An IAAO-standard ratio study (COD, PRD, PRB) requires parcel-level assessment-to-sale ratios. The methodology note at `docs/methodology.md` describes how this module would be structured.

---

## Project layout

```
ontario-fir-qa/
├── src/fir_qa/
│   ├── loader.py               xlsx loader with FIR quirk handling
│   ├── rules.py                single-year rules R01-R07
│   ├── cross_year_rules.py     cross-year rule R08
│   ├── cross_schedule_rules.py cross-schedule rules R11-R13
│   ├── engine.py               CLI runner and report writer
│   └── dashboard.py            Streamlit dashboard
├── streamlit_app.py            Streamlit Cloud entry point
├── data/raw/                   FIR xlsx files 2019-2023 (committed)
├── reports/                    pre-computed CSV outputs (committed for deployment)
├── tests/test_rules.py         pytest smoke tests (33 tests)
├── docs/
│   ├── methodology.md          rule design methodology and IAAO context
│   └── images/                 dashboard screenshots
└── .claude/rules/              extended context and decision log
```

---

## Data

All data from the Ontario Financial Information Return, published by the Ministry of Municipal Affairs and Housing.

> This project uses data from the Ontario Financial Information Return
> published by the Ministry of Municipal Affairs and Housing under the
> [Open Government Licence Ontario](https://www.ontario.ca/page/open-government-licence-ontario).

Source: https://efis.fma.csc.gov.on.ca/fir/index.php/en/open-data/fir-by-schedule-and-year/

---

## License

Code: MIT License. Data: Open Government Licence Ontario.
