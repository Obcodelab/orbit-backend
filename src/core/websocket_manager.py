from collections import defaultdict
from collections.abc import Iterable
from typing import Any
from uuid import UUID

from fastapi import WebSocket
from loguru import logger

from core.types import RealtimeEventType


class ConnectionManager:
    """One WebSocket per user session, registered under every project
    that user belongs to — so activity across all their projects reaches
    them at once, not just whichever board is on screen. Lives in core so
    every module's route layer can call it without an upward dependency."""

    def __init__(self) -> None:
        self._by_project: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._by_user: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._projects_of: dict[WebSocket, set[UUID]] = {}
        self._user_of: dict[WebSocket, UUID] = {}

    async def connect(
        self, user_id: UUID, project_ids: Iterable[UUID], websocket: WebSocket
    ) -> None:
        project_ids = set(project_ids)
        is_first_connection = not self._by_user[user_id]
        self._by_user[user_id].add(websocket)
        self._user_of[websocket] = user_id
        self._projects_of[websocket] = project_ids
        for project_id in project_ids:
            self._by_project[project_id].add(websocket)
        if is_first_connection:
            await self._broadcast_presence(
                RealtimeEventType.PRESENCE_JOINED, user_id, project_ids
            )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Also the dead-connection cleanup path — broadcast()/send_to_user()
        call this on a failed send, so a network drop is treated the same
        as an explicit disconnect for presence purposes."""
        user_id = self._user_of.pop(websocket, None)
        project_ids = self._projects_of.pop(websocket, set())
        for project_id in project_ids:
            self._by_project[project_id].discard(websocket)
            if not self._by_project[project_id]:
                del self._by_project[project_id]
        if user_id is None:
            return
        self._by_user[user_id].discard(websocket)
        if not self._by_user[user_id]:
            del self._by_user[user_id]
            await self._broadcast_presence(
                RealtimeEventType.PRESENCE_LEFT, user_id, project_ids
            )

    def add_user_to_project(self, project_id: UUID, user_id: UUID) -> None:
        """Called when membership changes — updates any already-open
        connection for this user immediately, no reconnect required."""
        for websocket in self._by_user.get(user_id, ()):
            self._projects_of[websocket].add(project_id)
            self._by_project[project_id].add(websocket)

    def remove_user_from_project(self, project_id: UUID, user_id: UUID) -> None:
        for websocket in self._by_user.get(user_id, ()):
            self._projects_of[websocket].discard(project_id)
            self._by_project[project_id].discard(websocket)
        if not self._by_project.get(project_id):
            self._by_project.pop(project_id, None)

    async def broadcast(self, project_id: UUID, message: dict[str, Any]) -> None:
        for websocket in list(self._by_project.get(project_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning(f"Dropping dead WebSocket for project {project_id}")
                await self.disconnect(websocket)

    async def send_to_user(self, user_id: UUID, message: dict[str, Any]) -> None:
        for websocket in list(self._by_user.get(user_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning(f"Dropping dead WebSocket for user {user_id}")
                await self.disconnect(websocket)

    async def _broadcast_presence(
        self, event_type: RealtimeEventType, user_id: UUID, project_ids: Iterable[UUID]
    ) -> None:
        for project_id in project_ids:
            await self.broadcast(
                project_id,
                build_event(
                    event_type=event_type,
                    project_id=project_id,
                    data={"user_id": str(user_id)},
                    actor_id=user_id,
                ),
            )


def build_event(
    *,
    event_type: RealtimeEventType,
    project_id: UUID,
    data: dict[str, Any],
    actor_id: UUID,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "project_id": str(project_id),
        "data": data,
        "actor_id": str(actor_id),
    }


connection_manager = ConnectionManager()
