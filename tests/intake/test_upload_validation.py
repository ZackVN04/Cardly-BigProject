import pytest
from unittest.mock import patch, MagicMock
from fastapi import status

@pytest.fixture
def valid_image_content():
    # A small valid PNG transparent pixel
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

@pytest.fixture
def invalid_mime_content():
    return b'some random text content'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mocks(mock_save, mock_enqueue, mock_dedupe, mock_insert, url="http://fake-gcs/image.png"):
    """Configure standard happy-path mocks."""
    mock_save.return_value = url
    mock_enqueue.return_value = None
    mock_dedupe.return_value = None
    mock_insert.return_value = MagicMock()

# ---------------------------------------------------------------------------
# Single-file upload tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_valid_image(client, valid_image_content):
    with patch("src.intake.service.save_to_storage") as mock_save, \
         patch("src.intake.service.enqueue_pipeline_task") as mock_enqueue, \
         patch("src.intake.service.dedupe_by_hash") as mock_dedupe, \
         patch("src.intake.models.UploadedImage.insert") as mock_insert:

        _make_mocks(mock_save, mock_enqueue, mock_dedupe, mock_insert)

        files = {"file": ("test.png", valid_image_content, "image/png")}
        response = await client.post("/api/v1/documents", files=files)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "processing_id" in data
        # New shape: files is a list of {original_filename, file_url}
        assert isinstance(data["files"], list)
        assert len(data["files"]) == 1
        assert data["files"][0]["file_url"] == "http://fake-gcs/image.png"
        assert data["files"][0]["original_filename"] == "test.png"

        mock_save.assert_called_once()
        mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_too_large(client):
    # Create content larger than 10MB
    large_content = b"0" * (11 * 1024 * 1024)
    files = {"file": ("large.png", large_content, "image/png")}

    response = await client.post("/api/v1/documents", files=files)

    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert "File exceeds max size" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_mime(client, invalid_mime_content):
    files = {"file": ("test.txt", invalid_mime_content, "text/plain")}

    response = await client.post("/api/v1/documents", files=files)

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert "not allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_duplicate_file(client, valid_image_content):
    with patch("src.intake.service.dedupe_by_hash") as mock_dedupe:
        from fastapi import HTTPException
        mock_dedupe.side_effect = HTTPException(status_code=409, detail="Duplicate file detected")

        files = {"file": ("duplicate.png", valid_image_content, "image/png")}
        response = await client.post("/api/v1/documents", files=files)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Duplicate file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_corrupted_file(client):
    # Image header but random data
    corrupted_content = b'\x89PNG\r\n\x1a\n' + b'garbage' * 10
    files = {"file": ("corrupted.png", corrupted_content, "image/png")}

    response = await client.post("/api/v1/documents", files=files)

    # dependencies.py calls detect_corrupted which uses PIL.Image.open().verify()
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "corrupted or unreadable" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Multi-file (2 images) upload tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_two_images(client, valid_image_content):
    """Two valid images → 202 with two entries sharing the same processing_id."""
    with patch("src.intake.service.save_to_storage") as mock_save, \
         patch("src.intake.service.enqueue_pipeline_task") as mock_enqueue, \
         patch("src.intake.service.dedupe_by_hash") as mock_dedupe, \
         patch("src.intake.models.UploadedImage.insert") as mock_insert:

        # Return different URLs per call to distinguish file1 vs file2
        mock_save.side_effect = [
            "http://fake-gcs/front.png",
            "http://fake-gcs/back.png",
        ]
        mock_enqueue.return_value = None
        mock_dedupe.return_value = None
        mock_insert.return_value = MagicMock()

        files = [
            ("file",  ("front.png", valid_image_content, "image/png")),
            ("file2", ("back.png",  valid_image_content, "image/png")),
        ]
        response = await client.post("/api/v1/documents", files=files)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()

        assert "processing_id" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) == 2

        filenames = {entry["original_filename"] for entry in data["files"]}
        assert filenames == {"front.png", "back.png"}

        urls = {entry["file_url"] for entry in data["files"]}
        assert urls == {"http://fake-gcs/front.png", "http://fake-gcs/back.png"}

        # Pipeline is enqueued exactly once for the whole submission
        mock_enqueue.assert_called_once()
        # save_to_storage called twice, once per file
        assert mock_save.call_count == 2


@pytest.mark.asyncio
async def test_upload_second_file_invalid_mime(client, valid_image_content, invalid_mime_content):
    """First file valid, second file has an unsupported MIME → 415."""
    files = [
        ("file",  ("front.png", valid_image_content,   "image/png")),
        ("file2", ("back.txt",  invalid_mime_content,  "text/plain")),
    ]
    response = await client.post("/api/v1/documents", files=files)

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert "not allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_second_file_corrupted(client, valid_image_content):
    """First file valid, second file corrupted → 400."""
    corrupted_content = b'\x89PNG\r\n\x1a\n' + b'garbage' * 10
    files = [
        ("file",  ("front.png",     valid_image_content, "image/png")),
        ("file2", ("corrupted.png", corrupted_content,   "image/png")),
    ]
    response = await client.post("/api/v1/documents", files=files)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "corrupted or unreadable" in response.json()["detail"]
