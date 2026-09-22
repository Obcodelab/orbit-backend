from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import (
    ORGS,
    _create_org,
    _invite_and_accept,
)

PROJECTS = "/api/v1/projects"


async def _create_project(
    client: AsyncClient,
    org_id: str,
    owner: AuthedUser,
    key: str = "ORB",
    name: str = "Orbit",
) -> dict:
    response = await client.post(
        f"{ORGS}/{org_id}/projects",
        json={"key": key, "name": name},
        headers=owner.headers,
    )
    return response.json()


# --- create ----------------------------------------------------------------------


async def test_create_project_requires_org_admin_or_owner(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "ORB", "name": "Orbit"},
        headers=member.headers,
    )
    assert response.status_code == 403


async def test_create_project_makes_creator_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "ORB", "name": "Orbit"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "ORB"
    assert body["owner_id"] == str(authenticated_user.user.id)
    assert body["status"] == "active"


async def test_create_project_rejects_lowercase_key(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "orb", "name": "Orbit"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 422


async def test_create_project_duplicate_key_in_same_org_returns_409(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "ORB", "name": "Orbit 2"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 409


async def test_create_project_same_key_in_different_org_succeeds(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org_a = await _create_org(client, authenticated_user, "Org A")
    org_b = await _create_org(client, authenticated_user, "Org B")
    await _create_project(client, org_a["org_id"], authenticated_user)

    response = await client.post(
        f"{ORGS}/{org_b['org_id']}/projects",
        json={"key": "ORB", "name": "Orbit"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201


# --- list / get --------------------------------------------------------------------


async def test_list_my_projects_excludes_archived_by_default(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    await _create_project(client, org["org_id"], authenticated_user, "ACT", "Active")
    archived = await _create_project(
        client, org["org_id"], authenticated_user, "ARC", "Archived"
    )
    await client.patch(
        f"{PROJECTS}/{archived['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.get(PROJECTS, headers=authenticated_user.headers)

    names = {p["name"] for p in response.json()["items"]}
    assert names == {"Active"}


async def test_list_my_projects_status_filter(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    archived = await _create_project(
        client, org["org_id"], authenticated_user, "ARC", "Archived"
    )
    await client.patch(
        f"{PROJECTS}/{archived['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )
    await _create_project(client, org["org_id"], authenticated_user, "ACT", "Active")

    response = await client.get(
        PROJECTS, params={"status": "archived"}, headers=authenticated_user.headers
    )

    names = {p["name"] for p in response.json()["items"]}
    assert names == {"Archived"}


async def test_get_project_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}", headers=stranger.headers
    )
    assert response.status_code == 403


async def test_get_project_returns_project_for_member(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}", headers=authenticated_user.headers
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == project["project_id"]


# --- update / archive --------------------------------------------------------------


async def test_update_project_owner_only(
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
        json={"user_id": str(member.user.id), "role": "admin"},
        headers=owner.headers,
    )

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"name": "New Name"},
        headers=member.headers,
    )
    assert response.status_code == 403

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"name": "New Name"},
        headers=owner.headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_archived_project_rejects_rename(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"name": "New Name"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 409


async def test_archived_project_can_be_unarchived(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "active"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"


# --- delete --------------------------------------------------------------------


async def test_delete_project_owner_only(
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
        json={"user_id": str(member.user.id), "role": "admin"},
        headers=owner.headers,
    )

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}", headers=member.headers
    )
    assert response.status_code == 403

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}", headers=owner.headers
    )
    assert response.status_code == 204

    follow_up = await client.get(
        f"{PROJECTS}/{project['project_id']}", headers=owner.headers
    )
    assert follow_up.status_code == 403  # membership row is gone too (cascade)


async def test_delete_archived_project_succeeds(
    client: AsyncClient, authenticated_user: AuthedUser
):
    """Deletion is the owner's override, not "new activity" — archiving
    freezes writes like rename/add-member, but never blocks delete."""
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}", headers=authenticated_user.headers
    )

    assert response.status_code == 204


async def test_delete_project_frees_up_its_key(
    client: AsyncClient, authenticated_user: AuthedUser
):
    """The concrete reason deletion exists alongside archiving: key is
    immutable, so delete-and-recreate is the only fix for a typo'd key."""
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user, "TYP")
    await client.delete(
        f"{PROJECTS}/{project['project_id']}", headers=authenticated_user.headers
    )

    response = await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "TYP", "name": "Fixed"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201


# --- members -------------------------------------------------------------------


async def test_add_project_member_requires_org_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/members",
        json={"user_id": str(stranger.user.id)},
        headers=owner.headers,
    )

    assert response.status_code == 404


async def test_add_project_member_succeeds_for_org_member(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/members",
        json={"user_id": str(member.user.id)},
        headers=owner.headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "member"
    assert body["user"]["email"] == member.user.email


async def test_add_project_member_already_member_returns_409(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/members",
        json={"user_id": str(authenticated_user.user.id)},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 409


async def test_add_project_member_rejects_owner_role(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/members",
        json={"user_id": str(member.user.id), "role": "owner"},
        headers=owner.headers,
    )

    assert response.status_code == 422


async def test_add_project_member_blocked_while_archived(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)
    project = await _create_project(client, org["org_id"], owner)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=owner.headers,
    )

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/members",
        json={"user_id": str(member.user.id)},
        headers=owner.headers,
    )

    assert response.status_code == 409


async def test_list_project_members_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/members", headers=stranger.headers
    )
    assert response.status_code == 403


async def test_get_project_member_unknown_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/members/{stranger.user.id}",
        headers=owner.headers,
    )
    assert response.status_code == 404


async def test_update_project_member_role_toggles_to_admin(
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

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/members/{member.user.id}",
        json={"role": "admin"},
        headers=owner.headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_update_project_member_role_cannot_target_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.patch(
        f"{PROJECTS}/{project['project_id']}/members/{authenticated_user.user.id}",
        json={"role": "admin"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 403


async def test_remove_project_member_success(
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

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/members/{member.user.id}",
        headers=owner.headers,
    )
    assert response.status_code == 204

    members = (
        await client.get(
            f"{PROJECTS}/{project['project_id']}/members", headers=owner.headers
        )
    ).json()["items"]
    assert len(members) == 1


async def test_remove_project_member_cannot_target_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/members/{authenticated_user.user.id}",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 403
