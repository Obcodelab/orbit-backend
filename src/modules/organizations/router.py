from fastapi import APIRouter

from .apis.invite import invite_router
from .apis.organization import organization_router

organizations_router = APIRouter()
# invite_router first: its literal "/invites" path must be tried before
# organization_router's "/{org_id}" pattern, or "/invites" would get
# swallowed as an org_id and fail UUID validation instead of matching.
organizations_router.include_router(invite_router)
organizations_router.include_router(organization_router)
