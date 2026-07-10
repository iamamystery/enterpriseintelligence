import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.database import DBSession
from app.api.dependencies.pagination import PaginationDep
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.scrape_job import ScrapeJobRead
from app.services.scrape_job_service import ScrapeJobService
from app.utils.pagination import Page

router = APIRouter(prefix="/scrape-jobs", tags=["scrape-jobs"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=Page[ScrapeJobRead])
async def list_scrape_jobs(
    session: DBSession,
    pagination: PaginationDep,
    current_user: Annotated[User, Depends(require_permission("scrape_jobs:read"))],
    job_name: Annotated[
        str | None,
        Query(description="Filter to one job, e.g. nvd_ingestion, cisa_kev_ingestion, redhat_ingestion, mitre_backfill"),
    ] = None,
) -> Page[ScrapeJobRead]:
    items, total = await ScrapeJobService(session).list_recent(
        job_name=job_name, limit=pagination.page_size, offset=pagination.offset
    )
    return Page.create(
        items=[ScrapeJobRead.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{scrape_job_id}", response_model=ScrapeJobRead)
async def get_scrape_job(
    scrape_job_id: uuid.UUID,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("scrape_jobs:read"))],
) -> ScrapeJobRead:
    job = await ScrapeJobService(session).get_by_id(scrape_job_id)
    return ScrapeJobRead.model_validate(job)
