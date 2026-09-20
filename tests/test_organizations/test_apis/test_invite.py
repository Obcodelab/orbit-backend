from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from tests.conftest import AuthedUser
from tests.test_organizations.test_apis.test_organization import (
    ORGS,
    _create_org,
    _invite,
)

# --- my invites: list / accept / decline ----------------------------------------


async def test_list_my_invites_shows_pending_invite(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner, "Acme Inc")
    await _invite(client, org["org_id"], owner, invitee)

    response = await client.get(f"{ORGS}/invites", headers=invitee.headers)

    assert response.status_code == 200
    invites = response.json()
    assert len(invites) == 1
    assert invites[0]["organization"]["name"] == "Acme Inc"
    assert invites[0]["role"] == "member"
    assert invites[0]["inviter"]["user_id"] == str(owner.user.id)


async def test_list_my_invites_empty_when_none(
    client: AsyncClient, authenticated_user: AuthedUser
):
    response = await client.get(f"{ORGS}/invites", headers=authenticated_user.headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_accept_invite_creates_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    invite = await _invite(client, org["org_id"], owner, invitee, "admin")

    response = await client.post(
        f"{ORGS}/invites/{invite['invite_id']}/accept", headers=invitee.headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["org_id"] == org["org_id"]
    assert body["role"] == "admin"

    members = (
        await client.get(f"{ORGS}/{org['org_id']}/members", headers=owner.headers)
    ).json()
    emails = {m["user"]["email"] for m in members}
    assert invitee.user.email in emails

    # accepted invite is gone
    remaining = (await client.get(f"{ORGS}/invites", headers=invitee.headers)).json()
    assert remaining == []


async def test_accept_invite_belonging_to_someone_else_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    invite = await _invite(client, org["org_id"], owner, invitee)

    response = await client.post(
        f"{ORGS}/invites/{invite['invite_id']}/accept", headers=stranger.headers
    )

    assert response.status_code == 404


async def test_accept_unknown_invite_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    fake_id = "00000000-0000-7000-8000-000000000000"

    response = await client.post(
        f"{ORGS}/invites/{fake_id}/accept", headers=authenticated_user.headers
    )

    assert response.status_code == 404


async def test_decline_invite_removes_it(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    invite = await _invite(client, org["org_id"], owner, invitee)

    response = await client.post(
        f"{ORGS}/invites/{invite['invite_id']}/decline", headers=invitee.headers
    )
    assert response.status_code == 204

    remaining = (await client.get(f"{ORGS}/invites", headers=invitee.headers)).json()
    assert remaining == []

    members = (
        await client.get(f"{ORGS}/{org['org_id']}/members", headers=owner.headers)
    ).json()
    assert len(members) == 1  # just the owner — decline never creates a member


async def test_decline_invite_belonging_to_someone_else_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    invite = await _invite(client, org["org_id"], owner, invitee)

    response = await client.post(
        f"{ORGS}/invites/{invite['invite_id']}/decline", headers=stranger.headers
    )

    assert response.status_code == 404


# --- org invites: list / revoke (admin/owner) -----------------------------------


async def test_list_org_invites_requires_admin_or_owner(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.get(
        f"{ORGS}/{org['org_id']}/invites", headers=stranger.headers
    )

    assert response.status_code == 403


async def test_list_org_invites_shows_pending_invite(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    await _invite(client, org["org_id"], owner, invitee)

    response = await client.get(
        f"{ORGS}/{org['org_id']}/invites", headers=owner.headers
    )

    assert response.status_code == 200
    invites = response.json()
    assert len(invites) == 1
    assert invites[0]["email"] == invitee.user.email


async def test_invite_unregistered_email_appears_in_org_invites(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    """No account is required to be invited — the invite is keyed by email
    and just sits there until someone registers with that address."""
    owner = await create_authenticated_user()
    org = await _create_org(client, owner)

    response = await client.post(
        f"{ORGS}/{org['org_id']}/members",
        json={"email": "never-registered@example.com"},
        headers=owner.headers,
    )
    assert response.status_code == 201
    assert response.json()["email"] == "never-registered@example.com"

    invites = (
        await client.get(f"{ORGS}/{org['org_id']}/invites", headers=owner.headers)
    ).json()
    assert invites[0]["email"] == "never-registered@example.com"


async def test_unregistered_invitee_sees_and_accepts_invite_after_registering(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    """The full cross-module round trip: invited before any account exists,
    then registers/verifies/logs in with that exact email, and the invite
    that was sitting there the whole time becomes visible and acceptable —
    no auto-creation, no temporary password, nothing invite-specific
    happens during registration itself."""
    owner = await create_authenticated_user()
    org = await _create_org(client, owner)

    invite = (
        await client.post(
            f"{ORGS}/{org['org_id']}/members",
            json={"email": "future-member@example.com", "role": "admin"},
            headers=owner.headers,
        )
    ).json()

    # not visible to anyone yet — no account exists for that email
    invitee = await create_authenticated_user(email="future-member@example.com")

    my_invites = (await client.get(f"{ORGS}/invites", headers=invitee.headers)).json()
    assert len(my_invites) == 1
    assert my_invites[0]["organization"]["org_id"] == org["org_id"]
    assert my_invites[0]["role"] == "admin"

    response = await client.post(
        f"{ORGS}/invites/{invite['invite_id']}/accept", headers=invitee.headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    members = (
        await client.get(f"{ORGS}/{org['org_id']}/members", headers=owner.headers)
    ).json()
    emails = {m["user"]["email"] for m in members}
    assert "future-member@example.com" in emails


async def test_revoke_invite_removes_it(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org = await _create_org(client, owner)
    invite = await _invite(client, org["org_id"], owner, invitee)

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/invites/{invite['invite_id']}", headers=owner.headers
    )
    assert response.status_code == 204

    remaining = (await client.get(f"{ORGS}/invites", headers=invitee.headers)).json()
    assert remaining == []


async def test_revoke_invite_requires_admin_or_owner(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    invite = await _invite(client, org["org_id"], owner, invitee)

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/invites/{invite['invite_id']}",
        headers=stranger.headers,
    )

    assert response.status_code == 403


async def test_revoke_unknown_invite_returns_404(
    client: AsyncClient, authenticated_user: AuthedUser
):
    org = await _create_org(client, authenticated_user)
    fake_id = "00000000-0000-7000-8000-000000000000"

    response = await client.delete(
        f"{ORGS}/{org['org_id']}/invites/{fake_id}", headers=authenticated_user.headers
    )

    assert response.status_code == 404


async def test_revoke_invite_from_wrong_org_returns_404(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
):
    owner = await create_authenticated_user()
    invitee = await create_authenticated_user()
    org_a = await _create_org(client, owner, "Org A")
    org_b = await _create_org(client, owner, "Org B")
    invite = await _invite(client, org_a["org_id"], owner, invitee)

    response = await client.delete(
        f"{ORGS}/{org_b['org_id']}/invites/{invite['invite_id']}", headers=owner.headers
    )

    assert response.status_code == 404
