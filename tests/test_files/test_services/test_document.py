import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from core.config import settings
from core.security import create_download_token, hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.files.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    InvalidDownloadTokenError,
    NotDocumentUploaderError,
    UnsupportedFileTypeError,
)
from modules.files.services import document_service
from modules.organizations.repositories import organization_member_repository
from modules.organizations.services import organization_service
from modules.organizations.types import OrganizationRole
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_member_repository, project_repository
from modules.projects.services import project_service
from modules.projects.types import ProjectRole, ProjectStatus
from modules.tasks.exceptions import ParentTaskNotFoundError
from modules.tasks.services import task_service
from modules.tasks.types import TaskPriority
from tests.test_files.fake_storage import FakeStorageBackend


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Service",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(db_session: AsyncSession, owner: User):
    org = await organization_service.create_organization(
        db_session, name="Test Org", owner=owner
    )
    return await project_service.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner=owner,
    )


async def test_upload_document_succeeds(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner1@example.com")
    project = await _make_project(db_session, owner)
    storage = FakeStorageBackend()

    document, dedup_source_id = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"hello",
        mime_type="application/pdf",
        storage_backend=storage,
    )

    assert document.filename == "spec.pdf"
    assert document.file_size == 5
    assert len(storage.files) == 1
    assert dedup_source_id is None


async def test_upload_document_dedups_identical_content(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner-dedup@example.com")
    project = await _make_project(db_session, owner)
    storage = FakeStorageBackend()

    first, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"same bytes",
        mime_type="application/pdf",
        storage_backend=storage,
    )
    second, dedup_source_id = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="renamed.pdf",
        file_bytes=b"same bytes",
        mime_type="application/pdf",
        storage_backend=storage,
    )

    assert dedup_source_id == first.id
    assert second.storage_path == first.storage_path
    assert len(storage.files) == 1


async def test_upload_document_raises_when_project_archived(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner2@example.com")
    project = await _make_project(db_session, owner)
    project = await project_repository.update_fields(
        db_session, project=project, updates={"status": ProjectStatus.ARCHIVED}
    )

    with pytest.raises(ProjectArchivedError):
        await document_service.upload_document(
            db_session,
            project=project,
            task_id=None,
            uploader_id=owner.id,
            filename="spec.pdf",
            file_bytes=b"hello",
            mime_type="application/pdf",
            storage_backend=FakeStorageBackend(),
        )


async def test_upload_document_raises_when_too_large(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner3@example.com")
    project = await _make_project(db_session, owner)
    oversized = b"x" * (settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

    with pytest.raises(FileTooLargeError):
        await document_service.upload_document(
            db_session,
            project=project,
            task_id=None,
            uploader_id=owner.id,
            filename="big.pdf",
            file_bytes=oversized,
            mime_type="application/pdf",
            storage_backend=FakeStorageBackend(),
        )


async def test_upload_document_raises_for_unsupported_type(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner4@example.com")
    project = await _make_project(db_session, owner)

    with pytest.raises(UnsupportedFileTypeError):
        await document_service.upload_document(
            db_session,
            project=project,
            task_id=None,
            uploader_id=owner.id,
            filename="virus.exe",
            file_bytes=b"hello",
            mime_type="application/x-msdownload",
            storage_backend=FakeStorageBackend(),
        )


async def test_upload_document_raises_when_task_not_in_project(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "fsvc-owner5@example.com")
    project = await _make_project(db_session, owner)

    with pytest.raises(ParentTaskNotFoundError):
        await document_service.upload_document(
            db_session,
            project=project,
            task_id=owner.id,
            uploader_id=owner.id,
            filename="spec.pdf",
            file_bytes=b"hello",
            mime_type="application/pdf",
            storage_backend=FakeStorageBackend(),
        )


async def test_upload_document_succeeds_with_valid_task(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner6@example.com")
    project = await _make_project(db_session, owner)
    task = await task_service.create_task(
        db_session,
        project=project,
        title="Task",
        description=None,
        assignee_ids=[],
        parent_task_id=None,
        priority=TaskPriority.MEDIUM,
        labels=None,
        due_date=None,
        creator_id=owner.id,
    )

    document, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=task.task_id,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"hello",
        mime_type="application/pdf",
        storage_backend=FakeStorageBackend(),
    )

    assert document.task_id == task.task_id


async def test_delete_document_succeeds_for_uploader(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner7@example.com")
    project = await _make_project(db_session, owner)
    storage = FakeStorageBackend()
    document, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"hello",
        mime_type="application/pdf",
        storage_backend=storage,
    )
    membership = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=owner.id
    )

    storage_path = await document_service.delete_document(
        db_session,
        project=project,
        document_id=document.id,
        caller=membership,
    )

    assert storage_path == document.storage_path


async def test_delete_document_keeps_storage_while_a_dedup_sibling_remains(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "fsvc-owner-dedup-del@example.com")
    project = await _make_project(db_session, owner)
    storage = FakeStorageBackend()
    first, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="a.pdf",
        file_bytes=b"shared bytes",
        mime_type="application/pdf",
        storage_backend=storage,
    )
    second, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="b.pdf",
        file_bytes=b"shared bytes",
        mime_type="application/pdf",
        storage_backend=storage,
    )
    membership = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=owner.id
    )

    first_result = await document_service.delete_document(
        db_session, project=project, document_id=first.id, caller=membership
    )
    second_result = await document_service.delete_document(
        db_session, project=project, document_id=second.id, caller=membership
    )

    assert first_result is None
    assert second_result == second.storage_path


