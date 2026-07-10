from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.organizations import router as organizations_router
from app.api.v1.endpoints.roles import router as roles_router
from app.api.v1.endpoints.sources import router as sources_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.vulnerabilities import router as vulnerabilities_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(organizations_router)
api_router.include_router(roles_router)
api_router.include_router(sources_router)
api_router.include_router(vulnerabilities_router)
