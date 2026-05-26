import io
from fastapi import UploadFile, HTTPException, status
from . import service


async def valid_upload_file(file: UploadFile) -> UploadFile:
    """Dependency that performs basic validation on the uploaded file.
    It checks the MIME type, reads the content to check size and corruption,
    and resets the file stream so it can be read again in the router.
    """
    await service.validate_mime(file.content_type)

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    await service.validate_size(len(content))
    await service.detect_corrupted(content, file.content_type)
    await service.validate_file_format(content, file.content_type)

    # Re-wrap content in a BytesIO so the router can 'read()' it again
    file.file = io.BytesIO(content)

    return file


async def valid_optional_upload_file(
    file2: UploadFile | None = None,
) -> UploadFile | None:
    """Dependency for the optional second file. Returns None when not provided,
    or runs the same validation as valid_upload_file when present.
    """
    if file2 is None:
        return None
    return await valid_upload_file(file2)
