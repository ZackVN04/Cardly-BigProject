# TODO(P2 — Phúc Khang): Implement upload file guard
from fastapi import UploadFile


async def valid_upload_file(file: UploadFile) -> UploadFile:
    # TODO: validate MIME, size, corruption
    return file
