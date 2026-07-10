import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies.database import DBSession
from app.api.dependencies.pagination import PaginationDep
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetRead
from app.schemas.vulnerability import VulnerabilityRead
from app.services.asset_service import AssetService
from app.utils.pagination import Page

router = APIRouter(prefix="/assets", tags=["assets"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    data: AssetCreate,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("assets:manage"))],
) -> AssetRead:
    asset = await AssetService(session).create_asset(current_user, data)
    return AssetRead.model_validate(asset)


@router.get("", response_model=Page[AssetRead])
async def list_assets(
    session: DBSession,
    pagination: PaginationDep,
    current_user: Annotated[User, Depends(require_permission("assets:read"))],
) -> Page[AssetRead]:
    items, total = await AssetService(session).list_for_organization(
        current_user, limit=pagination.page_size, offset=pagination.offset
    )
    return Page.create(
        items=[AssetRead.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: uuid.UUID,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("assets:read"))],
) -> AssetRead:
    asset = await AssetService(session).get_by_id(current_user, asset_id)
    return AssetRead.model_validate(asset)


@router.get("/{asset_id}/vulnerabilities", response_model=Page[VulnerabilityRead])
async def list_asset_vulnerabilities(
    asset_id: uuid.UUID,
    session: DBSession,
    pagination: PaginationDep,
    current_user: Annotated[User, Depends(require_permission("vulnerabilities:read"))],
) -> Page[VulnerabilityRead]:
    items, total = await AssetService(session).list_matching_vulnerabilities(
        current_user, asset_id, limit=pagination.page_size, offset=pagination.offset
    )
    return Page.create(
        items=[VulnerabilityRead.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
