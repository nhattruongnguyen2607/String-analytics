import json
import time
import streamlit as st
from drive_merge import merge_folder_to_excel
from pathlib import Path
import tempfile

def load_sa_info() -> dict:
    # ưu tiên dùng JSON string trong secrets
    if "service_account_json" in st.secrets:
        v = st.secrets["service_account_json"]
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, dict):
            return dict(v)
    raise RuntimeError("Chưa có service_account_json trong Secrets")

# cache kết quả ghép trong 10 phút để tránh rerun liên tục
@st.cache_data(ttl=600, show_spinner=False)
def run_merge_cached(folder_id: str, recursive: bool, output_name: str, refresh_nonce: int) -> bytes:
    sa_info = load_sa_info()
    out_dir = Path(tempfile.mkdtemp())
    merged_path = merge_folder_to_excel(
        folder_id=folder_id,
        sa_info=sa_info,
        out_dir=out_dir,
        recursive=recursive,
        output_excel=output_name,
    )
    return merged_path.read_bytes()

# ---------- UI ----------
folder_id = st.text_input("Google Drive Folder ID", value="1pqpMEVxsUerPCyECTqoh46XhjyU3Tc3Q")
recursive = st.checkbox("Quét cả subfolder", value=True)
output_name = st.text_input("Tên file output", value="merged.xlsx")

# refresh_nonce để “đập cache” khi bấm refresh
if "refresh_nonce" not in st.session_state:
    st.session_state.refresh_nonce = 0

col1, col2 = st.columns(2)
with col1:
    auto_run = st.checkbox("Tự động chạy khi vào trang", value=True)
with col2:
    if st.button("Refresh dữ liệu ngay"):
        st.session_state.refresh_nonce += 1

# auto chạy 1 lần mỗi session (mỗi lượt vào trang)
if auto_run and "has_run_once" not in st.session_state:
    st.session_state.has_run_once = True
    st.session_state.refresh_nonce += 1  # kích hoạt chạy lần đầu

# chạy khi refresh_nonce thay đổi
if st.session_state.refresh_nonce > 0:
    with st.spinner("Đang tải & ghép dữ liệu..."):
        data = run_merge_cached(folder_id, recursive, output_name, st.session_state.refresh_nonce)
    st.success("Xong!")
    st.download_button(
        "Tải merged.xlsx",
        data=data,
        file_name=output_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
