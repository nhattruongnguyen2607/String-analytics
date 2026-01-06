import streamlit as st
import pandas as pd

def render(df):
    st.header("Overview - Tổng quan hệ thống")

    # 1. Các chỉ số KPI (Key Performance Indicators)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tổng số Plant", df['Plant'].nunique())
    with col2:
        st.metric("Tổng số Inverter", df['Inverter'].nunique())
    with col3:
        st.metric("Tổng số String", df['label'].nunique())
    with col4:
        avg_perf = df['Performance'].mean()
        st.metric("Hiệu suất TB", f"{avg_perf:.2%}")

    st.markdown("---")

    # 2. Phát hiện String lỗi (Performance thấp bất thường)
    st.subheader("⚠️ Cảnh báo String hiệu suất thấp")
    
    # Logic đơn giản: Lấy các string có hiệu suất trung bình < 80% (hoặc threshold tùy chỉnh)
    threshold = st.slider("Ngưỡng hiệu suất cảnh báo (%)", 0.0, 1.0, 0.5, 0.05)
    
    # Tính hiệu suất trung bình theo từng string
    string_perf = df.groupby(['Plant', 'Inverter', 'label'])['Performance'].mean().reset_index()
    low_perf_strings = string_perf[string_perf['Performance'] < threshold].sort_values('Performance')

    if not low_perf_strings.empty:
        st.warning(f"Tìm thấy {len(low_perf_strings)} string có hiệu suất dưới {threshold*100}%")
        st.dataframe(low_perf_strings, use_container_width=True)
    else:
        st.success("Không tìm thấy string nào dưới ngưỡng cảnh báo.")
