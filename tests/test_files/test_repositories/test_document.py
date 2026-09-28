from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.files.repositories import document_repository
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(db_session: AsyncSession, owner_id) -> object:
    org = await organization_repository.create_organization(
        db_session, name="Test Org", owner_id=owner_id
    )
    return await project_repository.create_project(
        db_session,
        org_id=org.id,
        key="ORB",
        name="Orbit",
        description=None,
        owner_id=owner_id,
    )


async def test_create_document_sets_fields(db_session: AsyncSession):
    owner = await _make_user(db_session, "drepo-owner1@example.com")
    project = await _make_project(db_session, owner.id)

    document = await document_repository.create_document(
        db_session,
        id=uuid7(),
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_size=1024,
        mime_type="application/pdf",
        storage_path=f"{project.id}/spec.pdf",
        content_hash="a" * 64,
    )

    assert document.filename == "spec.pdf"
    assert document.project_id == project.id
    assert document.task_id is None


async def test_get_scoped_returns_none_for_wrong_project(db_session: AsyncSession):
    owner = await _make_user(db_session, "drepo-owner2@example.com")
    project_a = await _make_project(db_session, owner.id)
    project_b = await _make_project(db_session, owner.id)
    document = await document_repository.create_document(
        db_session,
        id=uuid7(),
        org_id=project_a.org_id,
        project_id=project_a.id,
        task_id=None,
        uploader_id=owner.id,
        filename="spec.pdf",
        file_size=1024,
        mime_type="application/pdf",
        storage_path=f"{project_a.id}/spec.pdf",
        content_hash="b" * 64,
    )

    result = await document_repository.get_scoped(
        db_session, project_id=project_b.id, document_id=document.id
    )

    assert result is None


async def test_get_for_project_paginates_and_counts(db_session: AsyncSession):
    owner = await _make_user(db_session, "drepo-owner3@example.com")
    project = await _make_project(db_session, owner.id)
    for i in range(2):
        await document_repository.create_document(
            db_session,
            id=uuid7(),
            org_id=project.org_id,
            project_id=project.id,
            task_id=None,
            uploader_id=owner.id,
            filename=f"doc{i}.pdf",
            file_size=1024,
            mime_type="application/pdf",
            storage_path=f"{project.id}/doc{i}.pdf",
            content_hash=f"{i}" * 64,
        )

    documents, total = await document_repository.get_for_project(
        db_session, project_id=project.id, order=None, limit=20, offset=0
    )

    assert total == 2
    assert len(documents) == 2


async def test_get_one_by_content_hash_returns_any_match(db_session: AsyncSession):
    owner = await _make_user(db_session, "drepo-owner4@example.com")
    project = await _make_project(db_session, owner.id)
    await document_repository.create_document(
        db_session,
        id=uuid7(),
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=owner.id,
        filename="a.pdf",
        file_size=5,
        mime_type="application/pdf",
        storage_path=f"{project.id}/a.pdf",
        content_hash="c" * 64,
    )
    await document_repository.create_document(
        db_session,
        id=uuid7(),
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=owner.id,
        filename="b.pdf",
        file_size=5,
        mime_type="application/pdf",
        storage_path=f"{project.id}/a.pdf",
        content_hash="c" * 64,
    )

    result = await document_repository.get_one_by_content_hash(
        db_session, project_id=project.id, content_hash="c" * 64
    )

    assert result is not None
    assert result.content_hash == "c" * 64


async def test_count_by_storage_path_excludes_self(db_session: AsyncSession):
    owner = await _make_user(db_session, "drepo-owner5@example.com")
    project = await _make_project(db_session, owner.id)
    shared_path = f"{project.id}/shared.pdf"
    first = await document_repository.create_document(
        db_session,
        id=uuid7(),
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=owner.id,
        filename="a.pdf",
        file_size=5,
        mime_type="application/pdf",
        storage_path=shared_path,
        content_hash="d" * 64,
    )
    second = await document_repository.create_document(
        db_session,
        id=uuid7(),
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=owner.id,
        filename="b.pdf",
        file_size=5,
        mime_type="application/pdf",
        storage_path=shared_path,
        content_hash="d" * 64,
    )

    assert (
        await document_repository.count_by_storage_path(
            db_session, storage_path=shared_path, exclude_id=first.id
        )
        == 1
    )
    await document_repository.delete_by_id(db_session, second.id)
    assert (
        await document_repository.count_by_storage_path(
            db_session, storage_path=shared_path, exclude_id=first.id
        )
        == 0
    )
