# Streamlit - Drive RAW Upload -> Incremental Import -> Archive + Extract

## Mục tiêu
- Upload file ngay trên Streamlit
- File được upload lên Google Drive RAW folder
- App tự chạy incremental import:
  - chỉ xử lý file mới/đổi (theo modifiedTime)
  - cập nhật `merged.csv` + `manifest.json` trong EXTRACT folder
  - move file đã xử lý từ RAW sang ARCHIVE

## 1) Chuẩn bị 3 folder Drive
- RAW_FOLDER_ID: nơi bạn upload file (input)
- ARCHIVE_FOLDER_ID: nơi chứa file đã xử lý (processed)
- EXTRACT_FOLDER_ID: nơi chứa output: merged.csv và manifest.json

Share cả 3 folder cho email service account với quyền **Editor**.

## 2) Cấu hình secrets theo kiểu JSON (Streamlit Cloud)
Vào App -> Settings -> Secrets và dán:

```toml
service_account_json = '''{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
  "client_email": "...@...iam.gserviceaccount.com",
  "client_id": "...",
  "token_uri": "https://oauth2.googleapis.com/token"
}'''
```

## 3) Chạy local
Tạo `.streamlit/secrets.toml` giống như trên rồi chạy:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 4) Ghi chú
- Output mặc định là `merged.csv` để nhẹ và append nhanh.
- Bạn có thể bấm "Download merged.csv" để tải về.


## Nếu gặp lỗi khi upload (ResumableUploadError / 403 / 404)
- Đảm bảo service account được share **Editor** cho RAW/ARCHIVE/EXTRACT folder.
- Nếu folder nằm trong **Shared Drive**, hãy add service account như **member** của Shared Drive (không chỉ share folder).
- Kiểm tra RAW_FOLDER_ID đúng là **folder** (không phải file).
