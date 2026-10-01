from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import _create_org
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
