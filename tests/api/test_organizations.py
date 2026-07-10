from httpx import AsyncClient

from app.models.organization import Organization
from app.models.user import User


async def test_get_my_organization_returns_own_org(
    client: AsyncClient, viewer_user: User, test_org: Organization, auth_headers
):
    response = await client.get("/api/v1/organizations/me", headers=auth_headers(viewer_user))
    assert response.status_code == 200
    assert response.json()["id"] == str(test_org.id)
    assert response.json()["slug"] == test_org.slug


async def test_get_my_organization_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/organizations/me")
    assert response.status_code in (401, 403)
