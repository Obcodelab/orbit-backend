from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from starlette import status

from core.database import async_session_factory
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.security import decode_token
from core.types import TokenType
from core.websocket_manager import connection_manager
from modules.auth.repositories import user_repository
from modules.projects.repositories import project_member_repository

websocket_router = APIRouter(tags=["Realtime"])


async def _authenticate(websocket: WebSocket) -> tuple[UUID, list[UUID]] | None:
    """Returns (user_id, project_ids) if authenticated, else None —
    project_ids is every project this user currently belongs to. Token
    comes via query param since browser WebSocket clients can't set an
    Authorization header on connect."""
    token = websocket.query_params.get("token")
    if not token:
        return None

    try:
        claims = decode_token(token)
    except (TokenExpiredError, TokenInvalidError):
        return None
    if claims.get("type") != TokenType.ACCESS:
        return None

    raw_user_id = claims.get("sub")
    if not raw_user_id:
        return None

    async with async_session_factory() as session:
        user = await user_repository.get_by_id(session, UUID(raw_user_id))
        if not user or not user.is_active:
            return None
        project_ids = await project_member_repository.get_project_ids_for_user(
            session, user_id=user.id
        )
    return user.id, project_ids


@websocket_router.websocket("/ws")
async def user_websocket(websocket: WebSocket) -> None:
    auth = await _authenticate(websocket)
    if auth is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user_id, project_ids = auth

    await websocket.accept()
    await connection_manager.connect(user_id, project_ids, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("user_websocket: unexpected exception in receive loop")
    finally:
        await connection_manager.disconnect(websocket)
