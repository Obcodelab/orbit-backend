from fastapi import APIRouter

from .apis.conversation import conversation_router

ai_router = APIRouter()
ai_router.include_router(conversation_router)
