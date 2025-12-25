# Drive Folder Merger (Streamlit) – dùng Service Account kiểu JSON

App Streamlit để tải và tổng hợp (ghép) dữ liệu dạng bảng từ một Google Drive folder.

## Bắt buộc: Share folder cho Service Account
Mở folder trên Google Drive → Share → thêm email service account → quyền Viewer.

## Cấu hình credentials theo "kiểu JSON"
Bạn có 3 cách (khuyên dùng 1 hoặc 2):

### Cách 1 (khuyên dùng khi deploy): env var
Set biến môi trường `GOOGLE_SERVICE_ACCOUNT_JSON` là **JSON string** của service account.

### Cách 2 (Streamlit Secrets): lưu JSON string
Trong Streamlit Community Cloud → App → Settings → Secrets, dán:

```toml
service_account_json = """{ 
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "...",
  "client_id": "...",
  "token_uri": "https://oauth2.googleapis.com/token"
}"""
```

> Lưu ý: vẫn là **JSON**, chỉ được bọc trong TOML string để Streamlit nhận.

### Cách 3: TOML table (truyền thống)
```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

## Chạy local
```bash
pip install -r requirements.txt
streamlit run app.py
```
