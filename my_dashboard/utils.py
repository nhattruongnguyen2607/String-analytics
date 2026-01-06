import pandas as pd
import streamlit as st

@st.cache_data
def load_and_process_data(data_path, config_path):
    """
    Hàm đọc, gộp và xử lý dữ liệu.
    Sử dụng @st.cache_data để không phải load lại mỗi khi tương tác.
    """
    try:
        # 1. Đọc dữ liệu
        df_data = pd.read_csv(data_path)
        df_config = pd.read_csv(config_path)

        # 2. Chuẩn hóa cột label
        df_data['label'] = df_data['label'].astype(str).str.strip()
        df_config['label'] = df_config['label'].astype(str).str.strip()

        # 3. Merge dữ liệu
        df_merged = pd.merge(df_data, df_config, on='label', how='inner')

        # 4. Xử lý giá trị thiếu (NA) cho String Tilt và Azimuth
        cols_to_fill = ['String Tilt', 'String Azimuth']
        df_merged[cols_to_fill] = df_merged[cols_to_fill].fillna('NA')
        
        # 5. Chuyển đổi cột Date sang dạng datetime
        # Giả định format trong file là dd/mm/yyyy H:M
        df_merged['date'] = pd.to_datetime(df_merged['date'], dayfirst=True)

        return df_merged
    except Exception as e:
        st.error(f"Lỗi khi xử lý dữ liệu: {e}")
        return pd.DataFrame()
