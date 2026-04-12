"""
Ontario FIR QA Dashboard.

Loads pre-computed report CSVs from reports/ and displays findings.
Does NOT re-run rules at startup; the engine must be run separately to
generate the CSVs that this dashboard reads.

Entry point for Streamlit Cloud is streamlit_app.py at the project root.
Run locally with:

    streamlit run streamlit_app.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"

SEVERITY_COLOUR = {"error": "#d62728", "warning": "#ff7f0e"}
SEVERITY_EMOJI = {"error": "🔴", "warning": "🟡"}

RULE_DESCRIPTIONS = {
    "R01": "Template arithmetic integrity",
    "R02": "Residential tax ratio = 1.00",
    "R03": "Standard residential education rate",
    "R04": "GPL to Total sheet reconciliation",
    "R05": "Phase-In assessment <= CVA",
    "R06": "Within-municipality rate consistency",
    "R07": "Property class coverage",
    "R08": "Year-over-year total levy change",
    "R11": "Schedule 26 vs S22 grand total",
    "R12": "SRA-LT vs Total sheet line 9499",
    "R13": "Grand total chain reconciliation",
}

SINGLE_YEARS = [2019, 2020, 2021, 2022, 2023]


# ---------------------------------------------------------------------------
# Data loaders (cached so Streamlit only reads CSV on first load)
# ---------------------------------------------------------------------------

@st.cache_data
def load_single_year_summary() -> pd.DataFrame:
    frames = []
    for year in SINGLE_YEARS:
        path = REPORTS_DIR / str(year) / "summary.csv"
        if path.exists():
            df = pd.read_csv(path)
            df.insert(0, "year", year)
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data
def load_single_year_flags() -> pd.DataFrame:
    frames = []
    for year in SINGLE_YEARS:
        year_dir = REPORTS_DIR / str(year)
        if not year_dir.exists():
            continue
        for csv_path in sorted(year_dir.glob("R*_flags.csv")):
            df = pd.read_csv(csv_path)
            df.insert(0, "year", year)
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data
def load_cross_year_flags() -> pd.DataFrame:
    path = REPORTS_DIR / "cross_year" / "R08_flags.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def load_cross_year_summary() -> pd.DataFrame:
    path = REPORTS_DIR / "cross_year" / "cross_year_summary.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def load_cross_schedule_summary() -> pd.DataFrame:
    path = REPORTS_DIR / "cross_schedule" / "cross_schedule_summary.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def load_cross_schedule_flags() -> pd.DataFrame:
    frames = []
    cs_dir = REPORTS_DIR / "cross_schedule"
    if not cs_dir.exists():
        return pd.DataFrame()
    for csv_path in sorted(cs_dir.glob("*_R1*_flags.csv")):
        df = pd.read_csv(csv_path)
        year_str = csv_path.stem.split("_")[0]
        try:
            df.insert(0, "year", int(year_str))
        except ValueError:
            pass
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data
def load_levy_series() -> pd.DataFrame:
    """Total levy per municipality per year, pre-computed by the engine."""
    path = REPORTS_DIR / "levy_series.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def load_levy_yoy_pct() -> pd.DataFrame:
    path = REPORTS_DIR / "levy_yoy_pct.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Page: Summary
# ---------------------------------------------------------------------------

def page_summary() -> None:
    st.header("QA Summary")
    st.caption(
        "Flag counts per rule across all years. "
        "Errors are definitive anomalies; warnings are candidates for review."
    )

    sy = load_single_year_summary()
    cy = load_cross_year_summary()
    cs = load_cross_schedule_summary()

    # --- Single-year rules ---
    st.subheader("Single-year rules (R01 to R07)")
    if sy.empty:
        st.info("No single-year report CSVs found under reports/.")
    else:
        pivot = sy.pivot_table(
            index=["rule_id", "rule_name", "severity"],
            columns="year",
            values="n_flags",
            aggfunc="sum",
        ).reset_index()
        pivot.columns.name = None

        def _fmt_sev(s):
            c = SEVERITY_COLOUR.get(s, "#888")
            return f'<span style="color:{c};font-weight:600">{s}</span>'

        pivot["severity"] = pivot["severity"].apply(_fmt_sev)
        st.write(pivot.to_html(escape=False, index=False), unsafe_allow_html=True)

    # --- Cross-year rules ---
    st.subheader("Cross-year rules (R08)")
    if cy.empty:
        st.info("No cross-year summary found.")
    else:
        st.dataframe(cy, use_container_width=True, hide_index=True)

    # --- Cross-schedule rules ---
    st.subheader("Cross-schedule rules (R11 to R13)")
    if cs.empty:
        st.info("No cross-schedule summary found.")
    else:
        pivot_cs = cs.pivot_table(
            index=["rule_id", "rule_name", "severity"],
            columns="year",
            values="n_flags",
            aggfunc="sum",
        ).reset_index()
        pivot_cs.columns.name = None
        st.dataframe(pivot_cs, use_container_width=True, hide_index=True)

    # --- YoY levy change distribution histogram ---
    st.divider()
    st.subheader("Province-wide levy change distribution")
    st.caption(
        "Distribution of year-over-year total levy percent changes across all "
        "municipalities, by consecutive year-pair. The 2022-2023 bar is "
        "noticeably wider and shifted right, reflecting the province-wide "
        "inflation-driven levy acceleration documented in the cross-year analysis."
    )

    yoy = load_levy_yoy_pct()
    if yoy.empty:
        st.info("Levy change data not found. Run: PYTHONPATH=src python /tmp/diag_histogram.py")
    else:
        clip_lo, clip_hi = -25.0, 25.0
        bin_edges = list(range(int(clip_lo), int(clip_hi) + 5, 5))
        bin_labels = [f"{b}%" for b in bin_edges[:-1]]

        hist_rows = []
        for pair in sorted(yoy["year_pair"].unique()):
            sub = yoy.loc[yoy["year_pair"] == pair, "pct_change"].clip(clip_lo, clip_hi - 0.01)
            counts, _ = np.histogram(sub, bins=bin_edges)
            for label, count in zip(bin_labels, counts):
                hist_rows.append({"bucket": label, pair: int(count)})

        hist_df = pd.DataFrame({"bucket": bin_labels})
        for pair in sorted(yoy["year_pair"].unique()):
            pair_data = {r["bucket"]: r[pair] for r in hist_rows if pair in r}
            hist_df[pair] = hist_df["bucket"].map(pair_data).fillna(0).astype(int)

        hist_df = hist_df.set_index("bucket")
        st.bar_chart(hist_df, use_container_width=True)
        st.caption(
            f"Values clipped to [{clip_lo}%, {clip_hi}%] for readability. "
            "Northeastern Manitoulin (-83%, 2022-2023) and Chatham-Kent M "
            "(data defect, 2019) fall outside this range."
        )

    # --- Province-wide headline numbers ---
    st.divider()
    total_errors = 0
    total_warnings = 0
    if not sy.empty:
        total_errors += int(sy.loc[sy["severity"] == "error", "n_flags"].sum())
        total_warnings += int(sy.loc[sy["severity"] == "warning", "n_flags"].sum())
    if not cy.empty:
        total_warnings += int(cy.loc[cy["severity"] == "warning", "n_flags"].sum())

    col1, col2, col3 = st.columns(3)
    col1.metric("Years covered", len(SINGLE_YEARS))
    col2.metric("Total errors", total_errors, delta_color="inverse")
    col3.metric("Total warnings", total_warnings, delta_color="inverse")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_levy_chart(municipality: str, levy: pd.DataFrame) -> None:
    """Render total levy trend chart for one municipality."""
    if levy.empty or "Municipality" not in levy.columns:
        return
    mun_levy = levy[levy["Municipality"] == municipality][["year", "total_levy"]].copy()
    if mun_levy.empty:
        return

    mun_levy = mun_levy.sort_values("year")
    mun_levy["total_levy_M"] = mun_levy["total_levy"] / 1_000_000
    # Use string years as the index so Streamlit renders "2019", "2020" etc.
    # without decimal points or thousands separators.
    mun_levy["year_label"] = mun_levy["year"].astype(str)
    chart_df = mun_levy.set_index("year_label")[["total_levy_M"]]

    st.subheader("Total levy 2019-2023 (all property classes, $M)")
    st.line_chart(chart_df)
    st.caption(
        "Sum of TOTAL Taxes across all GPL rows. "
        "Includes LT/ST, UT, and education components."
    )
    # Precise figures table
    table_df = mun_levy[["year", "total_levy", "total_levy_M"]].rename(
        columns={"year": "Year", "total_levy": "Total Levy ($)", "total_levy_M": "($M)"}
    ).copy()
    table_df["Total Levy ($)"] = table_df["Total Levy ($)"].apply(lambda x: f"${x:,.0f}")
    table_df["($M)"] = table_df["($M)"].apply(lambda x: f"${x:.2f}M")
    st.dataframe(table_df, use_container_width=False, hide_index=True)
    st.divider()


# ---------------------------------------------------------------------------
# Page: Municipality detail
# ---------------------------------------------------------------------------

def page_municipality() -> None:
    st.header("Municipality detail")
    st.caption(
        "Select a municipality to see every flag across all rules and years, "
        "plus the total levy trend over 2019-2023."
    )

    flags = load_single_year_flags()
    cy_flags = load_cross_year_flags()
    levy = load_levy_series()

    # Build union of flagged municipality names from all sources
    mun_names: set[str] = set()
    if not flags.empty and "Municipality" in flags.columns:
        mun_names.update(flags["Municipality"].dropna().unique())
    if not cy_flags.empty and "Municipality" in cy_flags.columns:
        mun_names.update(cy_flags["Municipality"].dropna().unique())

    selected = st.selectbox(
        "Municipality", sorted(mun_names), index=None, placeholder="Choose..."
    )
    if selected is None:
        return

    # --- Collect all flags first so the banner count is available ---
    all_flag_frames = []

    if not flags.empty and "Municipality" in flags.columns:
        sy_mun = flags[flags["Municipality"] == selected].copy()
        if not sy_mun.empty:
            all_flag_frames.append(sy_mun)

    if not cy_flags.empty and "Municipality" in cy_flags.columns:
        cy_mun = cy_flags[cy_flags["Municipality"] == selected].copy()
        if not cy_mun.empty:
            # R08 rows don't have a plain "year" column (they have year_from/year_to),
            # so add a display year = year_to so it sorts sensibly with single-year rows
            if "year" not in cy_mun.columns and "year_to" in cy_mun.columns:
                cy_mun.insert(0, "year", cy_mun["year_to"])
            all_flag_frames.append(cy_mun)

    if not all_flag_frames:
        st.info(f"{selected} has no flags across any rule or year.")
        # Still show levy chart for clean municipalities
        _render_levy_chart(selected, levy)
        return

    all_flags_df = pd.concat(all_flag_frames, ignore_index=True)
    n_flags = len(all_flags_df)
    n_rules = all_flags_df["rule_id"].nunique()

    # Banner: immediate context before the chart
    st.info(f"{selected} has {n_flags} flag(s) across {n_rules} rule(s).")

    # Levy trend chart
    _render_levy_chart(selected, levy)

    st.subheader(f"Flags for {selected}")
    st.caption(
        f"{len(all_flags_df)} flag(s) across "
        f"{all_flags_df['rule_id'].nunique()} rule(s)."
    )

    for rule_id, grp in all_flags_df.groupby("rule_id"):
        sev = grp["severity"].iloc[0]
        icon = SEVERITY_EMOJI.get(sev, "")
        label = RULE_DESCRIPTIONS.get(rule_id, rule_id)
        with st.expander(
            f"{icon} {rule_id}: {label}  ({len(grp)} flag(s))", expanded=True
        ):
            display_cols = [
                c for c in grp.columns
                if c not in {"rule_id", "rule_name", "severity"}
            ]
            # Drop columns that are entirely NaN within this rule's rows
            # so R05 doesn't show R08-only columns (and vice versa).
            display_df = (
                grp[display_cols]
                .dropna(axis=1, how="all")
                .reset_index(drop=True)
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Page: Rule detail
# ---------------------------------------------------------------------------

def page_rule() -> None:
    st.header("Rule detail")
    st.caption("Select a rule to see every flagged municipality.")

    all_rule_ids = sorted(RULE_DESCRIPTIONS.keys())
    rule_id = st.selectbox(
        "Rule",
        all_rule_ids,
        format_func=lambda r: f"{r}: {RULE_DESCRIPTIONS[r]}",
        index=None,
        placeholder="Choose a rule...",
    )
    if rule_id is None:
        return

    if rule_id == "R08":
        df = load_cross_year_flags()
    elif rule_id in ("R11", "R12", "R13"):
        df = load_cross_schedule_flags()
        if not df.empty:
            df = df[df["rule_id"] == rule_id]
    else:
        df = load_single_year_flags()
        if not df.empty:
            df = df[df["rule_id"] == rule_id]

    if df is None or df.empty:
        st.success(f"{rule_id} produced no flags.")
        return

    sev = df["severity"].iloc[0]
    icon = SEVERITY_EMOJI.get(sev, "")

    # Separate real flags from diagnostic skip rows (skip rows have MunID = NaN)
    if "MunID" in df.columns:
        skip_rows = df[df["MunID"].isna()]
        real_rows = df[df["MunID"].notna()]
    else:
        skip_rows = pd.DataFrame()
        real_rows = df

    # Render skip/diagnostic rows as prominent callouts, not truncated table cells
    if not skip_rows.empty:
        for _, row in skip_rows.iterrows():
            year_label = f" (year {int(row['year'])})" if "year" in row and pd.notna(row.get("year")) else ""
            st.warning(
                f"**{rule_id} diagnostic{year_label}:** {row.get('detail', 'No detail available.')}"
            )

    if real_rows.empty:
        st.info(f"{rule_id} produced no real flags (only diagnostic skip rows above).")
        return

    st.markdown(
        f"**{icon} Severity:** {sev} &nbsp;|&nbsp; "
        f"**Real flags:** {len(real_rows)} &nbsp;|&nbsp; "
        f"**Municipalities:** {real_rows['Municipality'].nunique() if 'Municipality' in real_rows.columns else 'n/a'}",
        unsafe_allow_html=True,
    )

    display_cols = [
        c for c in real_rows.columns if c not in {"rule_id", "rule_name", "severity"}
    ]
    st.dataframe(
        real_rows[display_cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )

    csv_bytes = df.to_csv(index=False).encode()
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name=f"{rule_id}_flags.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Page: About
# ---------------------------------------------------------------------------

def page_about() -> None:
    st.header("About this project")

    st.markdown("""
