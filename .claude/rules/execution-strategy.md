# Execution Strategy

This file describes HOW Claude Code should execute the project, not just
what to build. Read this before starting any new work session. The main
question it answers is "what should I work on next, and why."

## The spiral principle

Do not work breadth-first across all schedules and all years at once.
Do not work depth-first exhausting one schedule before touching another.
Work in a spiral: one narrow vertical slice end-to-end, then widen.

The reasoning: the interviewer will look at the final project for 5 to
15 minutes. What impresses them is (1) one or two genuinely interesting
findings they did not expect, (2) evidence of domain understanding, and
(3) a clean extensible structure. A project with 40 rules across 6
schedules and no interesting findings is worse than a project with 10
rules across 2 schedules and one real anomaly story.

## Phase order (critical)

Phases are not optional. Complete each one before moving to the next.
Do not jump to a later phase because it seems more interesting.

**Phase 0 (DONE)**: Schedule 22 for 2023 only. Single-year rules R01
through R07. Framework established. Loader handles quirks. Engine
writes reports.

**Phase 1**: Schedule 22 for 2022 and 2021 added. Cross-year rules R08
through R10 implemented. This is the next phase to work on.

**Phase 2**: Schedule 26 for 2021, 2022, 2023 added. Cross-schedule
reconciliation rules implemented (GPL plus SRA plus SPC equals
Schedule 26 taxation summary).

**Phase 3**: Schedules 02 and 80 for 2023 added. Peer-group outlier
rules implemented using Tier, MSO region, population band.

**Phase 4**: Dashboard, methodology note, README, tests, deployment.

**Phase 5 (nice to have)**: Schedules 20, 24 added for additional
cross-validation. IAAO ratio study module with simulated data.

## Why years before schedules in Phase 1

Cross-year analysis catches the most dramatic findings (a municipality's
levy jumping 40 percent year-over-year is visually striking and easy to
explain to a non-technical interviewer). Cross-schedule reconciliation
catches subtler findings ($50K discrepancies between roll-up lines) that
require more explanation to land in an interview setting.

Also, cross-year rules are harder to fake. Anyone can write a rule that
checks arithmetic within a single row; it takes real domain work to
decide what "a suspicious year-over-year change" means and to tune
thresholds against real data.

## Why load years sequentially, not all at once

Within Phase 1, load 2022 first, then 2021. Do not load both
simultaneously. Each new year should be treated as an experiment: load
it, run the existing rules, see what changes, then add new rules.

The reason is that loading 2021 and 2022 together and writing
cross-year rules at the same time forces Claude Code to debug the
loader, the rule semantics, and the data quirks all at once. Loading
them sequentially lets each year teach something the previous did not,
and by the time both are loaded the pipeline is solid.

## The "learn and adapt" behavior

This is the most important rule in this file. When loading a new year
or a new schedule, Claude Code must not mechanically apply the existing
rules. It must form hypotheses and revise them.

**After loading any new file, before writing new rules, Claude Code
must do the following**:

1. Run the existing rules on the new file and record the flag counts.
2. Compare flag counts to the previous file. Are they similar? If flag
   counts jumped dramatically in either direction, investigate why
   before proceeding. Sometimes this reveals a rule that worked by
   accident on the first file.
3. Spot-check 3 to 5 flagged rows manually. Do they represent real
   anomalies in the new file? Are any of them false positives caused
   by a quirk of the new year or new schedule that the original file
   did not have?
4. Look for anomalies the existing rules do NOT catch. What would a
   human analyst notice looking at the new file that the current rule
   set would miss? This is where new rules come from.
5. Ask: does this new data change any assumptions from earlier phases?
   If yes, document the change and update affected rules before
   continuing.

If a new file reveals that an earlier rule had a latent bug or an
overly narrow assumption, fix it. Do not layer new logic on top of
broken logic. The framework's credibility depends on every rule being
defensible.

## When to stop analyzing and ship

A common failure mode is analyzing one file too deeply before moving
on. To prevent this, each phase has a concrete "done" signal. Move to
the next phase when you hit the signal, even if you can think of more
things to investigate.

**Phase 1 done when**: Cross-year rules R08 through R10 are
implemented, they have been run on 2021, 2022, 2023, and they have
either (a) caught at least one anomaly that is interesting enough to
tell the interviewer about, or (b) generated zero flags and the user
agrees the framework is tuned correctly. Also: a 1-paragraph summary
of findings is added to `findings.md`.

**Phase 2 done when**: Cross-schedule reconciliation rules are
implemented and tested on the 3 years of data, and the framework can
answer the question "for each municipality, do all the taxation
schedules agree?" with a yes or no flag.

**Phase 3 done when**: At least one peer-group outlier rule is
implemented and has been run on 2023 data, with peer groups computed
from Schedule 02 (Tier, MSO region) and Schedule 80 (population band).

**Phase 4 done when**: The dashboard runs locally, the methodology
note exists at `docs/methodology.md`, the README is written, and at
least one smoke test exists in `tests/`.

## Budget guidance per phase

These are rough targets, not hard limits. If a phase is going over
budget, stop and ask the user whether to push through or ship what
exists.

- Phase 1: 1 to 2 focused sessions. This includes loading 2 new
  years, writing 3 new rules, debugging, and writing the findings
  summary.
- Phase 2: 1 to 2 sessions. Includes loading 1 new schedule across
  3 years, writing 3 reconciliation rules, and debugging.
- Phase 3: 1 to 2 sessions. Includes loading 2 new schedules, writing
  the peer grouping logic, and writing 2 outlier rules.
- Phase 4: 1 session. Dashboard, note, README, tests.

Total: 4 to 7 focused sessions from Phase 0 to Phase 4.

## The deliverable at each phase

After each phase, the project should be **in a shippable state**. That
means: the engine runs end-to-end without errors, the reports are
written, and the README would honestly describe the current
capabilities. If a phase leaves the project in a broken state, finish
the phase before ending the session.

This matters because the application deadline (April 16, 2026) is
fixed. If only Phases 0 and 1 are done by then, that must still be a
coherent project the user can submit.

## Decision log

As the project evolves, Claude Code should maintain a running decision
log at `.claude/rules/decisions.md` (to be created in Phase 1). Each
entry records a non-obvious choice made and the reasoning. Example
entries:

- "Chose line 9299 over 9201 for GPL reconciliation because Frontenac
  Islands has multiple levy areas. See Phase 0 investigation."
- "Chose to downgrade Rule 06 to warning after discovering graduated
  rate exceptions. See O. Reg. 73/03."
- "Chose to handle 2022 Schedule 22 column X differently from 2023
  because the template changed. See Phase 1 loader change."

The decision log is the most valuable artifact for the interview. It
is concrete proof that the user thought through the tradeoffs, not
just ran a checklist.

## Anti-patterns to avoid

1. **Rule inflation**: adding rules without running them first to
   check false positive rates. A rule that has never been tested on
   real data is not a rule, it is a hope.
2. **Schedule hoarding**: downloading 20 schedules before writing a
   single rule that uses the new ones. Download what the next phase
   needs, not everything.
3. **Refactoring before finding**: rewriting the rule engine to be
   more elegant before the framework has caught a single real
   anomaly. Elegance comes after evidence.
4. **Dashboard before rules**: building a Streamlit UI to display
   results before the rule set is rich enough to be worth displaying.
   The dashboard is Phase 4 for a reason.
5. **Depth loop**: spending a whole session investigating one edge
   case in one municipality. Set a 30-minute budget per deep dive
   and move on if it does not yield.
