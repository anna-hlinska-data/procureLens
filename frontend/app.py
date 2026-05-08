import streamlit as st
import pandas as pd
import os
from pathlib import Path
import shutil

from csv_converter import convert_to_csv, FileTypeFlags
from mapping import prepare_headers
from cleaning import clean_data
from risk_engine import analyse_contracts, risk_summary

# =============================================================================
# CONFIG & FOLDERS
# =============================================================================

st.set_page_config(
    page_title="Procurement Data Pipeline",
    page_icon="📦",
    layout="wide"
)

FOLDERS = {
    "input": "input_files",
    "original": "original_files",
    "converted": "converted_csv",
    "mapped": "mapped_files",
    "cleaned": "cleaned_files",
}

for folder in FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

# =============================================================================
# SESSION STATE
# =============================================================================

DEFAULT_STATE = {
    "step": 0,
    "uploaded_file": None,
    "file_path": None,
    "file_flags": None,
    "csv_path": None,
    "raw_df": None,
    "mapped_df": None,
    "cleaned_df": None,
    "mapped_out": None,
    "cleaned_out": None,
    "risk_df": None,
    "risk_stats": None,
}

for k, v in DEFAULT_STATE.items():
    st.session_state.setdefault(k, v)

# =============================================================================
# HEADER
# =============================================================================

st.title("🔍 EU ProcureLens — Procurement Risk Detection")
st.caption("Upload → Convert → Map → Clean → Export → Risk Analysis")

STEPS = ["Upload", "Convert", "Map", "Clean", "Export", "Risk Analysis"]
st.progress((st.session_state.step + 1) / len(STEPS))
st.caption(f"Step {st.session_state.step + 1} of {len(STEPS)} — {STEPS[st.session_state.step]}")

# =============================================================================
# SIDEBAR CONTROLS
# =============================================================================

with st.sidebar:
    st.header("⚙️ Cleaning Options")

    missing_threshold = st.slider(
        "Drop columns with > X% missing",
        0.0, 1.0, 0.5, 0.05
    )

    fill_method = st.selectbox(
        "Fill missing values using",
        ["median", "mean", "drop"]
    )

    st.divider()

    if st.button("🔄 Reset Pipeline"):
        for k in DEFAULT_STATE:
            st.session_state[k] = DEFAULT_STATE[k]
        st.rerun()

# =============================================================================
# TABS
# =============================================================================

tab_upload, tab_convert, tab_map, tab_clean, tab_export, tab_risk = st.tabs(
    ["📤 Upload", "🔄 Convert", "🧠 Map", "🧹 Clean", "📥 Export", "🔍 Risk Analysis"]
)

# =============================================================================
# TAB 1 — UPLOAD
# =============================================================================

with tab_upload:
    st.subheader("📤 Upload Procurement File")

    uploaded = st.file_uploader(
        "Supported formats: CSV, Excel, PDF, Image",
        type=["csv", "xlsx", "xls", "pdf", "jpg", "jpeg", "png", "tiff", "bmp"]
    )

    if uploaded:
        st.session_state.uploaded_file = uploaded
        file_path = os.path.join(FOLDERS["input"], uploaded.name)

        with open(file_path, "wb") as f:
            f.write(uploaded.getbuffer())

        st.session_state.file_path = file_path
        st.session_state.file_flags = FileTypeFlags(file_path)

        shutil.copy(file_path, os.path.join(FOLDERS["original"], uploaded.name))

        with st.container(border=True):
            st.markdown("### 📄 File Summary")
            st.write(f"**Name:** {uploaded.name}")
            st.write(f"**Size:** {uploaded.size / 1024:.1f} KB")

            flags = st.session_state.file_flags
            if flags.is_csv:
                st.success("CSV detected — fast processing")
            elif flags.is_excel:
                st.info("Excel detected — converting to CSV")
            elif flags.is_pdf:
                st.warning("PDF detected — table extraction / OCR may take time")
            elif flags.is_image:
                st.warning("Image detected — OCR will be applied")

        st.session_state.step = 1

# =============================================================================
# TAB 2 — CONVERT
# =============================================================================