This dashboard is a portfolio project for the Ontario Ministry of Finance,
Property Tax Services Partnerships Branch, Data and Quality Assurance Unit
(Senior Data and Quality Analyst, Job ID 242142). It demonstrates the kind
of automated QA pipeline a Data and Quality Assurance Unit might build on
day one, using the actual Financial Information Return data the Ministry
collects.

---

### What the framework does

The framework loads Ontario FIR Schedule 22 filings for 444 municipalities
across five years (2019 to 2023) and runs 11 domain-aware quality assurance
rules. Rules are organized into three categories:

- **Single-year rules (R01 to R07)**: check arithmetic identities, statutory
  rate requirements, and internal consistency within a single year's file.
- **Cross-year rules (R08)**: compare consecutive years to detect anomalous
  levy jumps that no single-year rule can see.
- **Cross-schedule rules (R11 to R13)**: reconcile Schedule 22 against the
  separately-filed Schedule 26 to confirm that the two independent filings agree.

---

### Key findings

**1. Northeastern Manitoulin & The Islands (2023):** Rule R08 flagged an
83% drop in total levy from $6.16M in 2022 to $1.05M in 2023. Investigation
showed every LT/ST and UT tax rate is exactly 0.0000 in the 2023 submission.
The entire municipal levy is absent from the FIR. No single-year rule could
catch this; it required cross-year comparison.

