from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import (
    _create_org,
    _invite_and_accept,
)
from tests.test_projects.test_apis.test_project import PROJECTS, _create_project
from tests.test_tasks.test_apis.test_task import _create_task


async def test_add_comment_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)
    task = await _create_task(client, project["project_id"], owner)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "hello"},
        headers=stranger.headers,
    )
    assert response.status_code == 403


async def test_add_comment_succeeds_for_any_member(
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

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "hello"},
        headers=member.headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["body"] == "hello"
    assert body["user"]["email"] == member.user.email


async def test_add_comment_unknown_task_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{project['project_id']}/comments",
        json={"body": "hello"},
        headers=authenticated_user.headers,
    )
    assert response.status_code == 404


async def test_list_comments_returns_in_chronological_order(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "first"},
        headers=authenticated_user.headers,
    )
    await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "second"},
        headers=authenticated_user.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        headers=authenticated_user.headers,
    )

    items = response.json()["items"]
    assert [c["body"] for c in items] == ["first", "second"]


async def test_update_comment_succeeds_for_author(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)
    create_response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "original"},
        headers=authenticated_user.headers,
    )
    comment_id = create_response.json()["comment_id"]

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments/{comment_id}",
        json={"body": "edited"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["body"] == "edited"


async def test_update_comment_requires_author(
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
    create_response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "original"},
        headers=owner.headers,
    )
    comment_id = create_response.json()["comment_id"]

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments/{comment_id}",
        json={"body": "edited"},
        headers=member.headers,
    )

    assert response.status_code == 403


async def test_update_comment_unknown_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments/{task['task_id']}",
        json={"body": "edited"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 404


async def test_delete_comment_succeeds_for_author(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)
    create_response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "original"},
        headers=authenticated_user.headers,
    )
    comment_id = create_response.json()["comment_id"]

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments/{comment_id}",
        headers=authenticated_user.headers,
    )
    assert response.status_code == 204

    listing = await client.get(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        headers=authenticated_user.headers,
    )
    assert listing.json()["items"] == []


async def test_delete_comment_requires_author(
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
    create_response = await client.post(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments",
        json={"body": "original"},
        headers=owner.headers,
    )
    comment_id = create_response.json()["comment_id"]

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments/{comment_id}",
        headers=member.headers,
    )

    assert response.status_code == 403


async def test_delete_comment_unknown_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/tasks/{task['task_id']}/comments/{task['task_id']}",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 404
