from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

import modules.ai.retrieval as retrieval_module
from core.security import hash_password
from modules.ai.repositories import document_chunk_repository
from modules.ai.retrieval import retrieve_relevant_chunks
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.files.repositories import document_repository
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_repository

_CLOSE = [1.0] + [0.0] * 767
_FAR = [0.0, 1.0] + [0.0] * 766


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Retrieval",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(db_session: AsyncSession, owner_id):
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


async def _make_document_with_chunks(
    db_session: AsyncSession, *, project, uploader_id, chunks: list[tuple[str, list]]
):
    document_id = uuid7()
    await document_repository.create_document(
        db_session,
        id=document_id,
        org_id=project.org_id,
        project_id=project.id,
        task_id=None,
        uploader_id=uploader_id,
        filename="spec.txt",
        file_size=100,
        mime_type="text/plain",
        storage_path=f"{project.id}/{document_id}/spec.txt",
        content_hash=str(document_id),
    )
    await document_chunk_repository.create_chunks(
        db_session,
        document_id=document_id,
        chunks=[content for content, _ in chunks],
        embeddings=[embedding for _, embedding in chunks],
    )
    return document_id


async def test_retrieve_relevant_chunks_orders_by_similarity(
    db_session: AsyncSession, monkeypatch
):
    async def _query_embeds_as_close(texts: list[str]) -> list[list[float]]:
        return [_CLOSE for _ in texts]

    monkeypatch.setattr(retrieval_module, "get_embeddings", _query_embeds_as_close)
    owner = await _make_user(db_session, "retrieval-owner1@example.com")
    project = await _make_project(db_session, owner.id)
    await _make_document_with_chunks(
        db_session,
        project=project,
        uploader_id=owner.id,
        chunks=[("close match", _CLOSE), ("far match", _FAR)],
    )

    results = await retrieve_relevant_chunks(
        db_session, project_id=project.id, query="anything", top_k=5
    )

    assert [r.content for r in results] == ["close match", "far match"]


async def test_retrieve_relevant_chunks_respects_top_k(db_session: AsyncSession):
    owner = await _make_user(db_session, "retrieval-owner2@example.com")
    project = await _make_project(db_session, owner.id)
    await _make_document_with_chunks(
        db_session,
        project=project,
        uploader_id=owner.id,
        chunks=[(f"chunk {i}", _CLOSE) for i in range(3)],
    )

    results = await retrieve_relevant_chunks(
        db_session, project_id=project.id, query="anything", top_k=2
    )

    assert len(results) == 2


async def test_retrieve_relevant_chunks_never_leaks_another_project(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "retrieval-owner3@example.com")
    project_a = await _make_project(db_session, owner.id)
    project_b = await _make_project(db_session, owner.id)
    await _make_document_with_chunks(
        db_session,
        project=project_a,
        uploader_id=owner.id,
        chunks=[("project a content", _CLOSE)],
    )
    await _make_document_with_chunks(
        db_session,
        project=project_b,
        uploader_id=owner.id,
        chunks=[("project b content", _CLOSE)],
    )

    results = await retrieve_relevant_chunks(
        db_session, project_id=project_a.id, query="anything", top_k=5
    )

    assert [r.content for r in results] == ["project a content"]
