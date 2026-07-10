from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.database import DBSession
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.advisory import AdvisoryRead
from app.schemas.asset import AssetRead
from app.schemas.search import SearchResponse, SearchResultGroup
from app.schemas.vulnerability import VulnerabilityRead
from app.services.search_service import SEARCHABLE_TYPES, SearchService

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=SearchResponse)
async def search(
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("search:read"))],
    q: Annotated[str, Query(min_length=1, description="Keyword to search for")],
    types: Annotated[
        str | None,
        Query(description="Comma-separated subset of: vulnerability,advisory,asset (default: all)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="Max results per entity type")] = 10,
) -> SearchResponse:
    requested_types = None
    if types is not None:
        requested_types = {t.strip() for t in types.split(",") if t.strip()} & SEARCHABLE_TYPES

    results = await SearchService(session).search(
        current_user, query=q, types=requested_types, limit=limit
    )

    vulnerabilities, vulnerabilities_total = results["vulnerabilities"]
    advisories, advisories_total = results["advisories"]
    assets, assets_total = results["assets"]

    return SearchResponse(
        query=q,
        vulnerabilities=SearchResultGroup(
            items=[VulnerabilityRead.model_validate(item) for item in vulnerabilities],
            total=vulnerabilities_total,
        ),
        advisories=SearchResultGroup(
            items=[AdvisoryRead.model_validate(item) for item in advisories], total=advisories_total
        ),
        assets=SearchResultGroup(
            items=[AssetRead.model_validate(item) for item in assets], total=assets_total
        ),
    )
