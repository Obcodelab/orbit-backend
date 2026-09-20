from fastapi import APIRouter

from modules.auth.router import account_router, auth_router

# Module routers are included here as each module is built.
api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(account_router)