async def test_delete_document_raises_for_non_uploader_non_admin(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "fsvc-owner8@example.com")
    member = await _make_user(db_session, "fsvc-member8@example.com")
    project = await _make_project(db_session, owner)
    await organization_member_repository.add_member(
        db_session,
        org_id=project.org_id,
        user_id=member.id,
        role=OrganizationRole.MEMBER,
    )
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )
    document, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"hello",
        mime_type="application/pdf",
        storage_backend=FakeStorageBackend(),
    )
    member_row = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=member.id
    )

    with pytest.raises(NotDocumentUploaderError):
        await document_service.delete_document(
            db_session,
            project=project,
            document_id=document.id,
            caller=member_row,
        )


async def test_delete_document_succeeds_for_admin_even_if_not_uploader(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "fsvc-owner9@example.com")
    admin = await _make_user(db_session, "fsvc-admin9@example.com")
    project = await _make_project(db_session, owner)
    await organization_member_repository.add_member(
        db_session,
        org_id=project.org_id,
        user_id=admin.id,
        role=OrganizationRole.MEMBER,
    )
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=admin.id, role=ProjectRole.ADMIN
    )
    storage = FakeStorageBackend()
    document, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"hello",
        mime_type="application/pdf",
        storage_backend=storage,
    )
    admin_row = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=admin.id
    )

    storage_path = await document_service.delete_document(
        db_session,
        project=project,
        document_id=document.id,
        caller=admin_row,
    )

    assert storage_path == document.storage_path


async def test_delete_document_raises_when_not_found(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner10@example.com")
    project = await _make_project(db_session, owner)
    membership = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=owner.id
    )

    with pytest.raises(DocumentNotFoundError):
        await document_service.delete_document(
            db_session,
            project=project,
            document_id=owner.id,
            caller=membership,
        )


async def test_get_download_url_returns_backend_url(db_session: AsyncSession):
    owner = await _make_user(db_session, "fsvc-owner11@example.com")
    project = await _make_project(db_session, owner)
    storage = FakeStorageBackend()
    document, _ = await document_service.upload_document(
        db_session,
        project=project,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_bytes=b"hello",
        mime_type="application/pdf",
        storage_backend=storage,
    )

    result = await document_service.get_download_url(
        db_session,
        project_id=project.id,
        document_id=document.id,
        storage_backend=storage,
    )

    assert result.url == f"https://fake-storage.test/{document.storage_path}"


def test_resolve_download_token_round_trips():
    document_id = uuid7()
    token, _ = create_download_token({"document_id": str(document_id)})

    assert document_service.resolve_download_token(token) == document_id


def test_resolve_download_token_raises_for_garbage():
    with pytest.raises(InvalidDownloadTokenError):
        document_service.resolve_download_token("not-a-real-token")
