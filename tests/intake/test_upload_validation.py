# TODO(P2 — Phúc Khang): Implement intake tests
import pytest


@pytest.mark.asyncio
async def test_upload_valid_image(client):
    pass


@pytest.mark.asyncio
async def test_upload_file_too_large(client):
    pass


@pytest.mark.asyncio
async def test_upload_invalid_mime(client):
    pass


@pytest.mark.asyncio
async def test_upload_duplicate_file(client):
    pass


@pytest.mark.asyncio
async def test_upload_corrupted_file(client):
    pass
