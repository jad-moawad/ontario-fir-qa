# Roadmap

This file lists the priorities for continuing the project, roughly ordered
by value-for-effort. The project is v1 as of the handoff: 7 rules, runner,
report writer, all passing without false positives on strict checks.

## Priority 1: Cross-year rules

The richest source of quality signal in panel data is year-over-year
consistency. Single-year checks cannot detect sudden jumps in assessment
or levy, which are the most common real-world data quality issue. Need at
least 2022 Schedule 22 to implement these; ideally also 2021 and 2020 for
richer trend analysis.

**Data needed**: Schedule 22 for 2022 from the FIR portal. Save at
`data/raw/2022/schedule_22.xlsx`. URL in data-sources.md.

**Architectural decision**: Cross-year rules have a different signature
from single-year rules. They take a dict of year to sheets dict rather
than a single sheets dict. Options:

1. New module `src/fir_qa/cross_year_rules.py` with its own decorator and
   runner. Cleaner separation but requires engine changes to dispatch to
   the right runner.
2. Extend the existing rules module so rule functions can optionally
   accept a year parameter and the engine loops over years. Simpler but
   mixes concerns.

Recommendation: option 1. Keep single-year rules in rules.py, cross-year
rules in cross_year_rules.py, and add a `run_cross_year` function to
engine.py that loads all available years and dispatches to cross-year
rules. The engine CLI accepts a data directory rather than a single file.

**Rules to implement**:

- **Rule 08: Year-over-year total levy change (warning)**. For each
  municipality, compute the percent change in TOTAL taxes from year N to
  year N+1. Flag changes outside plus or minus 25 percent. The threshold
  is configurable. Rationale: typical year-over-year changes are in the
  single digits due to assessment growth and rate changes; anything
  larger is a candidate for review.
- **Rule 09: Year-over-year effective rate change by class (warning)**.
  Compute levy divided by Phase-In assessment per (MunID, Property
  Class) for each year. Flag (MunID, Property Class) pairs where the
  effective rate changed by more than plus or minus 20 percent between
  adjacent years.
- **Rule 10: Municipality coverage continuity (error)**. Municipalities
  present in year N but absent in year N+1 (excluding known restructuring
  events). Municipal restructuring does happen in Ontario, so the rule
  should be a warning with a "known exceptions" escape hatch.

## Priority 2: Cross-sheet reconciliation

Currently Rule 04 only reconciles GPL. The full reconciliation chain
needs to verify that GPL + SRA-LT + SRA-UT + SPC adds up to the grand
total. This is the most important check in a real QA pipeline because it
catches cases where a municipality reports a levy on one sheet but the
roll-up mechanism fails.

**Rules to implement**:

- **Rule 11: SRA-LT reconciliation (error)**. Sum of SRA-LT rows per
  municipality equals Total sheet line 9499 (the post-aggregation SRA-LT
  total).
- **Rule 12: SRA-UT reconciliation (error)**. Same for SRA-UT against
  line 9699.
- **Rule 13: Grand total reconciliation (error)**. GPL (line 9299) plus
  SRA-LT (line 9499) plus SRA-UT (line 9699) plus SPC (line 9799) equals
  SPC line 9910 per municipality. This is the canonical "did the
  spreadsheet add up" check.

## Priority 3: Peer-group outlier rules

Need Schedule 02 (Municipal Data, for Tier and MSO region metadata) and
Schedule 80 (Statistical Information, for population). Peer groups are
defined as (Tier, MSO, population band).

**Data needed**: Schedule 02 for 2023 and Schedule 80 for 2023.

**Rules to implement**:

- **Rule 14: Effective residential tax rate peer outlier (warning)**.
  For each peer group, compute the median effective residential tax
  rate and the MAD. Flag municipalities whose effective residential rate
  is more than 2.5 MAD from the peer median.
- **Rule 15: Commercial-to-residential ratio peer outlier (warning)**.
  Same structure, but for the ratio of effective commercial to
  residential rate.

Use robust statistics (median, MAD) rather than mean and standard
deviation. Property tax data has heavy tails and a few extreme values
can distort mean-based thresholds.

## Priority 4: Dashboard and writeup

Once the rule set is richer and the project has cross-year coverage:

