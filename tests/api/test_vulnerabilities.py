import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source
from app.models.user import User
from app.models.vulnerability import Vulnerability


async def _seed_vulnerabilities(db_session: AsyncSession) -> None:
    source = Source(name=f"TestSource-{uuid.uuid4().hex[:8]}", source_type="api", base_url="https://example.com")
    db_session.add(source)
    await db_session.flush()

    db_session.add_all(
        [
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
            ),
            Vulnerability(
                cve_id="CVE-1999-0095",
                title="Sendmail debug",
                description="The debug command in Sendmail is enabled",
                severity="HIGH",
                cvss_score=7.5,
                affected_vendor="eric_allman",
                affected_product="sendmail",
                is_known_exploited=False,
                source_id=source.id,
            ),
            Vulnerability(
                cve_id="CVE-2026-00001",
                title="Unscored issue",
                description="A vulnerability with no CVSS score yet",
                severity=None,
                cvss_score=None,
                affected_vendor="SomeVendor",
                is_known_exploited=False,
                source_id=source.id,
            ),
        ]
    )
    await db_session.flush()


async def test_list_returns_all_seeded_vulnerabilities(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get("/api/v1/vulnerabilities", headers=auth_headers(admin_user))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3


async def test_keyword_search_matches_description(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get(
        "/api/v1/vulnerabilities", params={"q": "sendmail"}, headers=auth_headers(admin_user)
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cve_id"] == "CVE-1999-0095"


async def test_filter_by_known_exploited(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get(
        "/api/v1/vulnerabilities",
        params={"is_known_exploited": "true"},
        headers=auth_headers(admin_user),
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cve_id"] == "CVE-2021-44228"


async def test_sort_by_cvss_score_desc_puts_unscored_last(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get(
        "/api/v1/vulnerabilities",
        params={"sort_by": "cvss_score", "sort_order": "desc"},
        headers=auth_headers(admin_user),
    )
    cve_ids = [item["cve_id"] for item in response.json()["items"]]
    assert cve_ids == ["CVE-2021-44228", "CVE-1999-0095", "CVE-2026-00001"]


async def test_sort_by_cvss_score_asc_still_puts_unscored_last(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get(
        "/api/v1/vulnerabilities",
        params={"sort_by": "cvss_score", "sort_order": "asc"},
        headers=auth_headers(admin_user),
    )
    cve_ids = [item["cve_id"] for item in response.json()["items"]]
    assert cve_ids == ["CVE-1999-0095", "CVE-2021-44228", "CVE-2026-00001"]


async def test_pagination_page_size(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get(
        "/api/v1/vulnerabilities", params={"page_size": 2}, headers=auth_headers(admin_user)
    )
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["total_pages"] == 2


async def test_detail_endpoint_returns_full_record(
    client: AsyncClient, db_session: AsyncSession, admin_user: User, auth_headers
):
    await _seed_vulnerabilities(db_session)
    response = await client.get(
        "/api/v1/vulnerabilities/CVE-2021-44228", headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    assert response.json()["affected_vendor"] == "Apache Software Foundation"


async def test_detail_endpoint_404_for_unknown_cve(
    client: AsyncClient, admin_user: User, auth_headers
):
    response = await client.get(
        "/api/v1/vulnerabilities/CVE-0000-0000", headers=auth_headers(admin_user)
    )
    assert response.status_code == 404
