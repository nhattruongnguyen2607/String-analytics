# functions.py
"""
Shared functions for Streamlit Merge & Performance Dashboard.

This file contains:
- File I/O helpers (CSV/XLSX reading)
- Merge logic + download helpers
- Analysis computations (bottom labels per Plant)
- UI render helpers (preview + charts + low-performance section)
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px


# =========================
# 1) Data I/O utilities
# =========================
def read_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
    """Robust CSV reader with common encodings."""
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
        except Exception:
            pass
    return pd.read_csv(io.BytesIO(file_bytes))


def read_excel_bytes(file_bytes: bytes, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """Read Excel bytes; return (df, sheet_names)."""
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    sheets = xls.sheet_names
    sheet = sheet_name or sheets[0]
    df = pd.read_excel(xls, sheet_name=sheet)
    return df, sheets


@st.cache_data(show_spinner=False)
def load_table(
    file_name: str, file_bytes: bytes, sheet_name: Optional[str] = None
) -> Tuple[pd.DataFrame, Optional[List[str]]]:
    """Load CSV/XLSX -> (df, sheets_or_none)."""
    name = (file_name or "").lower()
    if name.endswith(".csv"):
        return read_csv_bytes(file_bytes), None
    if name.endswith(".xlsx") or name.endswith(".xls"):
        df, sheets = read_excel_bytes(file_bytes, sheet_name=sheet_name)
        return df, sheets
    return read_csv_bytes(file_bytes), None


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip column names to reduce mismatch."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def normalize_str_series(s: pd.Series) -> pd.Series:
    """Normalize join key: string + strip."""
    return s.astype(str).str.strip()


def find_col(df: pd.DataFrame, canonical: str, aliases: List[str]) -> Optional[str]:
    """Find a column (case-insensitive) from canonical + aliases."""
    norm = {str(c).strip().lower(): c for c in df.columns}
    for cand in [canonical] + aliases:
        key = cand.strip().lower()
        if key in norm:
            return norm[key]
    return None


def to_numeric_safe(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def to_datetime_safe(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce", infer_datetime_format=True)
    return out


# =========================
# 2) Merge logic
# =========================
@dataclass
class MergeStats:
    rows_a: int
    rows_b: int
    rows_merged: int
    matched_rows: int
    unmatched_rows: int
    unique_key_a: int
    unique_key_b: int


def merge_on_key(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    key_a: str,
    key_b: str,
    how: str = "left",
    drop_dupe_config: bool = True,
) -> Tuple[pd.DataFrame, MergeStats, List[str]]:
    """
    Merge df_a (DATA) với df_b (CONFIG) theo key.
    - Default: LEFT JOIN (giữ toàn bộ rows của DATA)
    - Optional: drop duplicates trong CONFIG theo key để tránh nhân bản.
    Returns: (merged_df, stats, warnings)
    """
    warns: List[str] = []
    a = df_a.copy()
    b = df_b.copy()

    a[key_a] = normalize_str_series(a[key_a])
    b[key_b] = normalize_str_series(b[key_b])

    if b[key_b].duplicated().any():
        ndup = int(b[key_b].duplicated().sum())
        warns.append(f"CONFIG có {ndup:,} dòng '{key_b}' bị trùng.")
        if drop_dupe_config:
            b = b.drop_duplicates(subset=[key_b], keep="first")
            warns.append("Đã tự động xoá duplicates trong CONFIG (giữ dòng đầu tiên theo key).")

    merged = a.merge(b, left_on=key_a, right_on=key_b, how=how, suffixes=("", "_cfg"))

    # Keep output key clean
    if key_a != "label" and "label" not in merged.columns and key_a in merged.columns:
        merged = merged.rename(columns={key_a: "label"})
    if key_b != key_a:
        merged = merged.drop(columns=[key_b], errors="ignore")

    b_cols = [c for c in b.columns if c != key_b]
    matched = int(merged[b_cols].notna().any(axis=1).sum()) if b_cols else 0
    total = int(len(merged))

    stats = MergeStats(
        rows_a=int(len(a)),
        rows_b=int(len(b)),
        rows_merged=total,
        matched_rows=matched,
        unmatched_rows=total - matched,
        unique_key_a=int(a[key_a].nunique(dropna=True)),
        unique_key_b=int(b[key_b].nunique(dropna=True)),
    )
    return merged, stats, warns


def download_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def download_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "merged") -> bytes:
    buff = io.BytesIO()
    with pd.ExcelWriter(buff, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buff.seek(0)
    return buff.read()


# =========================
# 3) Analysis computations
# =========================
def compute_bottom_labels_per_plant(
    df: pd.DataFrame,
    plant_col: str,
    label_col: str,
    perf_col: str,
    date_col: Optional[str] = None,
    bottom_n: int = 10,
) -> pd.DataFrame:
    """Compute avg/min/max/count per (Plant, label), then bottom_n labels per Plant by avg_performance."""
    work = df.copy()
    work[perf_col] = pd.to_numeric(work[perf_col], errors="coerce")

    agg_map: Dict[str, Tuple[str, str]] = {
        "avg_performance": (perf_col, "mean"),
        "min_performance": (perf_col, "min"),
        "max_performance": (perf_col, "max"),
        "n_points": (perf_col, "size"),
    }
    if date_col and date_col in work.columns:
        work[date_col] = pd.to_datetime(work[date_col], errors="coerce", infer_datetime_format=True)
        agg_map["last_date"] = (date_col, "max")

    out = (
        work.dropna(subset=[plant_col, label_col])
        .groupby([plant_col, label_col], dropna=False)
        .agg(**agg_map)
        .reset_index()
        .sort_values([plant_col, "avg_performance"], ascending=[True, True])
    )
    return out.groupby(plant_col, as_index=False).head(int(bottom_n))


def apply_analysis_filters(
    df: pd.DataFrame,
    plant_col: str,
    label_col: str,
    perf_col: str,
    date_col: Optional[str],
    inverter_col: Optional[str],
    capacity_col: Optional[str],
    az_col: Optional[str],
    plant_sel: List[str],
    inv_sel: List[str],
    az_sel: List[str],
    cap_range: Optional[Tuple[float, float]],
    cap_set: Optional[List[str]],
    date_range: Optional[Tuple[Any, Any]],
) -> pd.DataFrame:
    """Apply filters from ANALYSIS sidebar to merged dataframe."""
    work = df.copy()
    work = to_numeric_safe(work, perf_col)
    if date_col:
        work = to_datetime_safe(work, date_col)

    if plant_sel:
        work = work[work[plant_col].astype(str).isin([str(p) for p in plant_sel])]

    if inverter_col and inv_sel:
        work = work[work[inverter_col].astype(str).isin(inv_sel)]

    if az_col and az_sel:
        work = work[work[az_col].astype(str).isin(az_sel)]

    if capacity_col:
        if cap_range is not None and pd.api.types.is_numeric_dtype(work[capacity_col]):
            lo, hi = cap_range
            work = work[(work[capacity_col] >= lo) & (work[capacity_col] <= hi)]
        elif cap_set is not None:
            work = work[work[capacity_col].astype(str).isin(cap_set)]

    if date_col and date_range and isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        if work[date_col].notna().any():
            work = work[(work[date_col].dt.date >= start) & (work[date_col].dt.date <= end)]

    return work


# =========================
# 4) UI helpers (render)
# =========================
def render_preview(title: str, df: pd.DataFrame, head_rows: int = 50) -> None:
    st.markdown(f"### {title}")
    c1, c2 = st.columns(2)
    c1.metric("Rows", f"{len(df):,}")
    c2.metric("Columns", f"{df.shape[1]:,}")

    with st.expander("Dtypes", expanded=False):
        st.dataframe(
            pd.DataFrame({"column": df.columns, "dtype": [str(df[c].dtype) for c in df.columns]}),
            use_container_width=True,
        )
    st.dataframe(df.head(head_rows), use_container_width=True, height=380)


def render_basic_numeric_chart(df: pd.DataFrame, metric_col: Optional[str], chart_type: str) -> None:
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not num_cols:
        st.info("Không có cột numeric để vẽ biểu đồ.")
        return

    if metric_col not in num_cols:
        metric_col = num_cols[0]

    if chart_type == "Histogram":
        fig = px.histogram(df, x=metric_col, nbins=30, title=f"Histogram: {metric_col}")
    else:
        if "Plant" in df.columns:
            fig = px.box(df, x="Plant", y=metric_col, points="outliers", title=f"Boxplot {metric_col} theo Plant")
        else:
            fig = px.box(df, y=metric_col, points="outliers", title=f"Boxplot: {metric_col}")

    st.plotly_chart(fig, use_container_width=True)

    st.caption("Summary statistics")
    st.dataframe(df[num_cols].describe().T, use_container_width=True)


def render_low_performance_section(
    work: pd.DataFrame,
    plant_col: str,
    label_col: str,
    perf_col: str,
    date_col: Optional[str],
    bottom_n: int,
) -> None:
    st.markdown("## Dashboard: label có Performance thấp theo từng Plant")

    if work.empty:
        st.warning("Không có dữ liệu sau khi lọc (ANALYSIS).")
        return

    low = compute_bottom_labels_per_plant(
        work, plant_col=plant_col, label_col=label_col, perf_col=perf_col, date_col=date_col, bottom_n=bottom_n
    )

    st.markdown("### Bảng label Performance thấp")
    st.dataframe(low, use_container_width=True)

    if low[plant_col].nunique() == 1:
        fig = px.bar(low.sort_values("avg_performance"), x=label_col, y="avg_performance", title="Bottom labels theo avg performance")
    else:
        fig = px.bar(
            low.sort_values("avg_performance"),
            x=label_col,
            y="avg_performance",
            color=plant_col,
            barmode="group",
            title="Bottom labels theo avg performance (so sánh nhiều plant)",
        )
    st.plotly_chart(fig, use_container_width=True)

    if date_col and work[date_col].notna().any():
        st.markdown("### Drill-down: Performance day-by-day theo label")
        label_opts = low[label_col].astype(str).unique().tolist()
        sel_labels = st.multiselect(
            "Chọn label để xem chi tiết", options=label_opts, default=label_opts[: min(3, len(label_opts))]
        )
        if sel_labels:
            dd = work[work[label_col].astype(str).isin(sel_labels)].copy()
            dd = dd.dropna(subset=[date_col])
            dd["_day"] = dd[date_col].dt.to_period("D").dt.to_timestamp()
            ts = dd.groupby(["_day", label_col])[perf_col].mean().reset_index()

            fig2 = px.line(ts, x="_day", y=perf_col, color=label_col, markers=True, title="Performance day-by-day theo label")
            st.plotly_chart(fig2, use_container_width=True)
