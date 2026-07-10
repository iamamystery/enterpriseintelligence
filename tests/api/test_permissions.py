from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role
from app.models.user import User


async def test_admin_with_wildcard_permission_can_access(
    client: AsyncClient, admin_user: User, auth_headers
):
    response = await client.get("/api/v1/vulnerabilities", headers=auth_headers(admin_user))
    assert response.status_code == 200


async def test_viewer_without_permission_gets_403(client: AsyncClient, viewer_user: User, auth_headers):
    response = await client.get("/api/v1/vulnerabilities", headers=auth_headers(viewer_user))
    assert response.status_code == 403
    assert "vulnerabilities:read" in response.json()["detail"]


async def test_viewer_denied_on_detail_endpoint_too(client: AsyncClient, viewer_user: User, auth_headers):
    response = await client.get(
        "/api/v1/vulnerabilities/CVE-2021-44228", headers=auth_headers(viewer_user)
    )
    assert response.status_code == 403


async def test_superuser_bypasses_permission_check_despite_empty_role(
    client: AsyncClient,
    db_session: AsyncSession,
    test_org,
    viewer_role: Role,
    auth_headers,
):
    from app.core.security import hash_password

    superuser = User(
        email="superuser-test@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Superuser",
        organization_id=test_org.id,
        role_id=viewer_role.id,
        is_superuser=True,
    )
    db_session.add(superuser)
    await db_session.flush()

    response = await client.get("/api/v1/vulnerabilities", headers=auth_headers(superuser))
    assert response.status_code == 200


async def test_missing_token_returns_401(client: AsyncClient):
    response = await client.get("/api/v1/vulnerabilities")
    assert response.status_code in (401, 403)


async def test_garbage_token_returns_401(client: AsyncClient):
    response = await client.get(
        "/api/v1/vulnerabilities", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
