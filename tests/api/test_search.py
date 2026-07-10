import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.advisory import Advisory
from app.models.asset import Asset
from app.models.organization import Organization
from app.models.source import Source
from app.models.user import User
from app.models.vulnerability import Vulnerability


async def _seed_log4j_data(db_session: AsyncSession, organization_id) -> None:
    source = Source(name=f"TestSource-{uuid.uuid4().hex[:8]}", source_type="api", base_url="https://example.com")
    db_session.add(source)
    await db_session.flush()

    db_session.add(
        Vulnerability(
            cve_id="CVE-2021-44228",
            title="Log4Shell",
            description="Apache Log4j2 JNDI RCE",
            severity="CRITICAL",
            cvss_score=10.0,
            affected_vendor="Apache Software Foundation",
            affected_product="Apache Log4j2",
            is_known_exploited=True,
            source_id=source.id,
        )
    )
    db_session.add(
        Advisory(
            advisory_id="ICSA-24-123-01",
            title="Log4j exposure in Acme products",
            summary="Multiple Acme products bundle a vulnerable version of Log4j.",
            source_id=source.id,
        )
    )
    db_session.add(
        Asset(
            name="log4j-app-server",
            asset_type="application",
            vendor="Apache Software Foundation",
            product="Apache Log4j2",
            organization_id=organization_id,
        )
    )
    await db_session.flush()


async def test_search_returns_matches_across_all_types(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    await _seed_log4j_data(db_session, admin_user.organization_id)

    response = await client.get(
        "/api/v1/search", params={"q": "log4j"}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vulnerabilities"]["total"] == 1
    assert body["vulnerabilities"]["items"][0]["cve_id"] == "CVE-2021-44228"
    assert body["advisories"]["total"] == 1
    assert body["advisories"]["items"][0]["advisory_id"] == "ICSA-24-123-01"
    assert body["assets"]["total"] == 1
    assert body["assets"]["items"][0]["name"] == "log4j-app-server"


async def test_search_filters_by_types_param(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    await _seed_log4j_data(db_session, admin_user.organization_id)

    response = await client.get(
        "/api/v1/search",
        params={"q": "log4j", "types": "vulnerability"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vulnerabilities"]["total"] == 1
    assert body["advisories"]["total"] == 0
    assert body["assets"]["total"] == 0


async def test_search_assets_scoped_to_own_organization(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    other_org = Organization(name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}")
    db_session.add(other_org)
    await db_session.flush()
    db_session.add(
        Asset(name="uniquenamex-server", asset_type="server", organization_id=other_org.id)
    )
    db_session.add(
        Asset(
            name="uniquenamex-owned",
            asset_type="server",
            organization_id=admin_user.organization_id,
        )
    )
    await db_session.flush()

    response = await client.get(
        "/api/v1/search",
        params={"q": "uniquenamex", "types": "asset"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body["assets"]["items"]]
    assert names == ["uniquenamex-owned"]


async def test_search_no_matches_returns_empty_groups(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.get(
        "/api/v1/search", params={"q": "no-such-keyword-exists"}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["vulnerabilities"] == {"items": [], "total": 0}
    assert body["advisories"] == {"items": [], "total": 0}
    assert body["assets"] == {"items": [], "total": 0}


async def test_viewer_without_permission_cannot_search(client: AsyncClient, viewer_user: User, auth_headers):
    response = await client.get(
        "/api/v1/search", params={"q": "log4j"}, headers=auth_headers(viewer_user)
    )
    assert response.status_code == 403


async def test_search_requires_nonempty_query(client: AsyncClient, admin_user: User, auth_headers):
    response = await client.get("/api/v1/search", params={"q": ""}, headers=auth_headers(admin_user))
    assert response.status_code == 422
