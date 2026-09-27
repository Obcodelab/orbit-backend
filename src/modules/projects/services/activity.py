from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from core.types import SortOrder
from modules.projects.repositories import ActivityLogRepository, activity_log_repository
from modules.projects.schemas import ActivityLogEntryResponse


class ActivityService:
    def __init__(self, activity_repo: ActivityLogRepository) -> None:
        self.activity_repo = activity_repo

    async def list_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> Page[ActivityLogEntryResponse]:
        entries, total = await self.activity_repo.get_for_project(
            session, project_id=project_id, order=order, limit=limit, offset=offset
        )
        items = [ActivityLogEntryResponse.model_validate(e) for e in entries]
        return Page(items=items, total=total, limit=limit, offset=offset)


activity_service = ActivityService(activity_repo=activity_log_repository)
