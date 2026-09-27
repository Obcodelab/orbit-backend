from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import (
    _create_org,
    _invite_and_accept,
)
from tests.test_projects.test_apis.test_project import PROJECTS, _create_project
from tests.test_tasks.test_apis.test_task import _create_task


async def test_activity_feed_includes_task_created_and_status_changed(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/status",
        json={"status": "in_progress"},
        headers=authenticated_user.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/activity",
        headers=authenticated_user.headers,
    )

    actions = [e["action"] for e in response.json()["items"]]
    assert "task.created" in actions
    assert "task.status_changed" in actions


async def test_activity_feed_includes_comment_added(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "hi"},
        headers=authenticated_user.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/activity",
        headers=authenticated_user.headers,
    )

    actions = [e["action"] for e in response.json()["items"]]
    assert "comment.added" in actions


async def test_activity_feed_includes_member_joined(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)
    project = await _create_project(client, org["org_id"], owner)

    await client.post(
        f"{PROJECTS}/{project['project_id']}/members",
        json={"user_id": str(member.user.id)},
        headers=owner.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/activity", headers=owner.headers
    )

    actions = [e["action"] for e in response.json()["items"]]
    assert "member.joined" in actions
