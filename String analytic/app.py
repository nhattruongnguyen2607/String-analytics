# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path

import streamlit as st

from drive_merge import merge_folder_to_excel

st.set_page_config(page_title="Drive Folder Merger", layout="centered")
st.title("Tổng hợp file trong Google Drive Folder")

st.write("Nhớ share folder cho **email service account** trước (xem README).")

folder_id = st.text_input("Google Drive Folder ID", value="1pqpMEVxsUerPCyECTqoh46XhjyU3Tc3Q")
recursive = st.checkbox("Quét cả subfolder (recursive)", value=True)

with st.expander("Tuỳ chọn nâng cao"):
    output_name = st.text_input("Tên file output", value="merged.xlsx")

if st.button("Chạy tổng hợp"):
    if "gcp_service_account" not in st.secrets:
        st.error("Chưa cấu hình Streamlit Secrets: gcp_service_account")
        st.stop()

    sa_info = dict(st.secrets["gcp_service_account"])

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
