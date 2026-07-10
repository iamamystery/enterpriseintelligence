import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.organization import Organization
from app.models.user import User


async def test_admin_creates_asset(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers(admin_user),
        json={
            "name": "prod-web-01",
            "asset_type": "server",
            "vendor": "Acme",
            "product": "Widget Server",
            "version": "2.4.49",
            "ip_address": "10.0.0.5",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "prod-web-01"
    assert body["organization_id"] == str(admin_user.organization_id)
    assert body["is_active"] is True


async def test_viewer_without_permission_cannot_create_asset(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.post(
        "/api/v1/assets",
        headers=auth_headers(viewer_user),
        json={"name": "blocked-asset", "asset_type": "server"},
    )
    assert response.status_code == 403


async def test_list_assets_returns_only_own_organization(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    await client.post(
        "/api/v1/assets",
        headers=auth_headers(admin_user),
        json={"name": "own-org-asset", "asset_type": "server"},
    )

    other_org = Organization(name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}")
    db_session.add(other_org)
    await db_session.flush()
    db_session.add(Asset(name="other-org-asset", asset_type="server", organization_id=other_org.id))
    await db_session.flush()

    response = await client.get("/api/v1/assets", headers=auth_headers(admin_user))
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert "own-org-asset" in names
    assert "other-org-asset" not in names


async def test_viewer_without_permission_cannot_list_assets(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.get("/api/v1/assets", headers=auth_headers(viewer_user))
    assert response.status_code == 403


async def test_get_asset_by_id(client: AsyncClient, admin_user: User, auth_headers):
    create_response = await client.post(
        "/api/v1/assets",
        headers=auth_headers(admin_user),
        json={"name": "fetchable-asset", "asset_type": "workstation"},
    )
    asset_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers(admin_user))
    assert response.status_code == 200
    assert response.json()["name"] == "fetchable-asset"


async def test_get_asset_from_other_organization_returns_404(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    other_org = Organization(name="Another Org", slug=f"another-org-{uuid.uuid4().hex[:8]}")
    db_session.add(other_org)
    await db_session.flush()
    other_asset = Asset(name="cross-tenant-asset", asset_type="server", organization_id=other_org.id)
    db_session.add(other_asset)
    await db_session.flush()

    response = await client.get(f"/api/v1/assets/{other_asset.id}", headers=auth_headers(admin_user))
    assert response.status_code == 404


async def test_get_nonexistent_asset_returns_404(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.get(f"/api/v1/assets/{uuid.uuid4()}", headers=auth_headers(admin_user))
    assert response.status_code == 404
