from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser

ORGS = "/api/v1/organizations"


async def _create_org(
    client: AsyncClient, owner: AuthedUser, name: str = "Acme Inc"
) -> dict:
    response = await client.post(ORGS, json={"name": name}, headers=owner.headers)
    return response.json()


async def _invite(
    client: AsyncClient,
    org_id: str,
    owner: AuthedUser,
    invitee: AuthedUser,
    role: str = "member",
) -> dict:
    response = await client.post(
        f"{ORGS}/{org_id}/members",
        json={"email": invitee.user.email, "role": role},
        headers=owner.headers,
    )
    return response.json()


async def _invite_and_accept(
    client: AsyncClient,
    org_id: str,
    owner: AuthedUser,
    invitee: AuthedUser,
    role: str = "member",
) -> None:
    """Setup helper for tests that need a *real* member, not just a pending
    invite — goes through the actual invite+accept round trip rather than
    poking the DB directly, so it breaks the same way the real flow would."""
    invite = await _invite(client, org_id, owner, invitee, role)
    await client.post(
        f"{ORGS}/invites/{invite['invite_id']}/accept", headers=invitee.headers
    )


# --- create / list -------------------------------------------------------------


async def test_create_organization_requires_auth(client: AsyncClient):
    response = await client.post(ORGS, json={"name": "Acme Inc"})
    assert response.status_code == 401


