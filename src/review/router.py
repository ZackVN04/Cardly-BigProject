from typing import Annotated

from fastapi import APIRouter, Depends

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.review import service
from src.review.models import (
    ConfirmResponse,
    ReviewResponse,
    ReviewUpdateRequest,
    ReviewUpdateResponse,
)

router = APIRouter()
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/{processing_id}/review",
    response_model=ReviewResponse,
    summary="Get or create a JSON review session",
)
async def get_review_session(
    processing_id: str,
    current_user: CurrentUser,
) -> ReviewResponse:
    """Return the structured JSON and review metadata for one document."""
    return await service.get_or_create_review_session(
        processing_id=processing_id,
        user_id=current_user.id,
    )


@router.patch(
    "/{processing_id}/review",
    response_model=ReviewUpdateResponse,
    summary="Update reviewed JSON fields",
)
async def update_review_session(
    processing_id: str,
    body: ReviewUpdateRequest,
    current_user: CurrentUser,
) -> ReviewUpdateResponse:
    """Apply JSON field edits and persist audit logs."""
    return await service.update_review_session(
        processing_id=processing_id,
        updates=body.updates,
        edited_by=str(current_user.id),
    )


@router.post(
    "/{processing_id}/confirm",
    response_model=ConfirmResponse,
    summary="Confirm reviewed JSON and lock the document",
)
async def confirm_review_session(
    processing_id: str,
    current_user: CurrentUser,
) -> ConfirmResponse:
    """Validate the final JSON and create immutable downstream data."""
    return await service.confirm_review_session(processing_id)
