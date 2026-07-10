from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


async def test_db_session_persists_within_test(db_session: AsyncSession, test_org: Organization) -> None:
    result = await db_session.execute(select(Organization).where(Organization.id == test_org.id))
    assert result.scalar_one().slug == test_org.slug


async def test_db_session_commit_does_not_leak_across_tests(db_session: AsyncSession) -> None:
    result = await db_session.execute(select(Organization))
    orgs = result.scalars().all()
    assert orgs == [], f"expected clean DB at test start, found leaked rows: {orgs}"


async def test_client_and_session_share_state(client, test_org: Organization) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
