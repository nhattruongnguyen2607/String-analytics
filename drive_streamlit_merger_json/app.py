# -*- coding: utf-8 -*-
import json
import os
import tempfile
from pathlib import Path

import streamlit as st

from drive_merge import merge_folder_to_excel

st.set_page_config(page_title="Drive Folder Merger", layout="centered")
st.title("Tổng hợp file trong Google Drive Folder")

st.write("Nhớ share folder cho **email service account** trước.")

folder_id = st.text_input("Google Drive Folder ID", value="1pqpMEVxsUerPCyECTqoh46XhjyU3Tc3Q")
recursive = st.checkbox("Quét cả subfolder (recursive)", value=True)

with st.expander("Tuỳ chọn nâng cao"):
    output_name = st.text_input("Tên file output", value="merged.xlsx")
    st.caption("Bạn có thể cấu hình SA theo JSON (ưu tiên theo thứ tự):")
    st.caption("1) env var GOOGLE_SERVICE_ACCOUNT_JSON (JSON string)")
    st.caption("2) st.secrets['service_account_json'] (JSON string)")
    st.caption("3) st.secrets['gcp_service_account'] (TOML table -> dict)")
    st.caption("4) Upload file service_account.json (chỉ dùng tạm, không khuyên khi deploy public)")

uploaded = st.file_uploader("Upload service_account.json (tuỳ chọn)", type=["json"])

def load_service_account_info() -> dict:
    # 1) env var chứa JSON string
    env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        return json.loads(env_json)

    # 2) secrets chứa JSON string (giữ nguyên "kiểu JSON")
    if "service_account_json" in st.secrets:
        v = st.secrets["service_account_json"]
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, dict):
            return v

    # 3) secrets dạng TOML table
    if "gcp_service_account" in st.secrets:
        v = st.secrets["gcp_service_account"]
        if isinstance(v, dict):
            return dict(v)

    # 4) upload file json (fallback)
    if uploaded is not None:
        return json.load(uploaded)

    raise RuntimeError("Chưa có credentials. Hãy set GOOGLE_SERVICE_ACCOUNT_JSON hoặc secrets hoặc upload file json.")

if st.button("Chạy tổng hợp"):
    try:
        sa_info = load_service_account_info()
    except Exception as e:
        st.error(str(e))
        st.stop()

    with st.spinner("Đang tải file và ghép dữ liệu..."):
        out_dir = Path(tempfile.mkdtemp())
        merged_path = merge_folder_to_excel(
            folder_id=folder_id,
            sa_info=sa_info,
            out_dir=out_dir,
            recursive=recursive,
            output_excel=output_name,
        )

    st.success("Xong! Bạn có thể tải file merged.")
    st.download_button(
        label=f"Tải {merged_path.name}",
        data=merged_path.read_bytes(),
        file_name=merged_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
