from fastapi import APIRouter

from .apis.google_oauth import google_oauth_router
from .apis.user import profile_router, user_router

auth_router = APIRouter(prefix="/auth", tags=["Auth"])
auth_router.include_router(user_router)
auth_router.include_router(google_oauth_router, prefix="/google")

account_router = APIRouter(prefix="/account", tags=["Account"])
account_router.include_router(profile_router)
