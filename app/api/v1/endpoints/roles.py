import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies.database import DBSession
from app.api.dependencies.permissions import require_permission
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.role import RoleCreate, RoleRead
from app.services.role_service import RoleService

router = APIRouter(prefix="/roles", tags=["roles"], dependencies=[Depends(rate_limit)])


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("roles:manage"))],
) -> RoleRead:
    role = await RoleService(session).create_role(data)
    return RoleRead.model_validate(role)


@router.get("", response_model=list[RoleRead])
async def list_roles(
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("roles:read"))],
) -> list[RoleRead]:
    roles = await RoleService(session).list_all()
    return [RoleRead.model_validate(role) for role in roles]


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(
    role_id: uuid.UUID,
    session: DBSession,
    current_user: Annotated[User, Depends(require_permission("roles:read"))],
) -> RoleRead:
    role = await RoleService(session).get_by_id(role_id)
    return RoleRead.model_validate(role)