async def test_create_organization_makes_caller_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    response = await client.post(
        ORGS, json={"name": "Acme Inc"}, headers=authenticated_user.headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Inc"
    assert body["owner_id"] == str(authenticated_user.user.id)


async def test_list_my_organizations_only_shows_orgs_caller_belongs_to(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    user_a = await create_authenticated_user()
    user_b = await create_authenticated_user()
    await _create_org(client, user_a, "A's Org")
    await _create_org(client, user_b, "B's Org")

    response = await client.get(ORGS, headers=user_a.headers)

    names = {org["name"] for org in response.json()["items"]}
    assert names == {"A's Org"}


async def test_list_my_organizations_includes_role(
    client: AsyncClient, authenticated_user: AuthedUser
):
    await _create_org(client, authenticated_user)

    response = await client.get(ORGS, headers=authenticated_user.headers)

    assert response.json()["items"][0]["role"] == "owner"


# --- get / rename / delete ------------------------------------------------------


async def test_get_organization_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.get(f"{ORGS}/{org['org_id']}", headers=stranger.headers)
    assert response.status_code == 403


async def test_get_organization_unknown_id_returns_403_not_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    """require_role can't tell "org doesn't exist" from "you're not a
    member" apart without leaking which org IDs are real — both are the
    same 403, matching auth's own enumeration-safety stance elsewhere."""
    fake_id = "00000000-0000-7000-8000-000000000000"

    response = await client.get(f"{ORGS}/{fake_id}", headers=authenticated_user.headers)

    assert response.status_code == 403


async def test_get_organization_returns_org_for_member(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)

    response = await client.get(
        f"{ORGS}/{org['org_id']}", headers=authenticated_user.headers
    )

    assert response.status_code == 200
    assert response.json()["org_id"] == org["org_id"]


async def test_update_organization_owner_only(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    admin = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, admin, "admin")

    response = await client.patch(
        f"{ORGS}/{org['org_id']}", json={"name": "New Name"}, headers=admin.headers
    )
    assert response.status_code == 403

    response = await client.patch(
        f"{ORGS}/{org['org_id']}", json={"name": "New Name"}, headers=owner.headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_delete_organization_owner_only(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)

    response = await client.delete(f"{ORGS}/{org['org_id']}", headers=member.headers)
    assert response.status_code == 403

    response = await client.delete(f"{ORGS}/{org['org_id']}", headers=owner.headers)
    assert response.status_code == 204

    follow_up = await client.get(f"{ORGS}/{org['org_id']}", headers=owner.headers)
    assert follow_up.status_code == 403  # membership row is gone too (cascade)


async def test_delete_organization_blocked_when_it_has_projects(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "ORB", "name": "Orbit"},
        headers=authenticated_user.headers,
    )

    response = await client.delete(
        f"{ORGS}/{org['org_id']}", headers=authenticated_user.headers
    )

    assert response.status_code == 409


# --- members: invite / list -----------------------------------------------------


async def test_invite_member_requires_admin_or_owner(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": invitee.user.email},
        headers=member.headers,
    )
    assert response.status_code == 403


async def test_invite_member_creates_pending_invite_not_a_member(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": invitee.user.email},
        headers=owner.headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "member"
    assert body["email"] == invitee.user.email
    assert body["inviter"]["user_id"] == str(owner.user.id)

    # not a member yet — only a pending invite exists until they accept
    members = (
        await client.get(f"{ORGS}/{org['org_id']}/members", headers=owner.headers)
    ).json()["items"]
    assert len(members) == 1
    assert members[0]["user"]["email"] == owner.user.email


async def test_invite_member_unregistered_email_succeeds(
    client: AsyncClient, authenticated_user: AuthedUser
):
    """No account needed to be invited — see test_invite.py for the full
    unregistered-email flow (invite shows up once they register)."""
    org = await _create_org(client, authenticated_user)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": "nobody@example.com"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 201
    assert response.json()["email"] == "nobody@example.com"


async def test_invite_member_already_a_member_returns_409(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, invitee)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": invitee.user.email},
        headers=owner.headers,
    )

    assert response.status_code == 409


async def test_invite_member_already_invited_returns_409(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite(client, org["org_id"], owner, invitee)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": invitee.user.email},
        headers=owner.headers,
    )

    assert response.status_code == 409


async def test_invite_member_rejects_owner_role(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": invitee.user.email, "role": "owner"},
        headers=owner.headers,
    )

    assert response.status_code == 422


async def test_list_members_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.get(
        f"{ORGS}/{org['org_id']}/members", headers=stranger.headers
    )
    assert response.status_code == 403


async def test_list_members_returns_user_details(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)

    response = await client.get(
        f"{ORGS}/{org['org_id']}/members", headers=authenticated_user.headers
    )

    assert response.status_code == 200
    members = response.json()["items"]
    assert len(members) == 1
    assert members[0]["user"]["email"] == authenticated_user.user.email
    assert members[0]["role"] == "owner"


async def test_get_member_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.get(
        f"{ORGS}/{org['org_id']}/members/{owner.user.id}", headers=stranger.headers
    )
    assert response.status_code == 403


async def test_get_member_returns_user_details(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member, "admin")

    response = await client.get(
        f"{ORGS}/{org['org_id']}/members/{member.user.id}", headers=owner.headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["user"]["email"] == member.user.email


async def test_get_member_unknown_member_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.get(
        f"{ORGS}/{org['org_id']}/members/{stranger.user.id}", headers=owner.headers
    )

    assert response.status_code == 404


# --- members: change role -------------------------------------------------------


async def test_update_member_role_toggles_member_to_admin(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)

    response = await client.patch(
        f"{ORGS}/{org['org_id']}/members/{member.user.id}",
        json={"role": "admin"},
        headers=owner.headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_update_member_role_rejects_owner_role(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)

    response = await client.patch(
        f"{ORGS}/{org['org_id']}/members/{member.user.id}",
        json={"role": "owner"},
        headers=owner.headers,
    )

    assert response.status_code == 422


async def test_update_member_role_cannot_target_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)

    response = await client.patch(
        f"{ORGS}/{org['org_id']}/members/{authenticated_user.user.id}",
        json={"role": "admin"},
        headers=authenticated_user.headers,
    )

    assert response.status_code == 403


async def test_update_member_role_unknown_member_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.patch(
        f"{ORGS}/{org['org_id']}/members/{stranger.user.id}",
        json={"role": "admin"},
        headers=owner.headers,
    )

    assert response.status_code == 404


async def test_update_member_role_requires_admin_or_owner(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member_a = await create_authenticated_user()
    member_b = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member_a)
    await _invite_and_accept(client, org["org_id"], owner, member_b)

    response = await client.patch(
        f"{ORGS}/{org['org_id']}/members/{member_b.user.id}",
        json={"role": "admin"},
        headers=member_a.headers,
    )

    assert response.status_code == 403


# --- members: remove -------------------------------------------------------------


async def test_remove_member_success(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member)

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/members/{member.user.id}", headers=owner.headers
    )
    assert response.status_code == 204

    members = (
        await client.get(f"{ORGS}/{org['org_id']}/members", headers=owner.headers)
    ).json()["items"]
    assert len(members) == 1


async def test_remove_member_blocked_when_they_own_a_project(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member, "admin")
    await client.post(
        f"{ORGS}/{org['org_id']}/projects",
        json={"key": "ORB", "name": "Orbit"},
        headers=member.headers,
    )

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/members/{member.user.id}", headers=owner.headers
    )

    assert response.status_code == 409


async def test_remove_member_cannot_target_owner(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/members/{authenticated_user.user.id}",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 403


async def test_remove_member_unknown_member_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/members/{stranger.user.id}", headers=owner.headers
    )

    assert response.status_code == 404


async def test_remove_member_requires_admin_or_owner(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    member_a = await create_authenticated_user()
    member_b = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite_and_accept(client, org["org_id"], owner, member_a)
    await _invite_and_accept(client, org["org_id"], owner, member_b)

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/members/{member_b.user.id}", headers=member_a.headers
    )

    assert response.status_code == 403
