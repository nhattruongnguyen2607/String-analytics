import streamlit as st

def render(df):
    st.header("Dữ liệu chi tiết (Pre-processed)")
    
    st.markdown("Dữ liệu sau khi đã Merge và xử lý NA:")
    st.dataframe(df, use_container_width=True)
    
    st.subheader("Thống kê mô tả")
    st.write(df.describe())
