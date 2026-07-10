import uuid

from httpx import AsyncClient

from app.models.source import Source
from app.models.user import User


async def test_admin_lists_sources(
    client: AsyncClient, admin_user: User, test_source: Source, auth_headers
):
    response = await client.get("/api/v1/sources", headers=auth_headers(admin_user))
    assert response.status_code == 200
    names = [source["name"] for source in response.json()]
    assert test_source.name in names


async def test_viewer_without_permission_cannot_list_sources(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.get("/api/v1/sources", headers=auth_headers(viewer_user))
    assert response.status_code == 403


async def test_get_source_by_id(
    client: AsyncClient, admin_user: User, test_source: Source, auth_headers
):
    response = await client.get(f"/api/v1/sources/{test_source.id}", headers=auth_headers(admin_user))
    assert response.status_code == 200
    assert response.json()["name"] == test_source.name


async def test_get_nonexistent_source_returns_404(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.get(f"/api/v1/sources/{uuid.uuid4()}", headers=auth_headers(admin_user))
    assert response.status_code == 404
