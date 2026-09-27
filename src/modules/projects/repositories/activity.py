from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repository import BaseRepository
from core.types import SortOrder
from modules.projects.models import ActivityLogEntry
from modules.projects.types import ActivityAction


class ActivityLogRepository(BaseRepository[ActivityLogEntry]):
    model = ActivityLogEntry

    async def log(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        project_id: UUID,
        actor_id: UUID,
        action: ActivityAction,
        target: str,
    ) -> ActivityLogEntry:
        return await self.create(
            session,
            org_id=org_id,
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            target=target,
        )

    async def get_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ActivityLogEntry], int]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        total = await self._count(session, stmt)
        stmt = self._apply_order(
            stmt,
            order=order,
            column=self.model.created_at,
            default_order=SortOrder.DESC,
        )
        stmt = stmt.options(selectinload(self.model.actor)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


activity_log_repository = ActivityLogRepository()
