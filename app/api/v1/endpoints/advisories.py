import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.database import DBSession
from app.api.dependencies.pagination import PaginationDep
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.advisory import AdvisoryCreate, AdvisoryRead
from app.services.advisory_service import AdvisoryService
from app.utils.pagination import Page

router = APIRouter(prefix="/advisories", tags=["advisories"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=AdvisoryRead, status_code=status.HTTP_201_CREATED)
async def create_advisory(
    data: AdvisoryCreate,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("advisories:manage"))],
) -> AdvisoryRead:
    advisory = await AdvisoryService(session).create_advisory(data)
    return AdvisoryRead.model_validate(advisory)


@router.get("", response_model=Page[AdvisoryRead])
async def list_advisories(
    session: DBSession,
    pagination: PaginationDep,
    current_user: Annotated[User, Depends(require_permission("advisories:read"))],
    source_id: Annotated[uuid.UUID | None, Query(description="Filter to advisories from one source")] = None,
) -> Page[AdvisoryRead]:
    items, total = await AdvisoryService(session).list_recent(
        source_id=source_id, limit=pagination.page_size, offset=pagination.offset
    )
    return Page.create(
        items=[AdvisoryRead.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{advisory_id}", response_model=AdvisoryRead)
async def get_advisory(
    advisory_id: str,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("advisories:read"))],
) -> AdvisoryRead:
    advisory = await AdvisoryService(session).get_by_advisory_id(advisory_id)
    return AdvisoryRead.model_validate(advisory)
