from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import (
    _create_org,
    _invite_and_accept,
)
from tests.test_projects.test_apis.test_project import PROJECTS, _create_project


async def test_create_conversation_succeeds(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/ai/conversations",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201
    assert response.json()["title"] is None


async def test_create_conversation_blocked_while_archived(
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
        f"{PROJECTS}/{project['project_id']}/ai/conversations",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 409


async def test_list_conversations_returns_created(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.post(
        f"{PROJECTS}/{project['project_id']}/ai/conversations",
        headers=authenticated_user.headers,
    )

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/ai/conversations",
        headers=authenticated_user.headers,
    )

    assert response.json()["total"] == 1


async def test_list_messages_unknown_conversation_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/ai/conversations"
        f"/{project['project_id']}/messages",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 404


async def test_ask_returns_assistant_message(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    conversation = (
        await client.post(
            f"{PROJECTS}/{project['project_id']}/ai/conversations",
            headers=authenticated_user.headers,
        )
    ).json()

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/ai/conversations"
        f"/{conversation['conversation_id']}/ask",
        json={"question": "what's in the docs?"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    assert "couldn't find anything relevant" in response.json()["content"]


async def test_update_conversation_succeeds_for_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    conversation = (
        await client.post(
            f"{PROJECTS}/{project['project_id']}/ai/conversations",
            headers=authenticated_user.headers,
        )
    ).json()

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/ai/conversations"
        f"/{conversation['conversation_id']}",
        json={"title": "Renamed"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"


async def test_update_conversation_requires_owner(
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
    conversation = (
        await client.post(
            f"{PROJECTS}/{project['project_id']}/ai/conversations",
            headers=owner.headers,
        )
    ).json()

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/ai/conversations"
        f"/{conversation['conversation_id']}",
        json={"title": "Hijacked"},
        headers=member.headers,
    )

    assert response.status_code == 403


async def test_delete_conversation_succeeds_for_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    conversation = (
        await client.post(
            f"{PROJECTS}/{project['project_id']}/ai/conversations",
            headers=authenticated_user.headers,
        )
    ).json()

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/ai/conversations"
        f"/{conversation['conversation_id']}",
        headers=authenticated_user.headers,
    )
    assert response.status_code == 204

    listing = await client.get(
        f"{PROJECTS}/{project['project_id']}/ai/conversations",
        headers=authenticated_user.headers,
    )
    assert listing.json()["total"] == 0


async def test_delete_conversation_requires_owner(
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
    conversation = (
        await client.post(
            f"{PROJECTS}/{project['project_id']}/ai/conversations",
            headers=owner.headers,
        )
    ).json()

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/ai/conversations"
        f"/{conversation['conversation_id']}",
        headers=member.headers,
    )

    assert response.status_code == 403


async def test_delete_conversation_unknown_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/ai/conversations/{project['project_id']}",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 404
