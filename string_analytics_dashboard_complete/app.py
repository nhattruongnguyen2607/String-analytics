# app.py
# Streamlit multi-tab dashboard (single-file version to avoid ModuleNotFound / import issues)
# Run: streamlit run app.py

import io
from dataclasses import dataclass
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="String Analytics Dashboard", layout="wide")


# ---------------------------
# Helpers
# ---------------------------

@st.cache_data(show_spinner=False)
def load_sample_data(rows: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    start = pd.Timestamp("2024-01-01")
    dates = start + pd.to_timedelta(rng.integers(0, 180, size=rows), unit="D")
    categories = rng.choice(["A", "B", "C", "D"], size=rows, replace=True)
    regions = rng.choice(["North", "South", "East", "West"], size=rows, replace=True)
    value1 = rng.normal(100, 20, size=rows)
    value2 = rng.normal(50, 10, size=rows)
    score = (value1 * 0.4 + value2 * 0.6) + rng.normal(0, 5, size=rows)
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "category": categories,
            "region": regions,
            "value_1": np.round(value1, 2),
            "value_2": np.round(value2, 2),
            "score": np.round(score, 2),
        }
    )


def _try_read_csv(file_bytes: bytes) -> pd.DataFrame:
    # Try common encodings; fallback to pandas default
    for enc in ("utf-8", "utf-8-sig", "cp1258", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
        except Exception:
            pass
    return pd.read_csv(io.BytesIO(file_bytes))


def _try_read_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(file_bytes))


def load_uploaded_file(uploaded) -> Optional[pd.DataFrame]:
    if uploaded is None:
        return None

    file_bytes = uploaded.getvalue()
    name = (uploaded.name or "").lower()

    try:
        if name.endswith(".csv"):
            return _try_read_csv(file_bytes)
        if name.endswith(".xlsx") or name.endswith(".xls"):
            return _try_read_excel(file_bytes)
        if name.endswith(".parquet"):
            return pd.read_parquet(io.BytesIO(file_bytes))
        # Try CSV as a safe fallback
        return _try_read_csv(file_bytes)
    except Exception as e:
        st.error(f"Không đọc được file: {e}")
        return None


def get_column_types(df: pd.DataFrame) -> Tuple[List[str], List[str], List[str]]:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns.tolist()
    other_cols = [c for c in df.columns if c not in numeric_cols and c not in datetime_cols]
    return numeric_cols, datetime_cols, other_cols


def try_parse_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    s = df[col]
    if np.issubdtype(s.dtype, np.datetime64):
        return pd.to_datetime(s, errors="coerce")
    # Attempt parsing strings/objects
    return pd.to_datetime(s, errors="coerce", infer_datetime_format=True)


def kpi_card(label: str, value, help_text: Optional[str] = None):
    with st.container(border=True):
        st.caption(label)
        st.subheader(value)
        if help_text:
            st.write(help_text)


# ---------------------------
# Sidebar: data & settings
# ---------------------------

st.sidebar.title("⚙️ Cài đặt")

uploaded = st.sidebar.file_uploader("Tải dữ liệu (CSV/XLSX/Parquet)", type=["csv", "xlsx", "xls", "parquet"])
use_sample = st.sidebar.toggle("Dùng dữ liệu mẫu", value=(uploaded is None))

if use_sample:
    df = load_sample_data()
else:
    df = load_uploaded_file(uploaded)
    if df is None:
        st.stop()

# Basic cleaning options
st.sidebar.markdown("---")
st.sidebar.subheader("Tiền xử lý (tuỳ chọn)")
drop_na = st.sidebar.checkbox("Bỏ dòng có NA (thiếu dữ liệu)", value=False)
dedup = st.sidebar.checkbox("Xoá dòng trùng lặp", value=False)

if drop_na:
    df = df.dropna()
if dedup:
    df = df.drop_duplicates()

# Try to parse datetime columns from object columns (optional)
auto_parse_dt = st.sidebar.checkbox("Tự động nhận dạng cột ngày/giờ", value=True)
if auto_parse_dt:
    for c in df.columns:
        if df[c].dtype == "object":
            parsed = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
            # If many values parsed successfully, accept conversion
            if parsed.notna().mean() >= 0.8 and parsed.nunique(dropna=True) > 1:
                df[c] = parsed

numeric_cols, datetime_cols, other_cols = get_column_types(df)

st.title("📊 String Analytics Dashboard")
st.caption("Bản một-file (single-file) để tránh lỗi import trên Streamlit Cloud. Có tab Overview, Data View, Time Analysis, Attr Analysis.")

tabs = st.tabs(["Overview", "Data View", "Time Analysis", "Attr Analysis"])


# ---------------------------
# Tab: Overview
# ---------------------------
with tabs[0]:
    st.subheader("Tổng quan")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Số dòng", f"{len(df):,}")
    with c2:
        kpi_card("Số cột", f"{df.shape[1]:,}")
    with c3:
        kpi_card("Cột số (numeric)", f"{len(numeric_cols)}")
    with c4:
        kpi_card("Cột thời gian (datetime)", f"{len(datetime_cols)}")

    st.markdown("### Thông tin dữ liệu")
    info_left, info_right = st.columns([1, 1])
    with info_left:
        st.write("**Danh sách cột:**")
        st.dataframe(pd.DataFrame({"column": df.columns, "dtype": [str(df[c].dtype) for c in df.columns]}), use_container_width=True)
    with info_right:
        na_rate = (df.isna().mean() * 100).sort_values(ascending=False)
        st.write("**Tỷ lệ thiếu dữ liệu (NA %):**")
        st.dataframe(na_rate.reset_index().rename(columns={"index": "column", 0: "na_percent"}), use_container_width=True)

    st.markdown("### Xem nhanh")
    st.dataframe(df.head(20), use_container_width=True)


