from uuid import uuid4

from core.types import RealtimeEventType
from core.websocket_manager import ConnectionManager, build_event


class FakeWebSocket:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.received: list[dict] = []

    async def send_json(self, message: dict) -> None:
        if self.fails:
            raise RuntimeError("connection closed")
        self.received.append(message)


async def test_broadcast_delivers_to_all_connections_for_project():
    manager = ConnectionManager()
    project_id, user1, user2 = uuid4(), uuid4(), uuid4()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(user1, [project_id], ws1)
    await manager.connect(user2, [project_id], ws2)
    ws1.received.clear()
    ws2.received.clear()

    await manager.broadcast(project_id, {"type": "task.created"})

    assert ws1.received == [{"type": "task.created"}]
    assert ws2.received == [{"type": "task.created"}]


async def test_broadcast_does_not_leak_across_projects():
    manager = ConnectionManager()
    project_a, project_b, user_id = uuid4(), uuid4(), uuid4()
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(user_id, [project_a], ws_a)
    await manager.connect(user_id, [project_b], ws_b)
    ws_a.received.clear()
    ws_b.received.clear()

    await manager.broadcast(project_a, {"type": "task.created"})

    assert ws_a.received == [{"type": "task.created"}]
    assert ws_b.received == []


async def test_connection_registered_to_multiple_projects_receives_both():
    """The core behavior change from the old per-project-only model — one
    connection now hears everything across every project it belongs to."""
    manager = ConnectionManager()
    project_a, project_b, user_id = uuid4(), uuid4(), uuid4()
    ws = FakeWebSocket()
    await manager.connect(user_id, [project_a, project_b], ws)
    ws.received.clear()

    await manager.broadcast(project_a, {"type": "task.created"})
    await manager.broadcast(project_b, {"type": "comment.added"})

    assert ws.received == [{"type": "task.created"}, {"type": "comment.added"}]


async def test_broadcast_drops_dead_connections():
    manager = ConnectionManager()
    project_id, user1, user2 = uuid4(), uuid4(), uuid4()
    dead, alive = FakeWebSocket(), FakeWebSocket()
    await manager.connect(user1, [project_id], dead)
    await manager.connect(user2, [project_id], alive)
    dead.fails = True

    await manager.broadcast(project_id, {"type": "task.created"})

    # Cleaning up the dead connection fires a nested presence.left
    # broadcast that also reaches `alive` — set iteration order means it
    # can land before or after task.created, so check membership only.
    assert {"type": "task.created"} in alive.received
    assert dead not in manager._by_project.get(project_id, set())
    assert dead not in manager._by_user.get(user1, set())


async def test_send_to_user_delivers_to_all_that_users_connections():
    manager = ConnectionManager()
    project_a, project_b, user_id = uuid4(), uuid4(), uuid4()
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(user_id, [project_a], ws_a)
    await manager.connect(user_id, [project_b], ws_b)
    ws_a.received.clear()
    ws_b.received.clear()

    await manager.send_to_user(user_id, {"type": "task.assigned"})

    assert ws_a.received == [{"type": "task.assigned"}]
    assert ws_b.received == [{"type": "task.assigned"}]


async def test_send_to_user_does_not_leak_to_other_users():
    manager = ConnectionManager()
    project_id, user_a, user_b = uuid4(), uuid4(), uuid4()
    ws_a, ws_b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(user_a, [project_id], ws_a)
    await manager.connect(user_b, [project_id], ws_b)
    ws_a.received.clear()
    ws_b.received.clear()

    await manager.send_to_user(user_a, {"type": "task.assigned"})

    assert ws_a.received == [{"type": "task.assigned"}]
    assert ws_b.received == []


async def test_disconnect_removes_empty_project_and_user_entries():
    manager = ConnectionManager()
    project_id, user_id = uuid4(), uuid4()
    ws = FakeWebSocket()
    await manager.connect(user_id, [project_id], ws)

    await manager.disconnect(ws)

    assert project_id not in manager._by_project
    assert user_id not in manager._by_user


async def test_connect_broadcasts_presence_joined_to_others_already_there():
    manager = ConnectionManager()
    project_id, user_a, user_b = uuid4(), uuid4(), uuid4()
    ws_a = FakeWebSocket()
    await manager.connect(user_a, [project_id], ws_a)
    ws_a.received.clear()
    ws_b = FakeWebSocket()

    await manager.connect(user_b, [project_id], ws_b)

    assert ws_a.received == [
        build_event(
            event_type=RealtimeEventType.PRESENCE_JOINED,
            project_id=project_id,
            data={"user_id": str(user_b)},
            actor_id=user_b,
        )
    ]


async def test_second_connection_from_same_user_does_not_re_broadcast_presence():
    manager = ConnectionManager()
    project_id, user_id = uuid4(), uuid4()
    ws1 = FakeWebSocket()
    await manager.connect(user_id, [project_id], ws1)
    observer = FakeWebSocket()
    await manager.connect(uuid4(), [project_id], observer)
    observer.received.clear()
    ws2 = FakeWebSocket()

    await manager.connect(user_id, [project_id], ws2)  # second tab, same user

    assert observer.received == []


async def test_disconnect_broadcasts_presence_left_only_on_last_connection():
    manager = ConnectionManager()
    project_id, user_id = uuid4(), uuid4()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await manager.connect(user_id, [project_id], ws1)
    await manager.connect(user_id, [project_id], ws2)  # two tabs
    observer = FakeWebSocket()
    await manager.connect(uuid4(), [project_id], observer)
    observer.received.clear()

    await manager.disconnect(ws1)
    assert observer.received == []

    await manager.disconnect(ws2)
    assert observer.received == [
        build_event(
            event_type=RealtimeEventType.PRESENCE_LEFT,
            project_id=project_id,
            data={"user_id": str(user_id)},
            actor_id=user_id,
        )
    ]


async def test_add_user_to_project_registers_existing_connection():
    manager = ConnectionManager()
    project_id, user_id = uuid4(), uuid4()
    ws = FakeWebSocket()
    await manager.connect(user_id, [], ws)

    manager.add_user_to_project(project_id, user_id)
    await manager.broadcast(project_id, {"type": "member.joined"})

    assert {"type": "member.joined"} in ws.received


async def test_remove_user_from_project_unregisters_existing_connection():
    manager = ConnectionManager()
    project_id, user_id = uuid4(), uuid4()
    ws = FakeWebSocket()
    await manager.connect(user_id, [project_id], ws)
    ws.received.clear()

    manager.remove_user_from_project(project_id, user_id)
    await manager.broadcast(project_id, {"type": "task.created"})

    assert ws.received == []


def test_build_event_shape():
    project_id, actor_id = uuid4(), uuid4()

    event = build_event(
        event_type=RealtimeEventType.TASK_UPDATED,
        project_id=project_id,
        data={"foo": "bar"},
        actor_id=actor_id,
    )

    assert event == {
        "type": "task.updated",
        "project_id": str(project_id),
        "data": {"foo": "bar"},
        "actor_id": str(actor_id),
    }
