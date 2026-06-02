#!/bin/sh
set -e

if [ -n "$FASTAPI_UPLOADER_JSON_B64" ]; then
  echo "$FASTAPI_UPLOADER_JSON_B64" | base64 -d > /tmp/fastapi-uploader.json
  export GOOGLE_APPLICATION_CREDENTIALS=/tmp/fastapi-uploader.json
fi

exec "$@"