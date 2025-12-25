# -*- coding: utf-8 -*-
"""
drive_merge.py
Tải file từ Google Drive folder + ghép dữ liệu bảng -> merged.xlsx

Nhận service account dưới dạng dict JSON (sa_info).
"""

import io
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

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
    """
    Một số nơi lưu private_key dạng có '\\n' trong chuỗi.
    Hàm này đổi về newline thật để google-auth đọc được.
    """
    sa_info = dict(sa_info)
    pk = sa_info.get("private_key")
    if isinstance(pk, str) and "\\n" in pk and "-----BEGIN PRIVATE KEY-----" in pk:
        sa_info["private_key"] = pk.replace("\\n", "\n")
    return sa_info


def drive_service_from_info(sa_info: dict, readonly: bool = True):
    sa_info = normalize_private_key(sa_info)
    scopes = ["https://www.googleapis.com/auth/drive.readonly"] if readonly else ["https://www.googleapis.com/auth/drive"]
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


def walk_folder(drive, folder_id: str, recursive: bool) -> List[Dict]:
    results: List[Dict] = []
    stack = [folder_id]
    while stack:
        fid = stack.pop()
        children = list_children(drive, fid)
        for f in children:
            if f["mimeType"] == FOLDER_MIME and recursive:
                stack.append(f["id"])
            else:
                results.append(f)
    return results


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


def merge_folder_to_excel(
    folder_id: str,
    sa_info: dict,
    out_dir: Path,
    recursive: bool = True,
    output_excel: str = "merged.xlsx",
) -> Path:
    out_dir = Path(out_dir)
    download_dir = out_dir / "downloaded_files"
    download_dir.mkdir(parents=True, exist_ok=True)

    drive = drive_service_from_info(sa_info, readonly=True)
    all_files = walk_folder(drive, folder_id, recursive=recursive)

    downloaded: List[Path] = []
    for meta in all_files:
        p = download_one(drive, meta, download_dir)
        if p is not None:
            downloaded.append(p)

    merged_parts: List[pd.DataFrame] = []
    for p in downloaded:
        for df in try_read_tabular(p):
            df["__source_file"] = p.name
            merged_parts.append(df)

    merged_path = out_dir / output_excel
    if merged_parts:
        merged_df = pd.concat(merged_parts, ignore_index=True, sort=False)
        with pd.ExcelWriter(merged_path, engine="openpyxl") as writer:
            merged_df.to_excel(writer, index=False, sheet_name="merged")
    else:
        with pd.ExcelWriter(merged_path, engine="openpyxl") as writer:
            pd.DataFrame({"note": ["Không tìm thấy file dạng bảng để ghép (CSV/Excel/Sheets/JSON bảng)."]}).to_excel(
                writer, index=False, sheet_name="merged"
            )

    return merged_path