**2. 2022 Total sheet MunID corruption:** R04 detected that the MunID column
in the 2022 Schedule 22 Total sheet is corrupted (72 of 441 municipalities
have the wrong ID). The rule automatically skips 2022 and emits a diagnostic
row instead of 879 misleading error flags. Schedule 26 for 2022 is clean,
confirming the corruption is confined to Schedule 22's summary layer.

**3. Chatham-Kent M 2019:** R05 flagged 33 rows where CVA Assessment contains
per-parcel placeholder values instead of class-level totals, leaving $6.5B
of assessed value unverified in that year's filing.

**4. Brant County 2023:** R05 flagged Commercial Vacant Land with $12.9M of
Phase-In assessment exceeding CVA, which is structurally impossible under
Ontario's phase-in mechanism.

---

### Domain calibration notes

Rules R01 through R04 returning zero flags is the correct outcome for a
healthy file. The FIR template enforces arithmetic identities via cell
formulas and provincial regulation sets residential ratios and education rates.
These rules exist as canaries: if they ever fire, something structural has broken.

Rule R06 generates 95 warnings because Ontario permits graduated tax rates
(O. Reg. 73/03) and optional small business subclass reductions (Bill 62)
that produce legitimate deviations from the multiplicative rate identity.
The rule is marked warning with documented limitations rather than error,
demonstrating that false positive management matters as much as detection.