with tab_convert:
    st.subheader("🔄 Convert to CSV")

    if st.session_state.file_path:
        if st.button("Run Conversion", type="primary"):
            status = st.empty()
            status.info("Converting file...")

            csv_path = convert_to_csv(st.session_state.file_path)
            if csv_path is None:
                st.error("Conversion failed — no table found")
            else:
                st.session_state.csv_path = csv_path
                df = pd.read_csv(csv_path)
                df = prepare_headers(df)
                st.session_state.raw_df = df

                status.success("Conversion completed")
                st.dataframe(df.head(), use_container_width=True)
                st.caption(f"{df.shape[0]} rows × {df.shape[1]} columns")

                st.session_state.step = 2
    else:
        st.info("Upload a file to continue")

# =============================================================================
# TAB 3 — MAP (AUTO)
# =============================================================================

with tab_map:
    st.subheader("🧠 Column Mapping")

    if st.session_state.raw_df is not None:
        st.info("Using standardized column headers (auto-mapped)")

        # Mapping already applied in backend
        st.session_state.mapped_df = st.session_state.raw_df.copy()

        st.dataframe(st.session_state.mapped_df.head(), use_container_width=True)
        st.session_state.step = 3
    else:
        st.info("Convert file first")

# =============================================================================
# TAB 4 — CLEAN
# =============================================================================

with tab_clean:
    st.subheader("🧹 Clean Dataset")

    if st.session_state.mapped_df is not None:
        if st.button("Run Cleaning", type="primary"):
            with st.spinner("Cleaning data..."):
                cleaned_df = clean_data(
                    st.session_state.mapped_df,
                    missing_threshold=missing_threshold,
                    fill_method=fill_method
                )

                st.session_state.cleaned_df = cleaned_df
                st.session_state.step = 4

        if st.session_state.cleaned_df is not None:
            col1, col2 = st.columns(2)
            with col1:
                st.caption("Before Cleaning")
                st.dataframe(st.session_state.mapped_df.head())

            with col2:
                st.caption("After Cleaning")
                st.dataframe(st.session_state.cleaned_df.head())
    else:
        st.info("Mapping required first")

# =============================================================================
# TAB 5 — EXPORT
# =============================================================================

with tab_export:
    st.subheader("📥 Export Results")

    if st.session_state.cleaned_df is not None:
        base = Path(st.session_state.csv_path).stem

        mapped_out = os.path.join(FOLDERS["mapped"], f"{base}_mapped.csv")
        cleaned_out = os.path.join(FOLDERS["cleaned"], f"{base}_cleaned.csv")

        st.session_state.mapped_df.to_csv(mapped_out, index=False)
        st.session_state.cleaned_df.to_csv(cleaned_out, index=False)

        with st.container(border=True):
            st.markdown("### 📊 Pipeline Summary")
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows", st.session_state.cleaned_df.shape[0])
            c2.metric("Columns", st.session_state.cleaned_df.shape[1])
            c3.metric("Removed Rows",
                      st.session_state.mapped_df.shape[0] - st.session_state.cleaned_df.shape[0])

        st.download_button(
            "⬇ Download Cleaned CSV",
            data=open(cleaned_out, "rb"),
            file_name="cleaned_data.csv",
            mime="text/csv"
        )
    else:
        st.info("Clean the data to enable export")

# =============================================================================
# TAB 6 — RISK ANALYSIS
# =============================================================================

