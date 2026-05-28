import io
from fastapi import File, UploadFile, HTTPException, status
from . import service


async def valid_upload_file(file: UploadFile) -> UploadFile:
    """Dependency that performs basic validation on the uploaded file.
    It checks the MIME type, reads the content to check size and corruption,
    and resets the file stream so it can be read again in the router.
    """
    await service.validate_mime(file.content_type or "application/octet-stream")

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    await service.validate_size(len(content))
    await service.detect_corrupted(content, file.content_type or "application/octet-stream")
    await service.validate_file_format(content, file.content_type or "application/octet-stream")

    # Re-wrap content in a BytesIO so the router can 'read()' it again
    file.file = io.BytesIO(content)

    return file


async def valid_optional_upload_file(
    file2: UploadFile | str | None = File(default=None),
) -> UploadFile | None:
    """Dependency for the optional second file. Returns None when not provided
    (either as None, an empty string, or a file with an empty filename),
    or runs the same validation as valid_upload_file when present.
    """
    if file2 is None or isinstance(file2, str) or (isinstance(file2, UploadFile) and not file2.filename):
        return None
    return await valid_upload_file(file2)
