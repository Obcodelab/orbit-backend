from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from modules.auth.models import User
from modules.projects.exceptions import DuplicateProjectKeyError
from modules.projects.models import Project
from modules.projects.repositories import (
    ProjectMemberRepository,
    ProjectRepository,
    project_member_repository,
    project_repository,
)
from modules.projects.schemas import MyProjectResponse, ProjectResponse
from modules.projects.types import ProjectRole, ProjectStatus


class ProjectService:
    def __init__(
        self, project_repo: ProjectRepository, member_repo: ProjectMemberRepository
    ) -> None:
        self.project_repo = project_repo
        self.member_repo = member_repo

    async def create_project(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        key: str,
        name: str,
        description: str | None,
        owner: User,
    ) -> Project:
        if await self.project_repo.key_taken(session, org_id=org_id, key=key):
            raise DuplicateProjectKeyError

        project = await self.project_repo.create_project(
            session,
            org_id=org_id,
            key=key,
            name=name,
            description=description,
            owner_id=owner.id,
        )
        await self.member_repo.add_member(
            session, project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER
        )
        return project

    async def list_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        status_filter: ProjectStatus | None,
        limit: int,
        offset: int,
    ) -> Page[MyProjectResponse]:
        memberships, total = await self.member_repo.get_for_user(
            session,
            user_id=user_id,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        items = [
            MyProjectResponse(
                project_id=m.project.id,
                org_id=m.project.org_id,
                key=m.project.key,
                name=m.project.name,
                description=m.project.description,
                status=m.project.status,
                owner_id=m.project.owner_id,
                role=m.role,
            )
            for m in memberships
        ]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def update_project(
        self, session: AsyncSession, *, project: Project, updates: dict
    ) -> Project:
        return await self.project_repo.update_fields(
            session, project=project, updates=updates
        )

    async def delete_project(self, session: AsyncSession, *, project_id: UUID) -> None:
        await self.project_repo.delete_by_id(session, project_id)

    def build_response(self, project: Project) -> ProjectResponse:
        return ProjectResponse.model_validate(project)


project_service = ProjectService(
    project_repo=project_repository, member_repo=project_member_repository
)
