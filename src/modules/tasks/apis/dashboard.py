from uuid import UUID

from fastapi import APIRouter

from core.dependencies import DBSession
from modules.projects.dependencies import AnyProjectMember
from modules.tasks.schemas import ProjectDashboardResponse
from modules.tasks.services import dashboard_service

dashboard_router = APIRouter(tags=["Dashboard"])


@dashboard_router.get("/projects/{project_id}/dashboard")
async def get_dashboard(
    project_id: UUID, session: DBSession, membership: AnyProjectMember
) -> ProjectDashboardResponse:
    return await dashboard_service.get_dashboard(session, project_id=project_id)
