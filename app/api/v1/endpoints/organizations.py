from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.database import DBSession
from app.api.dependencies.rate_limit import rate_limit
from app.models.user import User
from app.schemas.organization import OrganizationRead
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"], dependencies=[Depends(rate_limit)])


@router.get("/me", response_model=OrganizationRead)
async def get_my_organization(
    session: DBSession,
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrganizationRead:
    organization = await OrganizationService(session).get_current(current_user)
    return OrganizationRead.model_validate(organization)