---

### Data

All data is from the Ontario Financial Information Return, published by the
Ministry of Municipal Affairs and Housing under the
[Open Government Licence Ontario](https://www.ontario.ca/page/open-government-licence-ontario).

---

### Technical stack

Python 3.10+, pandas, Streamlit. No database; all computation runs against
xlsx files from the FIR open data portal. Rules, loaders, and engine are in
`src/fir_qa/`. The dashboard reads pre-computed CSVs from `reports/`.
Source code: [github.com/jadmoawad/ontario-fir-qa](https://github.com/jadmoawad/ontario-fir-qa)
    """)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Ontario FIR QA",
        page_icon=":bar_chart:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.title("Ontario FIR QA")
    st.sidebar.caption("Data and Quality Assurance Framework")

    pages = {
        "Summary": page_summary,
        "Municipality detail": page_municipality,
        "Rule detail": page_rule,
        "About": page_about,
    }

    choice = st.sidebar.radio("Navigate", list(pages.keys()))
    st.sidebar.divider()
    st.sidebar.caption(
        "Rules: R01-R07 (single-year), R08 (cross-year), R11-R13 (cross-schedule)"
    )
    st.sidebar.caption(
        "Years: 2019-2023 | Municipalities: up to 444"
    )

    pages[choice]()


if __name__ == "__main__":
    main()
