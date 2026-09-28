from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from core.config import settings
from tests.conftest import AuthedUser
from tests.test_files.fake_storage import FakeStorageBackend
from tests.test_organizations.test_apis.test_organization import (
    _create_org,
    _invite_and_accept,
)
from tests.test_projects.test_apis.test_project import PROJECTS, _create_project
from tests.test_tasks.test_apis.test_task import _create_task


async def _upload(
    client: AsyncClient,
    project_id: str,
    owner: AuthedUser,
    *,
    filename: str = "spec.pdf",
    content: bytes = b"hello world",
    mime_type: str = "application/pdf",
    task_id: str | None = None,
) -> dict:
    data = {"task_id": task_id} if task_id else {}
    response = await client.post(
        f"{PROJECTS}/{project_id}/documents",
        files={"file": (filename, content, mime_type)},
        data=data,
        headers=owner.headers,
    )
    return response.json()


async def test_upload_document_requires_membership(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
    fake_storage_backend: FakeStorageBackend,
):
    owner = await create_authenticated_user()
    stranger = await create_authenticated_user()
    org = await _create_org(client, owner)
    project = await _create_project(client, org["org_id"], owner)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/documents",
        files={"file": ("spec.pdf", b"hello", "application/pdf")},
        headers=stranger.headers,
    )
    assert response.status_code == 403


async def test_upload_document_succeeds_for_any_member(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
    fake_storage_backend: FakeStorageBackend,
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

    body = await _upload(client, project["project_id"], member)

    assert body["filename"] == "spec.pdf"
    assert body["mime_type"] == "application/pdf"
    assert len(fake_storage_backend.files) == 1


async def test_upload_document_rejects_unsupported_type(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/documents",
        files={"file": ("virus.exe", b"hello", "application/x-msdownload")},
        headers=authenticated_user.headers,
    )
    assert response.status_code == 400


async def test_upload_document_rejects_oversized_file(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    oversized = b"x" * (settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/documents",
        files={"file": ("big.pdf", oversized, "application/pdf")},
        headers=authenticated_user.headers,
    )
    assert response.status_code == 413


async def test_upload_document_blocked_while_archived(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/documents",
        files={"file": ("spec.pdf", b"hello", "application/pdf")},
        headers=authenticated_user.headers,
    )
    assert response.status_code == 409


async def test_upload_document_with_task_attaches_it(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    task = await _create_task(client, project["project_id"], authenticated_user)

    body = await _upload(
        client, project["project_id"], authenticated_user, task_id=task["task_id"]
    )

    assert body["task_id"] == task["task_id"]


async def test_upload_document_unknown_task_returns_400(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.post(
        f"{PROJECTS}/{project['project_id']}/documents",
        files={"file": ("spec.pdf", b"hello", "application/pdf")},
        data={"task_id": str(project["project_id"])},
        headers=authenticated_user.headers,
    )
    assert response.status_code == 400


async def test_list_documents_returns_uploaded(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    await _upload(client, project["project_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/documents",
        headers=authenticated_user.headers,
    )

    assert response.json()["total"] == 1


async def test_get_document_unknown_returns_404(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/documents/{project['project_id']}",
        headers=authenticated_user.headers,
    )
    assert response.status_code == 404


async def test_get_download_url_returns_fake_backend_url(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    document = await _upload(client, project["project_id"], authenticated_user)

    response = await client.get(
        f"{PROJECTS}/{project['project_id']}/documents/{document['document_id']}/download",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 200
    assert response.json()["url"].startswith("https://fake-storage.test/")


async def test_delete_document_requires_uploader_or_admin(
    client: AsyncClient,
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
    fake_storage_backend: FakeStorageBackend,
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
    document = await _upload(client, project["project_id"], owner)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/documents/{document['document_id']}",
        headers=member.headers,
    )
    assert response.status_code == 403


async def test_delete_document_succeeds_for_uploader(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    document = await _upload(client, project["project_id"], authenticated_user)

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/documents/{document['document_id']}",
        headers=authenticated_user.headers,
    )

    assert response.status_code == 204
    assert fake_storage_backend.deleted


async def test_delete_document_blocked_while_archived(
    client: AsyncClient,
    authenticated_user: AuthedUser,
    fake_storage_backend: FakeStorageBackend,
):
    org = await _create_org(client, authenticated_user)
    project = await _create_project(client, org["org_id"], authenticated_user)
    document = await _upload(client, project["project_id"], authenticated_user)
    await client.patch(
        f"{PROJECTS}/{project['project_id']}",
        json={"status": "archived"},
        headers=authenticated_user.headers,
    )

    response = await client.delete(
        f"{PROJECTS}/{project['project_id']}/documents/{document['document_id']}",
        headers=authenticated_user.headers,
    )
    assert response.status_code == 409