# ---------------------------
# Tab: Data View
# ---------------------------
with tabs[1]:
    st.subheader("Xem dữ liệu & lọc")

    col_a, col_b, col_c = st.columns([2, 2, 1])

    with col_a:
        search = st.text_input("Tìm kiếm (áp dụng cho toàn bộ dữ liệu, dạng text)", value="")
    with col_b:
        show_cols = st.multiselect("Chọn cột hiển thị", options=df.columns.tolist(), default=df.columns.tolist()[: min(8, df.shape[1])])
    with col_c:
        nrows = st.number_input("Số dòng hiển thị", min_value=10, max_value=5000, value=200, step=10)

    view_df = df.copy()

    if search.strip():
        s = search.strip().lower()
        mask = pd.Series(False, index=view_df.index)
        for c in view_df.columns:
            mask = mask | view_df[c].astype(str).str.lower().str.contains(s, na=False)
        view_df = view_df.loc[mask]

    if show_cols:
        view_df = view_df[show_cols]

    st.dataframe(view_df.head(int(nrows)), use_container_width=True)

    st.markdown("### Tải xuống dữ liệu đã lọc")
    csv_bytes = view_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="filtered_data.csv", mime="text/csv")


# ---------------------------
# Tab: Time Analysis
# ---------------------------
with tabs[2]:
    st.subheader("Phân tích theo thời gian")

    if not datetime_cols:
        st.info("Không tìm thấy cột datetime. Hãy bật 'Tự động nhận dạng cột ngày/giờ' ở sidebar hoặc đảm bảo cột ngày/giờ đúng định dạng.")
    else:
        left, right = st.columns([1, 2])

        with left:
            dt_col = st.selectbox("Chọn cột thời gian", options=datetime_cols, index=0)
            metric = st.selectbox("Chọn cột số để phân tích", options=(numeric_cols if numeric_cols else ["(count)"]))
            freq = st.selectbox("Chu kỳ gom nhóm", options=["Day", "Week", "Month"], index=1)

            agg = st.selectbox("Phép tổng hợp", options=["sum", "mean", "median", "min", "max"], index=0)
            show_raw = st.checkbox("Hiện bảng dữ liệu sau gom nhóm", value=False)

        tmp = df.copy()
        tmp[dt_col] = try_parse_datetime(tmp, dt_col)
        tmp = tmp.dropna(subset=[dt_col])

        if freq == "Day":
            grp_key = tmp[dt_col].dt.to_period("D").dt.to_timestamp()
        elif freq == "Week":
            grp_key = tmp[dt_col].dt.to_period("W").dt.start_time
        else:
            grp_key = tmp[dt_col].dt.to_period("M").dt.to_timestamp()

        tmp = tmp.assign(_t=grp_key)

        if metric == "(count)" or (metric not in tmp.columns) or (not numeric_cols):
            ts = tmp.groupby("_t").size().reset_index(name="count")
            ycol = "count"
        else:
            ts = tmp.groupby("_t")[metric].agg(agg).reset_index()
            ycol = metric

        with right:
            fig = px.line(ts, x="_t", y=ycol, markers=True, title=f"{agg} {ycol} theo {freq.lower()}")
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

        if show_raw:
            st.dataframe(ts.sort_values("_t"), use_container_width=True)


# ---------------------------
# Tab: Attr Analysis
# ---------------------------
with tabs[3]:
    st.subheader("Phân tích thuộc tính (Attr)")

    if df.empty:
        st.warning("Dữ liệu trống.")
    else:
        left, right = st.columns([1, 2])

        with left:
            cat_candidates = other_cols + [c for c in df.columns if c in df.select_dtypes(include=["category", "bool"]).columns]
            cat_col = st.selectbox("Cột phân loại (categorical)", options=(cat_candidates if cat_candidates else df.columns.tolist()), index=0)

            num_col = None
            if numeric_cols:
                num_col = st.selectbox("Cột số (numeric) để so sánh", options=numeric_cols, index=0)

            top_n = st.slider("Top N giá trị phổ biến", min_value=5, max_value=50, value=10, step=1)

            chart_type = st.selectbox("Kiểu biểu đồ", options=["Count bar", "Treemap", "Box (numeric vs category)"], index=0)

        # Right side: charts
        if chart_type in ("Count bar", "Treemap"):
            vc = df[cat_col].astype(str).value_counts(dropna=False).head(int(top_n)).reset_index()
            vc.columns = [cat_col, "count"]

            with right:
                if chart_type == "Count bar":
                    fig = px.bar(vc, x=cat_col, y="count", title=f"Top {top_n} giá trị của {cat_col}")
                else:
                    fig = px.treemap(vc, path=[cat_col], values="count", title=f"Treemap {cat_col} (Top {top_n})")
                fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(vc, use_container_width=True)

        else:
            if not numeric_cols or num_col is None:
                st.info("Không có cột numeric để vẽ boxplot.")
            else:
                with right:
                    fig = px.box(df, x=cat_col, y=num_col, points="outliers", title=f"Phân phối {num_col} theo {cat_col}")
                    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
                    st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.markdown("### Tương quan (Correlation) giữa các cột số")
        if len(numeric_cols) >= 2:
            corr = df[numeric_cols].corr(numeric_only=True)
            fig = px.imshow(corr, text_auto=True, aspect="auto", title="Correlation matrix")
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Cần ít nhất 2 cột numeric để tính correlation.")


st.sidebar.markdown("---")
st.sidebar.caption("Nếu bạn gặp ModuleNotFoundError trên Streamlit Cloud: hãy chắc chắn requirements.txt có 'plotly' và 'streamlit'.")
