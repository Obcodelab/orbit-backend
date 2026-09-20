from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from core.dependencies import AuthenticatedUser, DBSession
from modules.organizations.dependencies import AdminOrOwner, AnyMember, OwnerOnly
from modules.organizations.exceptions import (
    AlreadyInvitedError,
    AlreadyMemberError,
    CannotChangeOwnerRoleError,
    CannotRemoveOwnerError,
    MembershipNotFoundError,
)
from modules.organizations.repositories import organization_repository
from modules.organizations.schemas import (
    AddOrganizationMemberRequest,
    MyOrganizationResponse,
    OrganizationCreateRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
    OrgInviteResponse,
    UpdateMemberRoleRequest,
)
from modules.organizations.services import (
    organization_invite_service,
    organization_member_service,
    organization_service,
)

organization_router = APIRouter(prefix="/organizations", tags=["Organizations"])


@organization_router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreateRequest, user: AuthenticatedUser, session: DBSession
) -> OrganizationResponse:
    org = await organization_service.create_organization(
        session, name=body.name, owner=user
    )
    return organization_service.build_response(org)


@organization_router.get("")
async def list_my_organizations(
    user: AuthenticatedUser, session: DBSession
) -> list[MyOrganizationResponse]:
    return await organization_service.list_for_user(session, user_id=user.id)


@organization_router.get("/{org_id}")
async def get_organization(
    org_id: UUID, session: DBSession, membership: AnyMember
) -> OrganizationResponse:
    org = await organization_repository.get_by_id(session, org_id)
    return organization_service.build_response(org)


@organization_router.patch("/{org_id}")
async def update_organization(
    org_id: UUID,
    body: OrganizationUpdateRequest,
    session: DBSession,
    membership: OwnerOnly,
) -> OrganizationResponse:
    org = await organization_repository.get_by_id(session, org_id)
    updated = await organization_service.update_name(session, org=org, name=body.name)
    return organization_service.build_response(updated)


@organization_router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID, session: DBSession, membership: OwnerOnly
) -> None:
    await organization_service.delete_organization(session, org_id=org_id)


@organization_router.post("/{org_id}/members", status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: UUID,
    body: AddOrganizationMemberRequest,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AdminOrOwner,
) -> OrgInviteResponse:
    org = await organization_repository.get_by_id(session, org_id)
    try:
        return await organization_invite_service.create_invite(
            session,
            org_id=org_id,
            org_name=org.name,
            email=body.email,
            role=body.role,
            inviter=user,
        )
    except AlreadyMemberError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "User is already a member of this organization"
        )
    except AlreadyInvitedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "User already has a pending invite to this organization",
        )


@organization_router.get("/{org_id}/members")
async def list_members(
    org_id: UUID, session: DBSession, membership: AnyMember
) -> list[OrganizationMemberResponse]:
    return await organization_member_service.list_for_org(session, org_id=org_id)


@organization_router.get("/{org_id}/members/{user_id}")
async def get_member(
    org_id: UUID, user_id: UUID, session: DBSession, membership: AnyMember
) -> OrganizationMemberResponse:
    try:
        return await organization_member_service.get_member(
            session, org_id=org_id, user_id=user_id
        )
    except MembershipNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "User is not a member of this organization"
        )


@organization_router.patch("/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    session: DBSession,
    membership: AdminOrOwner,
) -> OrganizationMemberResponse:
    try:
        return await organization_member_service.update_role(
            session, org_id=org_id, user_id=user_id, role=body.role
        )
    except MembershipNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "User is not a member of this organization"
        )
    except CannotChangeOwnerRoleError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "The organization's owner's role cannot be changed",
        )


@organization_router.delete(
    "/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    session: DBSession,
    membership: AdminOrOwner,
) -> None:
    try:
        await organization_member_service.remove_member(
            session, org_id=org_id, user_id=user_id
        )
    except MembershipNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "User is not a member of this organization"
        )
    except CannotRemoveOwnerError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "The organization's owner cannot be removed"
        )
