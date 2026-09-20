from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from core.dependencies import AuthenticatedUser, DBSession
from modules.organizations.dependencies import AdminOrOwner
from modules.organizations.exceptions import InviteNotFoundError
from modules.organizations.schemas import (
    MyInviteResponse,
    MyOrganizationResponse,
    OrgInviteResponse,
)
from modules.organizations.services import organization_invite_service

# Mounted before organization_router in router.py — "/invites" is a literal
# segment that must be matched before "/{org_id}" gets a chance to swallow it.
invite_router = APIRouter(prefix="/organizations", tags=["Organizations"])


@invite_router.get("/invites")
async def list_my_invites(
    user: AuthenticatedUser, session: DBSession
) -> list[MyInviteResponse]:
    return await organization_invite_service.list_for_user(session, email=user.email)


@invite_router.post("/invites/{invite_id}/accept")
async def accept_invite(
    invite_id: UUID, user: AuthenticatedUser, session: DBSession
) -> MyOrganizationResponse:
    try:
        return await organization_invite_service.accept(
            session, invite_id=invite_id, user=user
        )
    except InviteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending invite found")


@invite_router.post(
    "/invites/{invite_id}/decline", status_code=status.HTTP_204_NO_CONTENT
)
async def decline_invite(
    invite_id: UUID, user: AuthenticatedUser, session: DBSession
) -> None:
    try:
        await organization_invite_service.decline(
            session, invite_id=invite_id, user=user
        )
    except InviteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending invite found")


@invite_router.get("/{org_id}/invites")
async def list_org_invites(
    org_id: UUID, session: DBSession, membership: AdminOrOwner
) -> list[OrgInviteResponse]:
    return await organization_invite_service.list_for_org(session, org_id=org_id)


@invite_router.delete(
    "/{org_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_invite(
    org_id: UUID, invite_id: UUID, session: DBSession, membership: AdminOrOwner
) -> None:
    try:
        await organization_invite_service.revoke(
            session, org_id=org_id, invite_id=invite_id
        )
    except InviteNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending invite found")
