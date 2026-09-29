from uuid import uuid4

import core.notifications as notifications_module
from core.notifications import notify
from core.websocket_manager import connection_manager
from tests.test_core.test_websocket_manager import FakeWebSocket


async def test_notify_pushes_to_connected_socket_and_fires_mock_email(monkeypatch):
    project_id, user_id = uuid4(), uuid4()
    ws = FakeWebSocket()
    await connection_manager.connect(user_id, [project_id], ws)
    ws.received.clear()
    sent: list[tuple] = []
    monkeypatch.setattr(
        notifications_module, "send_email_mock", lambda uid, e: sent.append((uid, e))
    )
    event = {"type": "task.assigned"}

    try:
        await notify(user_id, event)
    finally:
        await connection_manager.disconnect(ws)

    assert ws.received == [event]
    assert sent == [(user_id, event)]


async def test_notify_still_fires_mock_email_when_nobody_connected(monkeypatch):
    user_id = uuid4()
    sent: list[tuple] = []
    monkeypatch.setattr(
        notifications_module, "send_email_mock", lambda uid, e: sent.append((uid, e))
    )

    await notify(user_id, {"type": "task.assigned"})

    assert sent == [(user_id, {"type": "task.assigned"})]
