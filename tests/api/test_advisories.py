import uuid

from httpx import AsyncClient

from app.models.source import Source
from app.models.user import User


async def test_admin_creates_advisory(
    client: AsyncClient, admin_user: User, test_source: Source, auth_headers
):
    response = await client.post(
        "/api/v1/advisories",
        headers=auth_headers(admin_user),
        json={
            "advisory_id": "ICSA-24-123-01",
            "title": "Critical vulnerability in Acme Widget",
            "summary": "An attacker could exploit this to gain remote code execution.",
            "url": "https://www.cisa.gov/ICSA-24-123-01",
            "cve_ids": ["CVE-2024-12345"],
            "source_id": str(test_source.id),
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["advisory_id"] == "ICSA-24-123-01"
    assert body["cve_ids"] == ["CVE-2024-12345"]
    assert body["source_id"] == str(test_source.id)


async def test_create_advisory_duplicate_advisory_id_returns_409(
    client: AsyncClient, admin_user: User, test_source: Source, auth_headers
):
    payload = {
        "advisory_id": "ICSA-24-999-01",
        "title": "Some advisory",
        "summary": "Summary text.",
        "source_id": str(test_source.id),
    }
    await client.post("/api/v1/advisories", headers=auth_headers(admin_user), json=payload)
    response = await client.post("/api/v1/advisories", headers=auth_headers(admin_user), json=payload)
    assert response.status_code == 409


async def test_create_advisory_with_nonexistent_source_returns_404(
    client: AsyncClient, admin_user: User, auth_headers
):
    response = await client.post(
        "/api/v1/advisories",
        headers=auth_headers(admin_user),
        json={
            "advisory_id": "ICSA-24-888-01",
            "title": "Some advisory",
            "summary": "Summary text.",
            "source_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


async def test_viewer_without_permission_cannot_create_advisory(
    client: AsyncClient, viewer_user: User, test_source: Source, auth_headers
):
    response = await client.post(
        "/api/v1/advisories",
        headers=auth_headers(viewer_user),
        json={
            "advisory_id": "ICSA-24-000-01",
            "title": "Blocked",
            "summary": "Blocked.",
            "source_id": str(test_source.id),
        },
    )
    assert response.status_code == 403


async def test_list_advisories_filters_by_source(
    client: AsyncClient, admin_user: User, test_source: Source, db_session, auth_headers
):
    from app.models.advisory import Advisory
    from app.models.source import Source as SourceModel

    other_source = SourceModel(name="other-source", source_type="api", base_url="https://example.com")
    db_session.add(other_source)
    await db_session.flush()

    db_session.add(
        Advisory(
            advisory_id="ICSA-24-111-01",
            title="From test_source",
            summary="Summary.",
            source_id=test_source.id,
        )
    )
    db_session.add(
        Advisory(
            advisory_id="ICSA-24-222-01",
            title="From other_source",
            summary="Summary.",
            source_id=other_source.id,
        )
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/advisories",
        params={"source_id": str(test_source.id)},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert all(item["source_id"] == str(test_source.id) for item in body["items"])
    assert any(item["advisory_id"] == "ICSA-24-111-01" for item in body["items"])


async def test_viewer_without_permission_cannot_list_advisories(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.get("/api/v1/advisories", headers=auth_headers(viewer_user))
    assert response.status_code == 403


async def test_get_advisory_by_advisory_id(
    client: AsyncClient, admin_user: User, test_source: Source, auth_headers
):
    await client.post(
        "/api/v1/advisories",
        headers=auth_headers(admin_user),
        json={
            "advisory_id": "ICSA-24-555-01",
            "title": "Fetchable advisory",
            "summary": "Summary.",
            "source_id": str(test_source.id),
        },
    )

    response = await client.get("/api/v1/advisories/ICSA-24-555-01", headers=auth_headers(admin_user))
    assert response.status_code == 200
    assert response.json()["title"] == "Fetchable advisory"


async def test_get_nonexistent_advisory_returns_404(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.get(
        "/api/v1/advisories/ICSA-99-999-99", headers=auth_headers(admin_user)
    )
    assert response.status_code == 404
