from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.tasks.repositories import TaskRepository, task_repository
from modules.tasks.schemas import ProjectDashboardResponse
from modules.tasks.types import TaskStatus


class DashboardService:
    def __init__(self, task_repo: TaskRepository) -> None:
        self.task_repo = task_repo

    async def get_dashboard(
        self, session: AsyncSession, *, project_id: UUID
    ) -> ProjectDashboardResponse:
        counts = await self.task_repo.count_by_status(session, project_id=project_id)
        total = sum(counts.values())
        done = counts.get(TaskStatus.DONE, 0)
        completion_percent = round(done / total * 100, 2) if total else 0.0
        return ProjectDashboardResponse(
            tasks_by_status=counts,
            total_tasks=total,
            completion_percent=completion_percent,
        )


dashboard_service = DashboardService(task_repo=task_repository)
