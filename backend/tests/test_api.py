"""API integration tests."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.models.database import Base, get_db
from app.core.config import settings

TEST_DB = "sqlite+aiosqlite:///./test.db"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_user(client):
    res = await client.post("/api/users/", json={"username": "testuser"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "testuser"
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_get_user_not_found(client):
    res = await client.get("/api/users/9999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_vocabulary_workflow(client):
    # Create user
    res = await client.post("/api/users/", json={"username": "vocabuser"})
    user_id = res.json()["id"]

    # List empty vocabulary
    res = await client.get(f"/api/words/{user_id}")
    assert res.status_code == 200
    assert res.json() == []

    # No due words
    res = await client.get(f"/api/words/{user_id}/due")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_conversations(client):
    res = await client.post("/api/users/", json={"username": "chatuser"})
    user_id = res.json()["id"]

    res = await client.get(f"/api/chat/conversations/{user_id}")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_dashboard(client):
    res = await client.post("/api/users/", json={"username": "dashuser"})
    user_id = res.json()["id"]

    res = await client.get(f"/api/dashboard/{user_id}")
    assert res.status_code == 200
    data = res.json()
    assert "total_words" in data
    assert "accuracy" in data
    assert "weekly_trend" in data