- **Streamlit dashboard** at `src/fir_qa/dashboard.py`. Loads the report
  CSVs and lets the user pick a municipality to see all flags for that
  municipality across all rules. Streamlit chosen for simplicity. Ship
  with a `streamlit run src/fir_qa/dashboard.py` command in the README.
- **Methodology note** at `docs/methodology.md`. 2 to 3 pages covering
  the rule set structure, the IAAO ratio study vocabulary (ASR, COD,
  PRB, PRD), and how the framework would plug into a ratio study workflow
  if parcel-level sales data became available. References to O. Reg.
  400/98, O. Reg. 73/03, and MPAC documentation.
- **README.md** at project root: one paragraph description, run
  instructions, link to CLAUDE.md for full context. Keep it short; the
  reader should be able to run the project in under 2 minutes.
- **LICENSE**: MIT or Apache 2.0. User preference unknown, default to
  MIT.
- **.gitignore**: standard Python, plus `reports/` and `data/raw/`
  (data files are downloaded, not committed).
- **pytest smoke tests** at `tests/test_rules.py`. At minimum: load the
  2023 file, run `run_all`, assert each rule returns a DataFrame without
  raising. Optionally: assert specific known flag counts.

## Priority 5: IAAO ratio study module

Implement COD, PRD, PRB as standalone functions in
`src/fir_qa/ratio_study.py`. Even without real parcel-level data, showing
that the framework can hook into IAAO-compliant ratio study metrics is
the single strongest domain signal in the project.

**Implementation**:

```python
def coefficient_of_dispersion(ratios):
    median = np.median(ratios)
    return 100 * np.mean(np.abs(ratios - median)) / median

def price_related_differential(ratios, assessments):
    mean_ratio = np.mean(ratios)
    weighted_mean = np.sum(ratios * assessments) / np.sum(assessments)
    return mean_ratio / weighted_mean

def price_related_bias(ratios, sale_prices):
    # IAAO formula: regression of ratio on log-sale-price
    from scipy.stats import linregress
    ln_price = np.log(sale_prices)
    slope, intercept, _, _, _ = linregress(ln_price, ratios)
    return slope
```

Include a demo script that runs the three metrics on a simulated dataset
and writes output in the same format as a ratio study report.

Reference: IAAO Standard on Ratio Studies, which MPAC cites in its own
assessment quality reports at
https://www.mpac.ca/en/AboutUs/HowMPACmeasuresqualityandaccuracyresidentialproperties

## Priority 6: Production hardening (only if time permits)

Nice-to-have items that demonstrate engineering maturity but are not
critical for the interview:

- Logging via Python `logging` module instead of print statements
- Type hints throughout (already partial)
- Config file for tolerances and thresholds instead of constants
- Parallel processing for cross-year runs over many years
- Known exceptions CSV for Rule 06 (per-municipality legitimate deviations)

## Decisions for user to confirm before Priority 1

Before starting cross-year work, confirm these with the user:

1. **Engine signature**: should `run_cross_year` be a separate command in
   engine.py (`python -m fir_qa.engine cross_year data/raw reports/xyear`)
   or a new module `src/fir_qa/cross_year_engine.py`?
2. **Year range**: what years should cross-year rules operate on? The
   simplest is "all years found under data/raw/" but that requires
   handling partial years like 2024.
3. **Threshold tuning**: the plus or minus 25 percent threshold for Rule
   08 is an initial guess. Once data is loaded we can look at the
   empirical distribution and pick a calibrated threshold.
4. **Report format for cross-year rules**: each rule writes its own CSV
   (as now) or a single combined `cross_year_flags.csv`?

## Timeline considerations

Application closes April 16 2026. Current state as of handoff:

- v1 complete: 7 rules, runner, reports. Ready to ship as-is.
- v2 target (cross-year rules): 2 focused work sessions
- v3 target (cross-sheet reconciliation, peer-group outliers, dashboard):
  3 to 5 work sessions

If time is short, prioritize: cross-year rules (Priority 1), then skip
straight to dashboard and writeup (Priority 4). Cross-sheet reconciliation
(Priority 2) is more elegant but catches fewer dramatic findings than
cross-year rules.
