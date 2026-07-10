import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.database import DBSession
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.source import SourceRead
from app.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(rate_limit)])


@router.get("", response_model=list[SourceRead])
async def list_sources(
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("sources:read"))],
) -> list[SourceRead]:
    sources = await SourceService(session).list_all()
    return [SourceRead.model_validate(source) for source in sources]


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(
    source_id: uuid.UUID,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("sources:read"))],
) -> SourceRead:
    source = await SourceService(session).get_by_id(source_id)
    return SourceRead.model_validate(source)
