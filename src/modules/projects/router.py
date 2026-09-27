from fastapi import APIRouter

from .apis.activity import activity_router
from .apis.project import project_router

projects_router = APIRouter()
projects_router.include_router(project_router)
projects_router.include_router(activity_router)
