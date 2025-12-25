# -*- coding: utf-8 -*-
import json
import os

import streamlit as st

from drive_merge import (
    drive_service_from_info,
    incremental_import,
    upload_streamlit_file_to_drive,
    find_file_in_folder,
    download_text_file,
)

st.set_page_config(page_title="Drive RAW Upload + Incremental Import", layout="centered")
st.title("Upload → RAW → Import (incremental) → Archive + Extract")

st.caption("Kiểu A: Upload file trên web → tự upload vào RAW_FOLDER_ID → tự Import Data.")

# ---------- Credentials loader (JSON style) ----------
def load_service_account_info() -> dict:
    env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env_json:
        return json.loads(env_json)

    if "service_account_json" in st.secrets:
        v = st.secrets["service_account_json"]
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, dict):
            return dict(v)

    raise RuntimeError("Chưa có credentials. Hãy set Secrets: service_account_json (JSON string).")


# ---------- Folder IDs ----------
RAW_FOLDER_ID = st.text_input("RAW_FOLDER_ID", placeholder="Folder ID chứa file raw (upload vào đây)")
ARCHIVE_FOLDER_ID = st.text_input("ARCHIVE_FOLDER_ID", placeholder="Folder ID chứa file đã xử lý")
EXTRACT_FOLDER_ID = st.text_input("EXTRACT_FOLDER_ID", placeholder="Folder ID chứa merged.csv + manifest.json")

st.divider()

# ---------- Upload UI ----------
st.subheader("1) Upload file")
uploaded_files = st.file_uploader(
    "Chọn file để upload (có thể chọn nhiều)",
    accept_multiple_files=True,
)

auto_import = st.checkbox("2) Tự chạy Import Data sau khi upload", value=True)

col1, col2 = st.columns(2)
with col1:
    run_btn = st.button("Upload & Import", type="primary")
with col2:
    import_only_btn = st.button("Chỉ Import (không upload)")

def validate_folder_ids():
    if not RAW_FOLDER_ID or not ARCHIVE_FOLDER_ID or not EXTRACT_FOLDER_ID:
        st.error("Bạn cần nhập đủ RAW_FOLDER_ID, ARCHIVE_FOLDER_ID, EXTRACT_FOLDER_ID.")
        st.stop()

def get_drive():
    sa_info = load_service_account_info()
    return drive_service_from_info(sa_info, readonly=False)

if run_btn:
    validate_folder_ids()
    if not uploaded_files:
        st.warning("Bạn chưa chọn file nào để upload.")
        st.stop()

    drive = get_drive()

    # Upload to RAW
    uploaded_list = []
    with st.spinner("Đang upload lên RAW folder..."):
        for f in uploaded_files:
            fid = upload_streamlit_file_to_drive(drive, RAW_FOLDER_ID, f)
            uploaded_list.append((f.name, fid))
    st.success(f"Đã upload {len(uploaded_list)} file vào RAW.")
    st.write(uploaded_list)

    # Auto import incremental
    if auto_import:
        with st.spinner("Đang Import Data (incremental) và cập nhật merged/manifest..."):
            stats = incremental_import(drive, RAW_FOLDER_ID, ARCHIVE_FOLDER_ID, EXTRACT_FOLDER_ID)
        st.success(f"Import xong! Đã xử lý: {stats['processed_now']} file. Tổng dòng: {stats['total_rows']}")

if import_only_btn:
    validate_folder_ids()
    drive = get_drive()
    with st.spinner("Đang Import Data (incremental) và cập nhật merged/manifest..."):
        stats = incremental_import(drive, RAW_FOLDER_ID, ARCHIVE_FOLDER_ID, EXTRACT_FOLDER_ID)
    st.success(f"Import xong! Đã xử lý: {stats['processed_now']} file. Tổng dòng: {stats['total_rows']}")

st.divider()

# ---------- Download merged ----------
st.subheader("Tải merged.csv (nếu đã có)")
if st.button("Download merged.csv"):
    validate_folder_ids()
    drive = get_drive()
    f = find_file_in_folder(drive, EXTRACT_FOLDER_ID, "merged.csv")
    if not f:
        st.warning("Chưa có merged.csv trong EXTRACT folder.")
    else:
        csv_text = download_text_file(drive, f["id"])
        st.download_button(
            "Tải merged.csv",
            data=csv_text.encode("utf-8"),
            file_name="merged.csv",
            mime="text/csv",
        )
