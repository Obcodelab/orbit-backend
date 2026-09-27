from uuid import UUID

from fastapi import APIRouter, Query

from core.dependencies import DBSession, PaginationParams
from core.pagination import Page
from core.types import SortOrder
from modules.projects.dependencies import AnyProjectMember
from modules.projects.schemas import ActivityLogEntryResponse
from modules.projects.services import activity_service

activity_router = APIRouter(tags=["Activity"])


@activity_router.get("/projects/{project_id}/activity")
async def list_activity(
    project_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
    order: SortOrder | None = Query(default=None),
) -> Page[ActivityLogEntryResponse]:
    return await activity_service.list_for_project(
        session,
        project_id=project_id,
        order=order,
        limit=pagination.limit,
        offset=pagination.offset,
    )
