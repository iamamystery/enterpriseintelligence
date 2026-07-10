import uuid

from httpx import AsyncClient

from app.models.user import User


async def test_admin_creates_role(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.post(
        "/api/v1/roles",
        headers=auth_headers(admin_user),
        json={"name": "analyst", "permissions": ["vulnerabilities:read"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "analyst"
    assert body["permissions"] == ["vulnerabilities:read"]


async def test_create_role_duplicate_name_returns_409(
    client: AsyncClient, admin_user: User, auth_headers
):
    payload = {"name": "duplicate-role", "permissions": []}
    await client.post("/api/v1/roles", headers=auth_headers(admin_user), json=payload)
    response = await client.post("/api/v1/roles", headers=auth_headers(admin_user), json=payload)
    assert response.status_code == 409


async def test_viewer_without_permission_cannot_create_role(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.post(
        "/api/v1/roles",
        headers=auth_headers(viewer_user),
        json={"name": "should-not-exist", "permissions": []},
    )
    assert response.status_code == 403


async def test_list_roles_returns_created_roles(client: AsyncClient, admin_user: User, auth_headers):
    await client.post(
        "/api/v1/roles",
        headers=auth_headers(admin_user),
        json={"name": "listed-role", "permissions": []},
    )
    response = await client.get("/api/v1/roles", headers=auth_headers(admin_user))
    assert response.status_code == 200
    names = [role["name"] for role in response.json()]
    assert "listed-role" in names


async def test_viewer_without_permission_cannot_list_roles(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.get("/api/v1/roles", headers=auth_headers(viewer_user))
    assert response.status_code == 403


async def test_get_role_by_id(client: AsyncClient, admin_user: User, auth_headers):
    create_response = await client.post(
        "/api/v1/roles",
        headers=auth_headers(admin_user),
        json={"name": "fetchable-role", "permissions": ["sources:read"]},
    )
    role_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/roles/{role_id}", headers=auth_headers(admin_user))
    assert response.status_code == 200
    assert response.json()["name"] == "fetchable-role"


async def test_get_nonexistent_role_returns_404(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.get(f"/api/v1/roles/{uuid.uuid4()}", headers=auth_headers(admin_user))
    assert response.status_code == 404