with tab_risk:
    st.subheader("🔍 Risk Analysis Dashboard")

    if st.session_state.cleaned_df is not None:

        if st.button("▶  Run Risk Analysis", type="primary"):
            with st.spinner("Analysing contracts..."):
                risk_df = analyse_contracts(st.session_state.cleaned_df)
                stats   = risk_summary(risk_df)
                st.session_state.risk_df    = risk_df
                st.session_state.risk_stats = stats
                st.session_state.step = 5

        if st.session_state.risk_df is not None:
            stats = st.session_state.risk_stats
            risk_df = st.session_state.risk_df

            # ── KPI metrics ──────────────────────────────────────────────────
            st.markdown("### 📊 Risk Summary")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Contracts", stats.get("total", 0))
            c2.metric("🔴 High Risk",
                      f"{stats.get('high_risk', 0)}",
                      f"{stats.get('high_pct', 0)}%")
            c3.metric("🟡 Medium Risk",
                      f"{stats.get('medium_risk', 0)}",
                      f"{stats.get('medium_pct', 0)}%")
            c4.metric("🟢 Low Risk",
                      f"{stats.get('low_risk', 0)}",
                      f"{stats.get('low_pct', 0)}%")

            st.divider()

            # ── Filter controls ───────────────────────────────────────────────
            st.markdown("### 🔎 Filter Results")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                flag_filter = st.multiselect(
                    "Show risk levels:",
                    options=["🔴 HIGH", "🟡 MEDIUM", "🟢 LOW"],
                    default=["🔴 HIGH", "🟡 MEDIUM", "🟢 LOW"]
                )
            with col_f2:
                score_max = st.slider(
                    "Max risk score to show",
                    min_value=0.0, max_value=10.0, value=10.0, step=0.1
                )

            # apply filters
            display_df = risk_df.copy()
            if "risk_flag" in display_df.columns:
                # normalise flag strings for filter
                display_df["_flag_short"] = display_df["risk_flag"].str.extract(
                    r"(HIGH|MEDIUM|LOW)"
                )
                flag_shorts = [f.split()[-1] for f in flag_filter]
                display_df = display_df[
                    display_df["_flag_short"].isin(flag_shorts)
                ]
                display_df = display_df[
                    display_df["risk_score"] <= score_max
                ]
                display_df = display_df.drop(columns=["_flag_short"])

            st.caption(f"Showing {len(display_df)} of {len(risk_df)} contracts")

            # ── Results table ─────────────────────────────────────────────────
            st.markdown("### 📋 Contract Risk Table")

            # choose display columns
            display_cols = []
            priority = [
                "risk_flag", "risk_score", "predicted_value_eur",
                "missing_critical_fields",
                "transaction_id", "contract_id",
                "company", "country",
                "item_category", "cpv_sector",
                "total_cost", "contract_value_eur",
                "purchase_date", "award_date",
            ]
            for col in priority:
                if col in display_df.columns:
                    display_cols.append(col)

            # add any remaining columns
            for col in display_df.columns:
                if col not in display_cols:
                    display_cols.append(col)

            st.dataframe(
                display_df[display_cols].reset_index(drop=True),
                use_container_width=True,
                height=400,
                column_config={
                    "risk_flag": st.column_config.TextColumn(
                        "Risk Flag", width="medium"
                    ),
                    "risk_score": st.column_config.NumberColumn(
                        "Risk Score", format="%.4f"
                    ),
                    "predicted_value_eur": st.column_config.NumberColumn(
                        "Predicted €", format="€%.2f"
                    ),
                    "missing_critical_fields": st.column_config.NumberColumn(
                        "Missing Fields"
                    ),
                }
            )

            # ── High risk table ───────────────────────────────────────────────
            high_risk_df = risk_df[risk_df["risk_flag"] == "🔴 HIGH"]
            if len(high_risk_df) > 0:
                st.divider()
                st.markdown(f"### 🔴 High Risk Contracts ({len(high_risk_df)})")
                st.dataframe(
                    high_risk_df[display_cols].reset_index(drop=True),
                    use_container_width=True,
                    height=300,
                )

            # ── Export risk results ───────────────────────────────────────────
            st.divider()
            st.markdown("### ⬇ Export Risk Analysis")
            col_e1, col_e2 = st.columns(2)

            with col_e1:
                csv_all = risk_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇ Download All Results (CSV)",
                    data=csv_all,
                    file_name="procurelens_risk_analysis.csv",
                    mime="text/csv"
                )

            with col_e2:
                if len(high_risk_df) > 0:
                    csv_high = high_risk_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "🔴 Download High Risk Only (CSV)",
                        data=csv_high,
                        file_name="procurelens_high_risk.csv",
                        mime="text/csv"
                    )

            # ── Model info ────────────────────────────────────────────────────
            st.divider()
            with st.expander("ℹ️ About the Risk Score"):
                st.markdown("""
**Risk Score Formula:**
```
Risk Score = |actual_value - predicted_value| / predicted_value
```

**Thresholds (from DAS5000 research):**
- 🔴 **HIGH**: score > 0.5 or 2+ critical fields missing
- 🟡 **MEDIUM**: score 0.2–0.5
- 🟢 **LOW**: score < 0.2

**Model:**
Random Forest trained on 10,038,018 EU TED contracts (2006–2025)
CV R² = 0.2795 · Test R² = 0.2613 · 127 features

**Note:** This is a decision-support prototype.
All flags require human review before action.
""")

    else:
        st.info("Please complete the data cleaning step first (Tab 4 — Clean).")
        st.markdown("""
        **Pipeline steps required:**
        1. 📤 Upload your procurement file
        2. 🔄 Convert to CSV
        3. 🧠 Map columns
        4. 🧹 Clean data
        5. **🔍 Then run Risk Analysis here**
        """)
