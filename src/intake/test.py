
from google.cloud import storage
import os, sys

print("Env var:", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
client = storage.Client()            # sẽ đọc key từ biến trên
# Thay <YOUR_BUCKET> bằng tên bucket thực của bạn
bucket = client.bucket("cardly-images-bucket")
if not bucket.exists():
    print("Bucket không tồn tại hoặc key không có quyền")
else:
    print("Bucket tồn tại – key và quyền OK")