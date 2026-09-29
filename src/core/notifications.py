from collections.abc import Iterable
from typing import Any
from uuid import UUID

from loguru import logger

from core.websocket_manager import connection_manager


def send_email_mock(user_id: UUID, event: dict[str, Any]) -> None:
    logger.info(f"[MOCK EMAIL] To user {user_id}: {event}")


async def notify(user_id: UUID, event: dict[str, Any]) -> None:
    """Push to the user's WebSocket(s) if connected, and always also
    'send' the mocked email — not conditional on socket delivery, so the
    email path stays exercised regardless of whether real email backs it
    later, and firing policy isn't tangled up with the v1 stub."""
    await connection_manager.send_to_user(user_id, event)
    send_email_mock(user_id, event)


async def notify_many(user_ids: Iterable[UUID], event: dict[str, Any]) -> None:
    """Meant to run as a single BackgroundTask covering every recipient,
    not one task per user — the event is already fully serialized by the
    caller, so this needs nothing from the request's DB session."""
    for user_id in user_ids:
        await notify(user_id, event)
