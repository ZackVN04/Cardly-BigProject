
from google.cloud import storage
from google.oauth2 import service_account
import json, os, sys

raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
print("Env var present:", bool(raw))

if not raw:
    print("GOOGLE_SERVICE_ACCOUNT_JSON is not set")
    sys.exit(1)

info = json.loads(raw)
credentials = service_account.Credentials.from_service_account_info(info)
client = storage.Client(credentials=credentials, project=info.get("project_id"))

# Thay <YOUR_BUCKET> bằng tên bucket thực của bạn
bucket = client.bucket("cardly-images-bucket")
if not bucket.exists():
    print("Bucket không tồn tại hoặc key không có quyền")
else:
    print("Bucket tồn tại – key và quyền OK")