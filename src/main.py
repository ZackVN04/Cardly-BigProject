from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.constants import SHOW_DOCS_ENVIRONMENTS
from src.database import init_db
from src.exceptions import AppException, app_exception_handler, unhandled_exception_handler

# Routers — uncomment each as the package is implemented
from src.auth.router import router as auth_router
from src.intake.router import router as intake_router
from src.confidence.router import router as confidence_router
from src.review.router import router as review_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield


app_configs: dict = {
    "title": "OCR Document Processing API",
    "version": settings.APP_VERSION,
    "lifespan": lifespan,
}
if settings.ENVIRONMENT not in SHOW_DOCS_ENVIRONMENTS:
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]

app.include_router(auth_router,       prefix="/api/v1/auth",      tags=["auth"])
app.include_router(intake_router,     prefix="/api/v1/documents", tags=["documents"])
app.include_router(confidence_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(review_router,     prefix="/api/v1/documents", tags=["review"])


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/api/v1/health/db", tags=["health"])
async def health_db() -> dict:
    from src.database import ALL_DOCUMENTS
    try:
        await ALL_DOCUMENTS[0].find_one()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
