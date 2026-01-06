# app.py
"""
Entry point for Streamlit.

- Sidebar is split into 2 tabs:
  - MERGE: upload 2 files + merge settings + Run Merge
  - ANALYSIS: cascading filters (Plant -> Inverter -> Azimuth -> Capacity) + Generate button

All reusable functions are located in functions.py
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from functions import (
    MergeStats,
    apply_analysis_filters,
    clean_columns,
    download_csv_bytes,
    download_xlsx_bytes,
    find_col,
    load_table,
    merge_on_key,
    render_basic_numeric_chart,
    render_low_performance_section,
    render_preview,
)

# =========================
# App config
# =========================
st.set_page_config(page_title="Merge & Performance Dashboard", layout="wide")

# =========================
# Sidebar layout: 2 tabs
# =========================
st.sidebar.title("🧭 Điều khiển")
tab_merge, tab_analysis = st.sidebar.tabs(["MERGE", "ANALYSIS"])

# Session state for dataframes
if "df_a" not in st.session_state:
    st.session_state.df_a = None
if "df_b" not in st.session_state:
    st.session_state.df_b = None
if "merged" not in st.session_state:
    st.session_state.merged = None
if "merge_stats" not in st.session_state:
    st.session_state.merge_stats = None
if "merge_warns" not in st.session_state:
    st.session_state.merge_warns = []

# Analysis state (apply filters only after clicking Generate)
if "analysis_settings" not in st.session_state:
    st.session_state.analysis_settings = None
if "analysis_generated" not in st.session_state:
    st.session_state.analysis_generated = False


# =========================
# MERGE tab (sidebar)
# =========================
with tab_merge:
    st.subheader("Upload & Merge")

    file_a = st.file_uploader("File A (DATA) - CSV/XLSX", type=["csv", "xlsx", "xls"], key="file_a")
    file_b = st.file_uploader("File B (CONFIG) - CSV/XLSX", type=["csv", "xlsx", "xls"], key="file_b")

    st.markdown("---")
    st.caption("Merge Settings")
    key_a = st.text_input("Key column File A", value="label", key="key_a")
    key_b = st.text_input("Key column File B", value="label", key="key_b")
    how = st.selectbox("Merge type", options=["left", "inner"], index=0, key="how")
    drop_dupe_cfg = st.checkbox("CONFIG: drop duplicate key (keep first)", value=True, key="drop_dupe_cfg")

    st.markdown("---")
    st.caption("Pre-processing (optional)")
    drop_na = st.checkbox("Drop rows with NA", value=False, key="drop_na")
    dedup = st.checkbox("Drop duplicated rows", value=False, key="dedup")

    # Sheet selection for Excel only
    sheet_a = None
    sheet_b = None
    if file_a is not None:
        _, sheets_a = load_table(file_a.name, file_a.getvalue(), sheet_name=None)
        if sheets_a:
            sheet_a = st.selectbox("Sheet File A", options=sheets_a, index=0, key="sheet_a")
    if file_b is not None:
        _, sheets_b = load_table(file_b.name, file_b.getvalue(), sheet_name=None)
        if sheets_b:
            sheet_b = st.selectbox("Sheet File B", options=sheets_b, index=0, key="sheet_b")

    st.markdown("---")
    run_merge = st.button("✅ Run Merge", type="primary", use_container_width=True)

    if run_merge:
        if file_a is None or file_b is None:
            st.error("Bạn cần upload cả File A và File B.")
        else:
            df_a, _ = load_table(file_a.name, file_a.getvalue(), sheet_name=sheet_a)
            df_b, _ = load_table(file_b.name, file_b.getvalue(), sheet_name=sheet_b)

            df_a = clean_columns(df_a)
            df_b = clean_columns(df_b)

            if drop_na:
                df_a = df_a.dropna()
                df_b = df_b.dropna()
            if dedup:
                df_a = df_a.drop_duplicates()
                df_b = df_b.drop_duplicates()

            if key_a not in df_a.columns:
                st.error(f"File A không có cột '{key_a}'.")
            elif key_b not in df_b.columns:
                st.error(f"File B không có cột '{key_b}'.")
            else:
                merged, stats, warns = merge_on_key(
                    df_a, df_b, key_a=key_a, key_b=key_b, how=how, drop_dupe_config=drop_dupe_cfg
                )
                st.session_state.df_a = df_a
                st.session_state.df_b = df_b
                st.session_state.merged = merged
                st.session_state.merge_stats = stats
                st.session_state.merge_warns = warns

                # reset analysis
                st.session_state.analysis_settings = None
                st.session_state.analysis_generated = False

                st.success("Merge thành công! Chuyển qua tab ANALYSIS để cấu hình phân tích.")


# =========================
# ANALYSIS tab (sidebar): cascading + Generate
# =========================
with tab_analysis:
    st.subheader("Analysis Settings")

    merged = st.session_state.merged
    if merged is None or not isinstance(merged, pd.DataFrame) or merged.empty:
        st.info("Chưa có dữ liệu merged. Hãy qua tab MERGE và bấm **Run Merge** trước.")
    else:
        # Identify columns
        label_col = find_col(merged, "label", aliases=["lable", "Label", "LABEL"])
        plant_col = find_col(merged, "Plant", aliases=["plant", "PLANT"])
        perf_col = find_col(merged, "Performance", aliases=["performance", "PERFORMANCE", "perf"])
        date_col = find_col(merged, "date", aliases=["Date", "DATE", "datetime", "time"])

        inverter_col = find_col(merged, "Inverter", aliases=["inverter"])
        capacity_col = find_col(merged, "Capacity", aliases=["capacity"])
        az_col = find_col(merged, "String Azimuth", aliases=["string azimuth", "azimuth"])

        # Chart settings
        st.caption("Biểu đồ thống kê (numeric)")
        num_cols = merged.select_dtypes(include=["number"]).columns.tolist()
        metric_col = st.selectbox("Numeric column", options=(num_cols if num_cols else ["(none)"]), index=0, key="metric_col")
        chart_type = st.selectbox("Chart type", options=["Histogram", "Boxplot"], index=0, key="chart_type")

        st.markdown("---")
        st.caption("Low-performance dashboard filters (cascading)")

        # Cascading options: Plant -> Inverter -> Azimuth -> Capacity
        opts_df = merged.copy()

        def _keep_valid(key: str, options: List[str]) -> List[str]:
            cur = st.session_state.get(key, [])
            if cur is None:
                cur = []
            cur = [str(x) for x in cur]
            return [x for x in cur if x in options]

        # 1) Plant
        plant_sel: List[str] = []
        if plant_col:
            plants = sorted(opts_df[plant_col].dropna().astype(str).unique().tolist())
            if "plant_sel" in st.session_state:
                st.session_state["plant_sel"] = _keep_valid("plant_sel", plants)
            default_plants = st.session_state.get("plant_sel", plants[:1] if plants else [])
            plant_sel = st.multiselect("Plant", options=plants, default=default_plants, key="plant_sel")
        else:
            st.info("Không tìm thấy cột Plant trong dữ liệu merge.")

        df_p = opts_df
        if plant_col and plant_sel:
            df_p = df_p[df_p[plant_col].astype(str).isin([str(p) for p in plant_sel])]

        bottom_n = st.number_input("Bottom N labels / Plant", min_value=3, max_value=50, value=10, step=1, key="bottom_n")

        # 2) Inverter (depends on Plant)
        inv_sel: List[str] = []
        if inverter_col:
            inv_vals = sorted(df_p[inverter_col].dropna().astype(str).unique().tolist())
            if "inv_sel" in st.session_state:
                st.session_state["inv_sel"] = _keep_valid("inv_sel", inv_vals)
            default_inv = st.session_state.get("inv_sel", inv_vals)
            inv_sel = st.multiselect("Inverter", options=inv_vals, default=default_inv, key="inv_sel")

        df_pi = df_p
        if inverter_col and inv_sel:
            df_pi = df_pi[df_pi[inverter_col].astype(str).isin(inv_sel)]

        # 3) Azimuth (depends on Plant + Inverter)
        az_sel: List[str] = []
        if az_col:
            az_vals = sorted(df_pi[az_col].dropna().astype(str).unique().tolist())
            if "az_sel" in st.session_state:
                st.session_state["az_sel"] = _keep_valid("az_sel", az_vals)
            default_az = st.session_state.get("az_sel", az_vals)
            az_sel = st.multiselect("String Azimuth", options=az_vals, default=default_az, key="az_sel")

        df_pia = df_pi
        if az_col and az_sel:
            df_pia = df_pia[df_pia[az_col].astype(str).isin(az_sel)]

        # 4) Capacity (depends on Plant + Inverter + Azimuth)
        cap_range = None
        cap_set = None
        if capacity_col:
            if pd.api.types.is_numeric_dtype(df_pia[capacity_col]):
                cap_series = pd.to_numeric(df_pia[capacity_col], errors="coerce").dropna()
                if not cap_series.empty:
                    cmin = float(cap_series.min())
                    cmax = float(cap_series.max())

                    prev = st.session_state.get("cap_range")
                    if isinstance(prev, (list, tuple)) and len(prev) == 2:
                        lo = max(cmin, float(prev[0]))
                        hi = min(cmax, float(prev[1]))
                        if lo > hi:
                            lo, hi = cmin, cmax
                        st.session_state["cap_range"] = (lo, hi)

                    cap_range = st.slider(
                        "Capacity (range)",
                        min_value=cmin,
                        max_value=cmax,
                        value=st.session_state.get("cap_range", (cmin, cmax)),
                        key="cap_range",
                    )
                else:
                    st.info("Không có dữ liệu Capacity sau khi lọc Plant/Inverter/Azimuth.")
            else:
                cap_vals = sorted(df_pia[capacity_col].dropna().astype(str).unique().tolist())
                if "cap_set" in st.session_state:
                    cur = st.session_state.get("cap_set", [])
                    st.session_state["cap_set"] = [str(x) for x in cur if str(x) in cap_vals]
                cap_set = st.multiselect("Capacity", options=cap_vals, default=st.session_state.get("cap_set", cap_vals), key="cap_set")

        # Date range (optional)
        date_range = None
        if date_col:
            tmpd = pd.to_datetime(df_pia[date_col], errors="coerce", infer_datetime_format=True)
            if tmpd.notna().any():
                dmin = tmpd.min().date()
                dmax = tmpd.max().date()
                prevd = st.session_state.get("date_range")
                if isinstance(prevd, (list, tuple)) and len(prevd) == 2:
                    s0, e0 = prevd
                    try:
                        s0 = max(dmin, s0)
                        e0 = min(dmax, e0)
                        if s0 > e0:
                            s0, e0 = dmin, dmax
                        st.session_state["date_range"] = (s0, e0)
                    except Exception:
                        st.session_state["date_range"] = (dmin, dmax)

                date_range = st.date_input(
                    "Khoảng ngày",
                    value=st.session_state.get("date_range", (dmin, dmax)),
                    min_value=dmin,
                    max_value=dmax,
                    key="date_range",
                )

        analysis_settings: Dict[str, Any] = {
            "label_col": label_col,
            "plant_col": plant_col,
            "perf_col": perf_col,
            "date_col": date_col,
            "inverter_col": inverter_col,
            "capacity_col": capacity_col,
            "az_col": az_col,
            "metric_col": metric_col if metric_col != "(none)" else None,
            "chart_type": chart_type,
            "plant_sel": plant_sel,
            "bottom_n": int(bottom_n),
            "inv_sel": inv_sel,
            "az_sel": az_sel,
            "cap_range": cap_range,
            "cap_set": cap_set,
            "date_range": date_range,
        }

        st.markdown("---")
        gen = st.button("⚙️ Generate", type="primary", use_container_width=True, key="btn_generate")
        if gen:
            st.session_state.analysis_settings = analysis_settings
            st.session_state.analysis_generated = True
            st.success("Đã Generate! Các bộ lọc/biểu đồ đã được áp dụng ở màn hình chính.")


# =========================
# Main Page
# =========================
st.title("🔗 Streamlit Merge Tool + Performance Dashboard")
st.caption("`app.py` chỉ là entrypoint. Tất cả functions nằm trong `functions.py`.")

merged = st.session_state.merged
df_a = st.session_state.df_a
df_b = st.session_state.df_b

if merged is None:
    st.info("Hãy vào tab **MERGE** (sidebar) → upload 2 file → bấm **Run Merge**.")
    st.stop()

# Preview
st.markdown("## Preview (File A vs File B)")
if df_a is not None and df_b is not None:
    c1, c2 = st.columns(2)
    with c1:
        render_preview("File A (DATA)", df_a)
    with c2:
        render_preview("File B (CONFIG)", df_b)

# Merged result
st.markdown("---")
st.markdown("## ✅ Merged Result")
stats = st.session_state.merge_stats
warns = st.session_state.merge_warns or []

if warns:
    for w in warns:
        st.warning(w)

if stats is not None:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Rows A", f"{stats.rows_a:,}")
    k2.metric("Rows B", f"{stats.rows_b:,}")
    k3.metric("Rows merged", f"{stats.rows_merged:,}")
    k4.metric("Matched", f"{stats.matched_rows:,}")
    k5.metric("Unmatched", f"{stats.unmatched_rows:,}")
    if stats.unmatched_rows > 0:
        st.info("Unmatched = label trong File A không tìm thấy trong File B. Các cột config sẽ trống.")

st.dataframe(merged.head(300), use_container_width=True, height=450)

d1, d2 = st.columns(2)
with d1:
    st.download_button(
        "⬇️ Download CSV",
        data=download_csv_bytes(merged),
        file_name="merged_result.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d2:
    st.download_button(
        "⬇️ Download Excel",
        data=download_xlsx_bytes(merged),
        file_name="merged_result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# Analysis (gated by Generate)
st.markdown("---")
st.markdown("## 📊 Analysis")

settings = st.session_state.analysis_settings if st.session_state.analysis_generated else None
if not settings:
    st.info("Hãy qua tab **ANALYSIS** (sidebar), chọn bộ lọc và bấm **Generate** để áp dụng.")
else:
    st.markdown("### 1) Biểu đồ thống kê cơ bản")
    render_basic_numeric_chart(
        merged,
        metric_col=settings.get("metric_col"),
        chart_type=settings.get("chart_type", "Histogram"),
    )

    st.markdown("---")
    st.markdown("### 2) Dashboard: Low-performance labels")

    label_col = settings.get("label_col")
    plant_col = settings.get("plant_col")
    perf_col = settings.get("perf_col")
    date_col = settings.get("date_col")

    if not (label_col and plant_col and perf_col):
        st.info("Thiếu cột Plant/label/Performance trong dữ liệu merge. Không thể chạy dashboard low-performance.")
    else:
        filtered = apply_analysis_filters(
            merged,
            plant_col=plant_col,
            label_col=label_col,
            perf_col=perf_col,
            date_col=date_col,
            inverter_col=settings.get("inverter_col"),
            capacity_col=settings.get("capacity_col"),
            az_col=settings.get("az_col"),
            plant_sel=settings.get("plant_sel", []),
            inv_sel=settings.get("inv_sel", []),
            az_sel=settings.get("az_sel", []),
            cap_range=settings.get("cap_range"),
            cap_set=settings.get("cap_set"),
            date_range=settings.get("date_range"),
        )

        render_low_performance_section(
            filtered,
            plant_col=plant_col,
            label_col=label_col,
            perf_col=perf_col,
            date_col=date_col,
            bottom_n=int(settings.get("bottom_n", 10)),
        )
