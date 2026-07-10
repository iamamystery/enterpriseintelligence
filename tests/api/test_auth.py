from httpx import AsyncClient


async def test_register_returns_201_with_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "apiuser@example.com",
            "password": "correcthorsebattery",
            "full_name": "API User",
            "organization_name": "API Org",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "apiuser@example.com"
    assert body["is_superuser"] is False
    assert "hashed_password" not in body


async def test_register_duplicate_email_returns_409(client: AsyncClient):
    payload = {
        "email": "dupapi@example.com",
        "password": "correcthorsebattery",
        "full_name": "User",
        "organization_name": "Org",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


async def test_register_rejects_reserved_tld_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@company.local",
            "password": "correcthorsebattery",
            "full_name": "User",
            "organization_name": "Org",
        },
    )
    assert response.status_code == 422


async def test_login_returns_tokens(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "loginapi@example.com",
            "password": "correcthorsebattery",
            "full_name": "User",
            "organization_name": "Org",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "loginapi@example.com", "password": "correcthorsebattery"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_returns_401(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpwapi@example.com",
            "password": "correcthorsebattery",
            "full_name": "User",
            "organization_name": "Org",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpwapi@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


async def test_auth_endpoints_are_rate_limited(client: AsyncClient):
    from app.core.config import settings

    limit = settings.AUTH_RATE_LIMIT_PER_MINUTE
    for _ in range(limit):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@example.com", "password": "whatever"},
        )
        assert response.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": "ratelimit@example.com", "password": "whatever"},
    )
    assert blocked.status_code == 429
