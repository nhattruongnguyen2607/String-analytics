# Drive Folder Merger (Streamlit)

App Streamlit để tải và tổng hợp (ghép) dữ liệu dạng bảng từ một Google Drive folder.

## 1) Bắt buộc: Share folder cho Service Account
Mở folder trên Google Drive → Share → thêm email service account (trong JSON của bạn) → quyền Viewer.

## 2) Cấu hình Secrets (không commit key)
Tạo file `.streamlit/secrets.toml` (local) hoặc dán vào Secrets trên Streamlit Community Cloud:

```toml
[gcp_service_account]
type = "service_account"
project_id = "xxx"
private_key_id = "xxx"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "xxx@xxx.iam.gserviceaccount.com"
client_id = "xxx"
token_uri = "https://oauth2.googleapis.com/token"
```

## 3) Chạy local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 4) Deploy Streamlit Community Cloud
- Push repo lên GitHub
- Tạo app mới, chọn `app.py`
- Add Secrets như trên
