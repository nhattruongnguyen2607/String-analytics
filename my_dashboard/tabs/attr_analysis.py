import streamlit as st
import plotly.express as px

def render(df):
    st.header("Tab 2: Phân tích theo Đặc tính (Capacity & Azimuth)")

    # Sử dụng lại dữ liệu đã lọc toàn cục hoặc cho lọc riêng tại đây
    # Ở đây tôi làm bộ lọc nhanh để user tập trung vào so sánh
    
    plants = st.multiselect("Chọn Plant để so sánh:", df['Plant'].unique(), default=df['Plant'].unique()[:1])
    df_filtered = df[df['Plant'].isin(plants)]

    if df_filtered.empty:
        st.write("Vui lòng chọn Plant.")
        return

    col1, col2 = st.columns(2)

    # 1. Biểu đồ phân tán: Performance vs Capacity
    with col1:
        st.subheader("Hiệu suất vs Capacity")
        # Tính trung bình hiệu suất của mỗi string trong khoảng thời gian đã chọn
        df_agg_cap = df_filtered.groupby(['label', 'Capacity', 'Plant'])['Performance'].mean().reset_index()
        
        fig_cap = px.scatter(df_agg_cap, x="Capacity", y="Performance", color="Plant",
                             hover_data=['label'],
                             title="Phân bố Hiệu suất theo Capacity")
        st.plotly_chart(fig_cap, use_container_width=True)

    # 2. Biểu đồ hộp (Boxplot): Performance vs Azimuth
    with col2:
        st.subheader("Hiệu suất vs Azimuth")
        # Convert Azimuth về string để vẽ dạng phân loại
        df_filtered['String Azimuth Str'] = df_filtered['String Azimuth'].astype(str)
        
        fig_azi = px.box(df_filtered, x="String Azimuth Str", y="Performance", color="Plant",
                         title="Phân bố Hiệu suất theo Hướng (Azimuth)")
        st.plotly_chart(fig_azi, use_container_width=True)
