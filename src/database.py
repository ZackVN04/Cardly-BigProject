from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from src.config import settings
from src.auth.models import User, RefreshToken, OtpCode, PasswordResetSession
from src.intake.models import UploadedImage
from src.preprocess.models import PreprocessedImage
from src.ocr.models import OcrResult, AiVisionResult, BusinessCardScan
from src.mapping.models import MappedDocument
from src.confidence.models import ConfidenceReport, ProcessingHistory
from src.review.models import JsonReviewSession, FinalizedDocument

ALL_DOCUMENTS = [
    User,
    RefreshToken,
    OtpCode,
    PasswordResetSession,
    UploadedImage,
    PreprocessedImage,
    OcrResult,
    BusinessCardScan,
    AiVisionResult,
    MappedDocument,
    ConfidenceReport,
    ProcessingHistory,
    JsonReviewSession,
    FinalizedDocument,
]


async def init_db() -> None:
    client: AsyncIOMotorClient = AsyncIOMotorClient(str(settings.MONGODB_URL))
    await init_beanie(database=client.ocr_db, document_models=ALL_DOCUMENTS)
