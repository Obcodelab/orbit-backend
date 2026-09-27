from fastapi import APIRouter

from .apis.comment import comment_router
from .apis.dashboard import dashboard_router
from .apis.task import task_router

tasks_router = APIRouter()
tasks_router.include_router(task_router)
tasks_router.include_router(comment_router)
tasks_router.include_router(dashboard_router)
