import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import status
from beanie import PydanticObjectId
from src.intake.models import UploadedImage, ImageStatus

@pytest.mark.asyncio
async def test_get_image_urls_single(client):
    processing_id = "PRC-123"
    mock_doc = MagicMock(spec=UploadedImage)
    mock_doc.processing_id = processing_id
    mock_doc.storage_path = f"{processing_id}/test.png"
    mock_doc.status = ImageStatus.PROCESSED
    mock_doc.user_id = PydanticObjectId()

    with patch("src.intake.models.UploadedImage.find_one") as mock_find_one, \
         patch("src.intake.service.storage.Client") as mock_storage:
        
        mock_find_one.return_value = mock_doc
        
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.generate_signed_url.return_value = "http://signed-url/1"
        
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_storage.return_value = mock_client

        response = await client.get(f"/api/v1/documents/{processing_id}/image")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "urls" in data
        assert len(data["urls"]) == 1
        assert data["urls"][0] == "http://signed-url/1"

@pytest.mark.asyncio
async def test_get_image_urls_multiple(client):
    processing_id = "PRC-456"
    
    doc1 = MagicMock(spec=UploadedImage)
    doc1.processing_id = processing_id
    doc1.storage_path = f"{processing_id}/front.png"
    doc1.status = ImageStatus.PROCESSED
    doc1.user_id = PydanticObjectId()

    doc2 = MagicMock(spec=UploadedImage)
    doc2.processing_id = processing_id
    doc2.storage_path = f"{processing_id}/back.png"
    doc2.status = ImageStatus.PROCESSED
    doc2.user_id = PydanticObjectId()

    with patch("src.intake.models.UploadedImage.find_one") as mock_find_one, \
         patch("src.intake.models.UploadedImage.find") as mock_find, \
         patch("src.intake.service.storage.Client") as mock_storage:
        
        mock_find_one.return_value = None
        
        mock_find_query = MagicMock()
        mock_find_query.to_list = AsyncMock(return_value=[doc1, doc2])
        mock_find.return_value = mock_find_query
        
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.generate_signed_url.side_effect = ["http://signed-url/front", "http://signed-url/back"]
        
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_storage.return_value = mock_client

        response = await client.get(f"/api/v1/documents/{processing_id}/image")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "urls" in data
        assert len(data["urls"]) == 2
        assert "http://signed-url/front" in data["urls"]
        assert "http://signed-url/back" in data["urls"]

@pytest.mark.asyncio
async def test_get_image_urls_not_found(client):
    processing_id = "PRC-NOT-FOUND"
    
    with patch("src.intake.models.UploadedImage.find_one") as mock_find_one, \
         patch("src.intake.models.UploadedImage.find") as mock_find:
        
        mock_find_one.return_value = None
        mock_find_query = MagicMock()
        mock_find_query.to_list = AsyncMock(return_value=[])
        mock_find.return_value = mock_find_query

        response = await client.get(f"/api/v1/documents/{processing_id}/image")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
