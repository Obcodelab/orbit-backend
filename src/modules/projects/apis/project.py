from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from core.dependencies import AuthenticatedUser, DBSession, PaginationParams
from core.pagination import Page
from modules.organizations.dependencies import AdminOrOwner as OrgAdminOrOwner
from modules.projects.dependencies import (
    AnyProjectMember,
    ProjectAdminOrOwner,
    ProjectOwnerOnly,
)
from modules.projects.exceptions import (
    AlreadyProjectMemberError,
    CannotChangeProjectOwnerRoleError,
    CannotRemoveProjectOwnerError,
    DuplicateProjectKeyError,
    NotOrgMemberError,
    ProjectArchivedError,
    ProjectMembershipNotFoundError,
)
from modules.projects.repositories import project_repository
from modules.projects.schemas import (
    AddProjectMemberRequest,
    MyProjectResponse,
    ProjectCreateRequest,
    ProjectMemberResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    UpdateProjectMemberRoleRequest,
)
from modules.projects.services import project_member_service, project_service
from modules.projects.types import ProjectStatus

project_router = APIRouter(tags=["Projects"])


@project_router.post(
    "/organizations/{org_id}/projects", status_code=status.HTTP_201_CREATED
)
async def create_project(
    org_id: UUID,
    body: ProjectCreateRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: OrgAdminOrOwner,
) -> ProjectResponse:
    try:
        project = await project_service.create_project(
            session,
            org_id=org_id,
            key=body.key,
            name=body.name,
            description=body.description,
            owner=user,
        )
    except DuplicateProjectKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A project with key '{body.key}' already exists in this organization",
        )
    return project_service.build_response(project)


@project_router.get("/projects")
async def list_my_projects(
    user: AuthenticatedUser,
    session: DBSession,
    pagination: PaginationParams,
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
) -> Page[MyProjectResponse]:
    return await project_service.list_for_user(
        session,
        user_id=user.id,
        status_filter=status_filter,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@project_router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID, session: DBSession, membership: AnyProjectMember
) -> ProjectResponse:
    project = await project_repository.get_by_id(session, project_id)
    return project_service.build_response(project)


@project_router.patch("/projects/{project_id}")
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    session: DBSession,
    membership: ProjectOwnerOnly,
) -> ProjectResponse:
    project = await project_repository.get_by_id(session, project_id)
    updates = body.model_dump(exclude_unset=True)

    still_archived = project.status == ProjectStatus.ARCHIVED and (
        "status" not in updates or updates["status"] == ProjectStatus.ARCHIVED
    )
    if still_archived:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This project is archived — only un-archiving it is allowed",
        )

    updated = await project_service.update_project(
        session, project=project, updates=updates
    )
    return project_service.build_response(updated)


@project_router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, session: DBSession, membership: ProjectOwnerOnly
) -> None:
    await project_service.delete_project(session, project_id=project_id)


@project_router.post(
    "/projects/{project_id}/members", status_code=status.HTTP_201_CREATED
)
async def add_project_member(
    project_id: UUID,
    body: AddProjectMemberRequest,
    session: DBSession,
    membership: ProjectAdminOrOwner,
) -> ProjectMemberResponse:
    project = await project_repository.get_by_id(session, project_id)
    try:
        return await project_member_service.add_member(
            session, project=project, user_id=body.user_id, role=body.role
        )
    except NotOrgMemberError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "User must be a member of this project's organization first",
        )
    except AlreadyProjectMemberError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "User is already a member of this project"
        )
    except ProjectArchivedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This project is archived and is read-only"
        )


@project_router.get("/projects/{project_id}/members")
async def list_project_members(
    project_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
) -> Page[ProjectMemberResponse]:
    return await project_member_service.list_for_project(
        session, project_id=project_id, limit=pagination.limit, offset=pagination.offset
    )


@project_router.get("/projects/{project_id}/members/{user_id}")
async def get_project_member(
    project_id: UUID, user_id: UUID, session: DBSession, membership: AnyProjectMember
) -> ProjectMemberResponse:
    try:
        return await project_member_service.get_member(
            session, project_id=project_id, user_id=user_id
        )
    except ProjectMembershipNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "User is not a member of this project"
        )


@project_router.patch("/projects/{project_id}/members/{user_id}")
async def update_project_member_role(
    project_id: UUID,
    user_id: UUID,
    body: UpdateProjectMemberRoleRequest,
    session: DBSession,
    membership: ProjectAdminOrOwner,
) -> ProjectMemberResponse:
    try:
        return await project_member_service.update_role(
            session, project_id=project_id, user_id=user_id, role=body.role
        )
    except ProjectMembershipNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "User is not a member of this project"
        )
    except CannotChangeProjectOwnerRoleError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The project's owner's role cannot be changed"
        )


@project_router.delete(
    "/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    session: DBSession,
    membership: ProjectAdminOrOwner,
) -> None:
    try:
        await project_member_service.remove_member(
            session, project_id=project_id, user_id=user_id
        )
    except ProjectMembershipNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "User is not a member of this project"
        )
    except CannotRemoveProjectOwnerError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The project's owner cannot be removed"
        )
