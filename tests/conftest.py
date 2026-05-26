from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.database import init_db


_db_initialized = False


@pytest.fixture(autouse=True)
async def init_test_db():
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
