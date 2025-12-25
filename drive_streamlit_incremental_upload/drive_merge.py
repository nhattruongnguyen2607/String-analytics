# -*- coding: utf-8 -*-
"""
drive_merge.py
- Upload file Streamlit lên Google Drive folder
- Incremental import: đọc RAW, chỉ xử lý file mới/đổi, cập nhật merged.csv + manifest.json trong EXTRACT,
  rồi move file đã xử lý sang ARCHIVE.

Hỗ trợ ghép dữ liệu bảng từ:
- CSV
- Excel (.xlsx/.xls)
- Google Sheets (export .xlsx)
- JSON dạng bảng (list[dict] hoặc dict chứa list[dict])
"""

import io
import json
import mimetypes
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaInMemoryUpload, MediaIoBaseUpload

FOLDER_MIME = "application/vnd.google-apps.folder"

GOOGLE_EXPORTS = {
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


def safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:\*\?\"<>\|]+", "_", name)
    return name[:200] if len(name) > 200 else name


def normalize_private_key(sa_info: dict) -> dict:
    sa_info = dict(sa_info)
    pk = sa_info.get("private_key")
    if isinstance(pk, str) and "\\n" in pk and "-----BEGIN PRIVATE KEY-----" in pk:
        sa_info["private_key"] = pk.replace("\\n", "\n")
    return sa_info


def drive_service_from_info(sa_info: dict, readonly: bool = False):
    """
    readonly=False vì cần upload/move/update.
    """
    sa_info = normalize_private_key(sa_info)
    scopes = ["https://www.googleapis.com/auth/drive"] if not readonly else ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_children(drive, folder_id: str) -> List[Dict]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "nextPageToken, files(id, name, mimeType, size, modifiedTime)"
    out: List[Dict] = []
    page_token = None
    while True:
        resp = drive.files().list(
            q=q,
            fields=fields,
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def download_one(drive, file_meta: Dict, out_dir: Path) -> Optional[Path]:
    file_id = file_meta["id"]
    name = safe_filename(file_meta["name"])
    mime = file_meta["mimeType"]

    if mime == FOLDER_MIME:
        return None

    if mime in GOOGLE_EXPORTS:
        export_mime, ext = GOOGLE_EXPORTS[mime]
        local_path = out_dir / f"{name}{ext}"
        request = drive.files().export_media(fileId=file_id, mimeType=export_mime)
    else:
        local_path = out_dir / name
        request = drive.files().get_media(fileId=file_id)

    fh = io.FileIO(local_path, "wb")
    downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
    done = False
    try:
        while not done:
            _, done = downloader.next_chunk()
    finally:
        fh.close()

    return local_path


def try_read_tabular(path: Path) -> List[pd.DataFrame]:
    ext = path.suffix.lower()
    dfs: List[pd.DataFrame] = []

    try:
        if ext == ".csv":
            dfs.append(pd.read_csv(path))
        elif ext in (".xlsx", ".xls"):
            xls = pd.ExcelFile(path)
            for sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet)
                df["__source_sheet"] = sheet
                dfs.append(df)
        elif ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)

            if isinstance(obj, list) and (len(obj) == 0 or isinstance(obj[0], dict)):
                dfs.append(pd.DataFrame(obj))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, list) and (len(v) == 0 or isinstance(v[0], dict)):
                        df = pd.DataFrame(v)
                        df["__json_key"] = k
                        dfs.append(df)
                        break
    except Exception:
        return []

    return dfs


# --------- Drive helper for manifest / upload bytes/text ----------

