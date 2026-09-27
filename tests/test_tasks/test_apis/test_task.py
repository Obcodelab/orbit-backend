from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import (
    _create_org,
    _invite_and_accept,
)
from tests.test_projects.test_apis.test_project import PROJECTS, _create_project


async def _create_task(
    client: AsyncClient,
    project_id: str,
    owner: AuthedUser,
    title: str = "Fix bug",
    assignee_ids: list[str] | None = None,
) -> dict:
    response = await client.post(
        f"{PROJECTS}/{project_id}/tasks",
        json={"title": title, "assignee_ids": assignee_ids or []},
        headers=owner.headers,
    )
    return response.json()


# --- create ----------------------------------------------------------------------


async def test_create_task_requires_admin_or_owner(
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

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Fix bug"},
        headers=member.headers,
    )
    assert response.status_code == 403


async def test_create_task_succeeds_for_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Fix bug"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "ORB-1"
    assert body["status"] == "todo"
    assert body["assignees"] == []


async def test_create_task_rejects_non_member_assignee(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Fix bug", "assignee_ids": [str(stranger.user.id)]},
        headers=owner.headers,
    )

    assert response.status_code == 400


async def test_create_task_rejects_unknown_parent(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Child", "parent_task_id": str(project["project_id"])},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 400


async def test_create_subtask_succeeds(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    parent = await _create_task(client, project["project_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Child", "parent_task_id": parent["task_id"]},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201
    assert response.json()["parent_task_id"] == parent["task_id"]


async def test_create_task_blocked_while_project_archived(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Fix bug"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 409


# --- list / get --------------------------------------------------------------------


async def test_list_tasks_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks", headers=stranger.headers
    )
    assert response.status_code == 403


async def test_list_tasks_status_filter(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await _create_task(client, project["project_id"], authenticated_user, "Task 1")

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks",
        params={"status": "done"},
        headers=authenticated_user.headers,
    )

    assert response.json()["total"] == 0


async def test_list_tasks_priority_filter(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Urgent", "priority": "high"},
        headers=authenticated_user.headers,
    )
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Later", "priority": "low"},
        headers=authenticated_user.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks",
        params={"priority": "high"},
        headers=authenticated_user.headers,
    )

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Urgent"


async def test_list_tasks_label_filter(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Bug", "labels": "bug,urgent"},
        headers=authenticated_user.headers,
    )
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks",
        json={"title": "Feature", "labels": "feature"},
        headers=authenticated_user.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks",
        params={"label": "urgent"},
        headers=authenticated_user.headers,
    )

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Bug"


async def test_get_task_unknown_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks/{project['project_id']}",
        headers=authenticated_user.headers,
    )
    assert response.status_code == 404


async def test_get_task_returns_task(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == task["task_id"]


# --- update / status ---------------------------------------------------------------


async def test_update_task_requires_admin_or_owner(
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
    task = await _create_task(client, project["project_id"], owner)

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}",
        json={"title": "Renamed"},
        headers=member.headers,
    )
    assert response.status_code == 403


async def test_update_task_replaces_assignees(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(
        client,
        project["project_id"],
        authenticated_user,
        assignee_ids=[str(authenticated_user.user.id)],
    )

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}",
        json={"assignee_ids": []},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["assignees"] == []


async def test_update_task_status_allowed_for_assignee(
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
    task = await _create_task(
        client, project["project_id"], owner, assignee_ids=[str(member.user.id)]
    )

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/status",
        json={"status": "in_progress"},
        headers=member.headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


async def test_update_task_status_forbidden_for_non_assignee_member(
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
    task = await _create_task(client, project["project_id"], owner)

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/status",
        json={"status": "in_progress"},
        headers=member.headers,
    )

    assert response.status_code == 403


# --- delete --------------------------------------------------------------------


async def test_delete_task_requires_admin_or_owner(
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
    task = await _create_task(client, project["project_id"], owner)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}",
        headers=member.headers,
    )
    assert response.status_code == 403

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}",
        headers=owner.headers,
    )
    assert response.status_code == 204


async def test_delete_task_unknown_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/tasks/{project['project_id']}",
        headers=authenticated_user.headers,
    )
    assert response.status_code == 404
