from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.database import DBSession
from app.api.dependencies.pagination import PaginationDep
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.vulnerability import VulnerabilityRead
from app.services.vulnerability_service import VulnerabilityService
from app.utils.pagination import Page

router = APIRouter(prefix="/vulnerabilities", tags=["vulnerabilities"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=Page[VulnerabilityRead])
async def list_vulnerabilities(
    session: DBSession,
    pagination: PaginationDep,
    current_user: Annotated[User, Depends(require_permission("vulnerabilities:read"))],
    q: Annotated[
        str | None, Query(description="Keyword search across CVE ID, title, and description")
    ] = None,
    severity: Annotated[str | None, Query(description="LOW, MEDIUM, HIGH, or CRITICAL")] = None,
    is_known_exploited: Annotated[
        bool | None, Query(description="Filter to CISA KEV-flagged vulnerabilities")
    ] = None,
    affected_vendor: Annotated[str | None, Query()] = None,
    affected_product: Annotated[str | None, Query()] = None,
    min_cvss: Annotated[float | None, Query(ge=0, le=10)] = None,
    max_cvss: Annotated[float | None, Query(ge=0, le=10)] = None,
    sort_by: Annotated[
        str, Query(description="cve_id, published_date, updated_date, or cvss_score")
    ] = "published_date",
    sort_order: Annotated[str, Query(description="asc or desc")] = "desc",
) -> Page[VulnerabilityRead]:
    items, total = await VulnerabilityService(session).search(
        keyword=q,
        severity=severity,
        is_known_exploited=is_known_exploited,
        affected_vendor=affected_vendor,
        affected_product=affected_product,
        min_cvss=min_cvss,
        max_cvss=max_cvss,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return Page.create(
        items=[VulnerabilityRead.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{cve_id}", response_model=VulnerabilityRead)
async def get_vulnerability(
    cve_id: str,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("vulnerabilities:read"))],
) -> VulnerabilityRead:
    vulnerability = await VulnerabilityService(session).get_by_cve_id(cve_id)
    return VulnerabilityRead.model_validate(vulnerability)
