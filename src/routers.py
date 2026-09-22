from fastapi import APIRouter

from modules.auth.router import account_router, auth_router
from modules.organizations.router import organizations_router
from modules.projects.router import projects_router

# Module routers are included here as each module is built.
api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(organizations_router)
api_router.include_router(projects_router)
