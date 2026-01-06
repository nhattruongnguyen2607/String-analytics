import streamlit as st
import pandas as pd
from utils import load_and_process_data

# Import các tab giao diện
from tabs import overview, data_view, time_analysis, attr_analysis

# 1. Cấu hình trang
st.set_page_config(
    page_title="Solar String Analysis Dashboard",
    page_icon="☀️",
    layout="wide"
)

# 2. Load dữ liệu (Chỉ load 1 lần nhờ @st.cache_data trong utils)
DATA_FILE = '202510.csv'
CONFIG_FILE = 'String config.csv'

# Hiển thị loading khi đang đọc file
with st.spinner('Đang tải và xử lý dữ liệu...'):
    df = load_and_process_data(DATA_FILE, CONFIG_FILE)

if df.empty:
    st.error("Không có dữ liệu để hiển thị. Vui lòng kiểm tra file đầu vào.")
    st.stop()

# 3. Sidebar - Bộ lọc Toàn cục (Global Filters)
st.sidebar.title("🔧 Điều khiển Dashboard")

# 3.1 Chọn Tab
tab_selection = st.sidebar.radio(
    "Chọn chức năng:",
    ["Overview", "Data (Pre-processing)", "Tab 1: Time Analysis", "Tab 2: Attribute Analysis"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("📅 Bộ lọc Thời gian (Toàn cục)")

# 3.2 Lọc ngày tháng
min_date = df['date'].min()
max_date = df['date'].max()

start_date = st.sidebar.date_input("Ngày bắt đầu", min_date)
end_date = st.sidebar.date_input("Ngày kết thúc", max_date)

# Filter dữ liệu theo ngày đã chọn (Filter này áp dụng cho TẤT CẢ các tab)
mask_date = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
df_filtered_date = df[mask_date]

st.sidebar.info(f"Đang hiển thị dữ liệu từ {start_date} đến {end_date}")
st.sidebar.text(f"Số dòng dữ liệu: {len(df_filtered_date)}")


# 4. Điều hướng nội dung chính
if tab_selection == "Overview":
    overview.render(df_filtered_date)

elif tab_selection == "Data (Pre-processing)":
    data_view.render(df_filtered_date)

elif tab_selection == "Tab 1: Time Analysis":
    # Truyền dữ liệu đã lọc theo ngày vào tab
    time_analysis.render(df_filtered_date)

elif tab_selection == "Tab 2: Attribute Analysis":
    attr_analysis.render(df_filtered_date)
