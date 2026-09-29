from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from core.types import SortOrder
from core.websocket_manager import connection_manager
from modules.organizations.repositories import (
    OrganizationMemberRepository,
    organization_member_repository,
)
from modules.projects.exceptions import (
    AlreadyProjectMemberError,
    CannotChangeProjectOwnerRoleError,
    CannotRemoveProjectOwnerError,
    NotOrgMemberError,
    ProjectArchivedError,
    ProjectMembershipNotFoundError,
)
from modules.projects.models import Project
from modules.projects.repositories import (
    ActivityLogRepository,
    ProjectMemberRepository,
    activity_log_repository,
    project_member_repository,
)
from modules.projects.schemas import ProjectMemberResponse
from modules.projects.types import ActivityAction, ProjectRole, ProjectStatus
from modules.tasks.repositories import TaskAssigneeRepository, task_assignee_repository


class ProjectMemberService:
    def __init__(
        self,
        member_repo: ProjectMemberRepository,
        org_member_repo: OrganizationMemberRepository,
        task_assignee_repo: TaskAssigneeRepository,
        activity_repo: ActivityLogRepository,
    ) -> None:
        self.member_repo = member_repo
        self.org_member_repo = org_member_repo
        self.task_assignee_repo = task_assignee_repo
        self.activity_repo = activity_repo

    async def add_member(
        self,
        session: AsyncSession,
        *,
        project: Project,
        user_id: UUID,
        role: ProjectRole,
        actor_id: UUID,
    ) -> ProjectMemberResponse:
        if project.status == ProjectStatus.ARCHIVED:
            raise ProjectArchivedError

        if await self.member_repo.get_membership(
            session, project_id=project.id, user_id=user_id
        ):
            raise AlreadyProjectMemberError

        if not await self.org_member_repo.get_membership(
            session, org_id=project.org_id, user_id=user_id
        ):
            raise NotOrgMemberError

        member = await self.member_repo.add_member(
            session, project_id=project.id, user_id=user_id, role=role
        )
        connection_manager.add_user_to_project(project.id, user_id)
        await self.activity_repo.log(
            session,
            org_id=project.org_id,
            project_id=project.id,
            actor_id=actor_id,
            action=ActivityAction.MEMBER_JOINED,
            target=str(user_id),
        )
        member_with_user = await self.member_repo.get_membership_with_user(
            session, project_id=project.id, user_id=member.user_id
        )
        return ProjectMemberResponse.model_validate(member_with_user)

    async def list_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        q: str | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> Page[ProjectMemberResponse]:
        members, total = await self.member_repo.get_for_project(
            session, project_id=project_id, q=q, order=order, limit=limit, offset=offset
        )
        items = [ProjectMemberResponse.model_validate(m) for m in members]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get_member(
        self, session: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> ProjectMemberResponse:
        membership = await self.member_repo.get_membership_with_user(
            session, project_id=project_id, user_id=user_id
        )
        if not membership:
            raise ProjectMembershipNotFoundError
        return ProjectMemberResponse.model_validate(membership)

    async def remove_member(
        self, session: AsyncSession, *, project_id: UUID, user_id: UUID
    ) -> None:
        membership = await self.member_repo.get_membership(
            session, project_id=project_id, user_id=user_id
        )
        if not membership:
            raise ProjectMembershipNotFoundError
        if membership.role == ProjectRole.OWNER:
            raise CannotRemoveProjectOwnerError

        await self.member_repo.remove_member(
            session, project_id=project_id, user_id=user_id
        )
        await self.task_assignee_repo.remove_for_project(
            session, project_id=project_id, user_id=user_id
        )
        connection_manager.remove_user_from_project(project_id, user_id)

    async def update_role(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        user_id: UUID,
        role: ProjectRole,
    ) -> ProjectMemberResponse:
        membership = await self.member_repo.get_membership_with_user(
            session, project_id=project_id, user_id=user_id
        )
        if not membership:
            raise ProjectMembershipNotFoundError
        if membership.role == ProjectRole.OWNER:
            raise CannotChangeProjectOwnerRoleError

        user = membership.user  # keep a reference — avoids a lazy-load on response
        updated = await self.member_repo.update_role(
            session, member=membership, role=role
        )
        updated.user = user
        return ProjectMemberResponse.model_validate(updated)


project_member_service = ProjectMemberService(
    member_repo=project_member_repository,
    org_member_repo=organization_member_repository,
    task_assignee_repo=task_assignee_repository,
    activity_repo=activity_log_repository,
)