def find_file_in_folder(drive, folder_id: str, filename: str):
    q = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    resp = drive.files().list(
        q=q,
        fields="files(id,name,mimeType,modifiedTime)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = resp.get("files", [])
    return files[0] if files else None


def download_text_file(drive, file_id: str) -> str:
    request = drive.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue().decode("utf-8")


def upload_text_file(drive, folder_id: str, filename: str, text: str, mimetype="application/json"):
    existing = find_file_in_folder(drive, folder_id, filename)
    media = MediaInMemoryUpload(text.encode("utf-8"), mimetype=mimetype, resumable=False)
    if existing:
        drive.files().update(fileId=existing["id"], media_body=media, supportsAllDrives=True).execute()
        return existing["id"]
    body = {"name": filename, "parents": [folder_id]}
    return drive.files().create(body=body, media_body=media, fields="id", supportsAllDrives=True).execute()["id"]


def upload_bytes_file(drive, folder_id: str, filename: str, data: bytes, mimetype: str):
    existing = find_file_in_folder(drive, folder_id, filename)
    media = MediaInMemoryUpload(data, mimetype=mimetype, resumable=False)
    if existing:
        drive.files().update(fileId=existing["id"], media_body=media, supportsAllDrives=True).execute()
        return existing["id"]
    body = {"name": filename, "parents": [folder_id]}
    return drive.files().create(body=body, media_body=media, fields="id", supportsAllDrives=True).execute()["id"]


def move_file(drive, file_id: str, from_folder_id: str, to_folder_id: str):
    drive.files().update(
        fileId=file_id,
        addParents=to_folder_id,
        removeParents=from_folder_id,
        supportsAllDrives=True,
    ).execute()


def load_manifest(drive, extract_folder_id: str) -> dict:
    mf = find_file_in_folder(drive, extract_folder_id, "manifest.json")
    if not mf:
        return {"processed": {}}
    try:
        return json.loads(download_text_file(drive, mf["id"]))
    except Exception:
        return {"processed": {}}


# --------- Upload from Streamlit ----------

def upload_streamlit_file_to_drive(drive, folder_id: str, uploaded_file) -> str:
    """
    Upload file-like object from streamlit uploader to RAW folder.
    """
    filename = uploaded_file.name
    mime, _ = mimetypes.guess_type(filename)
    if mime is None:
        mime = "application/octet-stream"

    media = MediaIoBaseUpload(uploaded_file, mimetype=mime, resumable=True)
    body = {"name": filename, "parents": [folder_id]}
    created = drive.files().create(
        body=body,
        media_body=media,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()
    return created["id"]


# --------- Incremental import core ----------

def incremental_import(
    drive,
    raw_folder_id: str,
    archive_folder_id: str,
    extract_folder_id: str,
) -> Dict[str, int]:
    """
    - Quét RAW folder
    - So với manifest.json (EXTRACT) -> chỉ xử lý file mới/đổi
    - Append vào merged.csv (EXTRACT)
    - Cập nhật manifest.json
    - Move file đã xử lý từ RAW -> ARCHIVE
    """
    manifest = load_manifest(drive, extract_folder_id)
    processed = manifest.get("processed", {})

    raw_files = [f for f in list_children(drive, raw_folder_id) if f.get("mimeType") != FOLDER_MIME]

    to_process: List[Dict] = []
    for f in raw_files:
        prev = processed.get(f["id"])
        if (prev is None) or (prev.get("modifiedTime") != f.get("modifiedTime")):
            to_process.append(f)

    # load existing merged.csv
    merged_existing = find_file_in_folder(drive, extract_folder_id, "merged.csv")
    if merged_existing:
        merged_csv = download_text_file(drive, merged_existing["id"])
        try:
            merged_df = pd.read_csv(io.StringIO(merged_csv))
        except Exception:
            merged_df = pd.DataFrame()
    else:
        merged_df = pd.DataFrame()

    new_parts: List[pd.DataFrame] = []
    tmpdir = Path(tempfile.mkdtemp())

    for meta in to_process:
        local_path = download_one(drive, meta, tmpdir)
        if local_path is not None:
            for df in try_read_tabular(local_path):
                df["__source_file"] = meta["name"]
                df["__source_id"] = meta["id"]
                df["__modifiedTime"] = meta.get("modifiedTime")
                new_parts.append(df)

        processed[meta["id"]] = {
            "modifiedTime": meta.get("modifiedTime"),
            "name": meta.get("name"),
            "mimeType": meta.get("mimeType"),
        }

        # move file after processing
        move_file(drive, meta["id"], raw_folder_id, archive_folder_id)

    if new_parts:
        add_df = pd.concat(new_parts, ignore_index=True, sort=False)
        merged_df = pd.concat([merged_df, add_df], ignore_index=True, sort=False)

    # upload merged.csv + manifest.json
    merged_bytes = merged_df.to_csv(index=False).encode("utf-8")
    upload_bytes_file(drive, extract_folder_id, "merged.csv", merged_bytes, "text/csv")

    manifest["processed"] = processed
    upload_text_file(drive, extract_folder_id, "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return {"processed_now": len(to_process), "total_rows": int(len(merged_df))}
