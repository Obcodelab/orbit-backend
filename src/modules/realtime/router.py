from fastapi import APIRouter

from .apis.websocket import websocket_router

realtime_router = APIRouter()
realtime_router.include_router(websocket_router)
