import asyncio
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.database.postgres import get_db
from app.main import app
from app.models.organization import Organization
from app.models.role import Role
from app.models.source import Source
from app.models.user import User

TEST_DB_NAME = f"{settings.POSTGRES_DB}_test"
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{TEST_DB_NAME}"
)
TEST_SYNC_DATABASE_URL = (
    f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{TEST_DB_NAME}"
)


async def _ensure_test_database_exists() -> None:
    conn = await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database="postgres",
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


def _run_migrations() -> None:
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_SYNC_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def _setup_test_database() -> None:
    asyncio.run(_ensure_test_database_exists())
    _run_migrations()


@pytest.fixture(scope="session")
def test_engine() -> AsyncEngine:
    return create_async_engine(TEST_DATABASE_URL)


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    from app.api.dependencies import rate_limit as rate_limit_module

    rate_limit_module._general_limiter._hits.clear()
    rate_limit_module._auth_limiter._hits.clear()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession) -> Organization:
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


@pytest_asyncio.fixture
async def test_source(db_session: AsyncSession) -> Source:
    source = Source(
        name=f"test-source-{uuid.uuid4().hex[:8]}",
        source_type="api",
        base_url="https://example.com/api",
    )
    db_session.add(source)
    await db_session.flush()
    return source


@pytest_asyncio.fixture
async def admin_role(db_session: AsyncSession) -> Role:
    role = Role(name=f"admin-{uuid.uuid4().hex[:8]}", permissions=["*"])
    db_session.add(role)
    await db_session.flush()
    return role


@pytest_asyncio.fixture
async def viewer_role(db_session: AsyncSession) -> Role:
    role = Role(name=f"viewer-{uuid.uuid4().hex[:8]}", permissions=[])
    db_session.add(role)
    await db_session.flush()
    return role


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, test_org: Organization, admin_role: Role) -> User:
    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test Admin",
        organization_id=test_org.id,
        role_id=admin_role.id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession, test_org: Organization, viewer_role: Role) -> User:
    user = User(
        email=f"viewer-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test Viewer",
        organization_id=test_org.id,
        role_id=viewer_role.id,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
def auth_headers():
    def _make(user: User) -> dict[str, str]:
        token = create_access_token(str(user.id))
        return {"Authorization": f"Bearer {token}"}

    return _make
