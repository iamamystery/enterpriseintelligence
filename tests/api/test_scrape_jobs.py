import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.scrape_job_service import ScrapeJobService


async def test_admin_lists_scrape_jobs(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    job = await ScrapeJobService(db_session).start("nvd_ingestion")
    await ScrapeJobService(db_session).mark_success(job.id, items_processed=10)

    response = await client.get("/api/v1/scrape-jobs", headers=auth_headers(admin_user))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["job_name"] == "nvd_ingestion" for item in body["items"])


async def test_list_scrape_jobs_filters_by_job_name(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    await ScrapeJobService(db_session).start("nvd_ingestion")
    await ScrapeJobService(db_session).start("mitre_backfill")

    response = await client.get(
        "/api/v1/scrape-jobs", params={"job_name": "mitre_backfill"}, headers=auth_headers(admin_user)
    )
    assert response.status_code == 200
    body = response.json()
    assert all(item["job_name"] == "mitre_backfill" for item in body["items"])


async def test_viewer_without_permission_cannot_list_scrape_jobs(
    client: AsyncClient, viewer_user: User, auth_headers
):
    response = await client.get("/api/v1/scrape-jobs", headers=auth_headers(viewer_user))
    assert response.status_code == 403


async def test_get_scrape_job_by_id(
    client: AsyncClient, admin_user: User, db_session: AsyncSession, auth_headers
):
    job = await ScrapeJobService(db_session).start("redhat_ingestion")
    await ScrapeJobService(db_session).mark_failed(job.id, "boom")

    response = await client.get(f"/api/v1/scrape-jobs/{job.id}", headers=auth_headers(admin_user))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "boom"


async def test_get_nonexistent_scrape_job_returns_404(
    client: AsyncClient, admin_user: User, auth_headers
):
    response = await client.get(f"/api/v1/scrape-jobs/{uuid.uuid4()}", headers=auth_headers(admin_user))
    assert response.status_code == 404
