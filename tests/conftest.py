from collections.abc import AsyncGenerator

import pytest

_db_initialized = False


@pytest.fixture(autouse=True)
async def init_test_db(request: pytest.FixtureRequest):
    if request.node.get_closest_marker("no_db"):
        return

    global _db_initialized
    if not _db_initialized:
        from src.database import init_db
        await init_db()
        _db_initialized = True


@pytest.fixture
async def client() -> AsyncGenerator:
    # Only available for tests that need the full app (not no_db tests)
    from httpx import ASGITransport, AsyncClient
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
