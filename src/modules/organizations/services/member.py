from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.pagination import Page
from core.types import SortOrder
from modules.organizations.exceptions import (
    CannotChangeOwnerRoleError,
    CannotRemoveOwnerError,
    MemberOwnsProjectsError,
    MembershipNotFoundError,
)
from modules.organizations.repositories import (
    OrganizationMemberRepository,
    organization_member_repository,
)
from modules.organizations.schemas import OrganizationMemberResponse
from modules.organizations.types import OrganizationRole
from modules.projects.repositories import (
    ProjectMemberRepository,
    ProjectRepository,
    project_member_repository,
    project_repository,
)
from modules.tasks.repositories import TaskAssigneeRepository, task_assignee_repository


class OrganizationMemberService:
    def __init__(
        self,
        member_repo: OrganizationMemberRepository,
        project_repo: ProjectRepository,
        project_member_repo: ProjectMemberRepository,
        task_assignee_repo: TaskAssigneeRepository,
    ) -> None:
        self.member_repo = member_repo
        self.project_repo = project_repo
        self.project_member_repo = project_member_repo
        self.task_assignee_repo = task_assignee_repo

    async def list_for_org(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        q: str | None,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> Page[OrganizationMemberResponse]:
        members, total = await self.member_repo.get_for_org(
            session, org_id=org_id, q=q, order=order, limit=limit, offset=offset
        )
        return Page(
            items=[OrganizationMemberResponse.model_validate(m) for m in members],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_member(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> OrganizationMemberResponse:
        membership = await self.member_repo.get_membership_with_user(
            session, org_id=org_id, user_id=user_id
        )
        if not membership:
            raise MembershipNotFoundError
        return OrganizationMemberResponse.model_validate(membership)

    async def remove_member(
        self, session: AsyncSession, *, org_id: UUID, user_id: UUID
    ) -> None:
        membership = await self.member_repo.get_membership(
            session, org_id=org_id, user_id=user_id
        )
        if not membership:
            raise MembershipNotFoundError
        if membership.role == OrganizationRole.OWNER:
            raise CannotRemoveOwnerError

        owned_projects = await self.project_repo.get_all_by(
            session, org_id=org_id, owner_id=user_id
        )
        if owned_projects:
            raise MemberOwnsProjectsError

        await self.member_repo.remove_member(session, org_id=org_id, user_id=user_id)
        await self.project_member_repo.remove_for_org(
            session, org_id=org_id, user_id=user_id
        )
        await self.task_assignee_repo.remove_for_org(
            session, org_id=org_id, user_id=user_id
        )

    async def update_role(
        self,
        session: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID,
        role: OrganizationRole,
    ) -> OrganizationMemberResponse:
        membership = await self.member_repo.get_membership_with_user(
            session, org_id=org_id, user_id=user_id
        )
        if not membership:
            raise MembershipNotFoundError
        if membership.role == OrganizationRole.OWNER:
            raise CannotChangeOwnerRoleError

        user = membership.user  # keep a reference — avoids a lazy-load on response
        updated = await self.member_repo.update_role(
            session, member=membership, role=role
        )
        updated.user = user
        return OrganizationMemberResponse.model_validate(updated)


organization_member_service = OrganizationMemberService(
    member_repo=organization_member_repository,
    project_repo=project_repository,
    project_member_repo=project_member_repository,
    task_assignee_repo=task_assignee_repository,
)
