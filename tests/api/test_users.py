from httpx import AsyncClient

from app.models.user import User


async def test_admin_creates_restricted_user(
    client: AsyncClient, admin_user: User, viewer_role, auth_headers
):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin_user),
        json={
            "email": "created-by-admin@example.com",
            "password": "newuserpass1",
            "full_name": "Created User",
            "role_name": viewer_role.name,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["organization_id"] == str(admin_user.organization_id)
    assert body["is_superuser"] is False


async def test_is_superuser_cannot_be_injected_via_request_body(
    client: AsyncClient, admin_user: User, viewer_role, auth_headers
):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin_user),
        json={
            "email": "sneaky-superuser@example.com",
            "password": "newuserpass1",
            "full_name": "Sneaky",
            "role_name": viewer_role.name,
            "is_superuser": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["is_superuser"] is False


async def test_viewer_without_permission_cannot_create_users(
    client: AsyncClient, viewer_user: User, viewer_role, auth_headers
):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(viewer_user),
        json={
            "email": "blocked@example.com",
            "password": "newuserpass1",
            "full_name": "Blocked",
            "role_name": viewer_role.name,
        },
    )
    assert response.status_code == 403


async def test_create_user_with_nonexistent_role_returns_404(
    client: AsyncClient, admin_user: User, auth_headers
):
    response = await client.post(
        "/api/v1/users",
        headers=auth_headers(admin_user),
        json={
            "email": "norole@example.com",
            "password": "newuserpass1",
            "full_name": "No Role",
            "role_name": "role-that-does-not-exist",
        },
    )
    assert response.status_code == 404


async def test_create_user_duplicate_email_returns_409(
    client: AsyncClient, admin_user: User, viewer_role, auth_headers
):
    payload = {
        "email": "dupuser@example.com",
        "password": "newuserpass1",
        "full_name": "Dup",
        "role_name": viewer_role.name,
    }
    await client.post("/api/v1/users", headers=auth_headers(admin_user), json=payload)
    response = await client.post("/api/v1/users", headers=auth_headers(admin_user), json=payload)
    assert response.status_code == 409


async def test_new_user_can_log_in_with_assigned_restricted_role(
    client: AsyncClient, admin_user: User, viewer_role, auth_headers
):
    await client.post(
        "/api/v1/users",
        headers=auth_headers(admin_user),
        json={
            "email": "loginflow@example.com",
            "password": "newuserpass1",
            "full_name": "Login Flow",
            "role_name": viewer_role.name,
        },
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "loginflow@example.com", "password": "newuserpass1"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/vulnerabilities", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
