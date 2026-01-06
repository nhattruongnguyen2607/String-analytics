import streamlit as st
import plotly.express as px

def render(df):
    st.header("Tab 1: So sánh hiệu suất theo thời gian")

    # --- BỘ LỌC CỤ THỂ CHO TAB NÀY ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Lọc Plant (Mặc định lấy plant đầu tiên để biểu đồ không bị trống lúc đầu)
        plant_options = df['Plant'].unique()
        selected_plant = st.selectbox("Chọn Plant:", plant_options)
    
    # Lọc dữ liệu theo Plant trước để các filter sau chỉ hiện giá trị của Plant đó
    df_plant = df[df['Plant'] == selected_plant]

    with col2:
        # Lọc theo Capacity
        cap_options = sorted(df_plant['Capacity'].unique())
        selected_caps = st.multiselect("Lọc Capacity:", cap_options, default=cap_options)
    
    with col3:
        # Lọc theo Azimuth
        azimuth_options = sorted(df_plant['String Azimuth'].astype(str).unique())
        selected_azimuths = st.multiselect("Lọc Azimuth:", azimuth_options, default=azimuth_options)

    # Áp dụng bộ lọc
    mask = (
        (df_plant['Capacity'].isin(selected_caps)) & 
        (df_plant['String Azimuth'].astype(str).isin(selected_azimuths))
    )
    df_filtered = df_plant[mask]

    # --- VISUALIZATION ---
    st.subheader(f"Biểu đồ hiệu suất tại {selected_plant}")
    
    if df_filtered.empty:
        st.info("Không có dữ liệu phù hợp với bộ lọc.")
        return

    # Gom nhóm theo Inverter hoặc vẽ hết string (nếu vẽ hết string sẽ rất rối, nên gom nhóm hoặc cho chọn)
    view_mode = st.radio("Chế độ xem:", ["Trung bình theo Inverter", "Chi tiết từng String"], horizontal=True)

    if view_mode == "Trung bình theo Inverter":
        # Tính trung bình performance của Inverter theo ngày
        df_chart = df_filtered.groupby(['date', 'Inverter'])['Performance'].mean().reset_index()
        fig = px.line(df_chart, x='date', y='Performance', color='Inverter', 
                      title='Hiệu suất trung bình các Inverter theo ngày',
                      hover_data=['Performance'])
    else:
        # Chọn cụ thể Inverter để xem string bên trong (tránh lag nếu vẽ ngàn line)
        inverter_list = df_filtered['Inverter'].unique()
        selected_inv_for_detail = st.multiselect("Chọn Inverter để xem chi tiết String:", inverter_list, default=inverter_list[:1])
        
        df_chart = df_filtered[df_filtered['Inverter'].isin(selected_inv_for_detail)]
        fig = px.line(df_chart, x='date', y='Performance', color='label', 
                      title='Hiệu suất chi tiết từng String',
                      hover_data=['Capacity', 'String Azimuth'])

    st.plotly_chart(fig, use_container_width=True)
