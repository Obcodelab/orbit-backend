from pydantic import BaseModel

from modules.tasks.types import TaskStatus


class ProjectDashboardResponse(BaseModel):
    tasks_by_status: dict[TaskStatus, int]
    total_tasks: int
    completion_percent: float
