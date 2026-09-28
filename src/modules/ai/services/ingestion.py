from uuid import UUID

from loguru import logger

from core.database import async_session_factory
from modules.ai.chunking import chunk_text
from modules.ai.embeddings import get_embedding
from modules.ai.extraction import extract_text
from modules.ai.repositories import DocumentChunkRepository, document_chunk_repository
from modules.files.repositories import DocumentRepository, document_repository
from modules.files.storage import get_storage_backend


class IngestionService:
    def __init__(
        self, document_repo: DocumentRepository, chunk_repo: DocumentChunkRepository
    ) -> None:
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo

    async def ingest_document(self, *, document_id: UUID) -> None:
        """Runs as a FastAPI BackgroundTask, after the upload response is
        already sent — the request's session is gone by then, so this
        opens its own. Failures are logged, not raised — there's no
        caller left waiting to handle them."""
        async with async_session_factory() as session:
            try:
                document = await self.document_repo.get_by_id(session, document_id)
                if not document:
                    return

                file_bytes = await get_storage_backend().read(document.storage_path)
                text = extract_text(file_bytes=file_bytes, mime_type=document.mime_type)
                chunks = chunk_text(text)
                embeddings = [await get_embedding(chunk) for chunk in chunks]

                await self.chunk_repo.create_chunks(
                    session,
                    document_id=document.id,
                    chunks=chunks,
                    embeddings=embeddings,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception(f"Ingestion failed for document {document_id}")

    async def clone_or_ingest(
        self, *, document_id: UUID, source_document_id: UUID
    ) -> None:
        """A dedup upload shares another document's bytes — reuse its
        embeddings too when they're ready, instead of paying for Gemini
        again. Falls back to a normal ingest if the source has none yet
        (still processing, or its ingestion failed)."""
        async with async_session_factory() as session:
            try:
                source_chunks = await self.chunk_repo.get_all_by(
                    session, document_id=source_document_id
                )
                if source_chunks:
                    await self.chunk_repo.clone_chunks(
                        session, source_chunks=source_chunks, document_id=document_id
                    )
                    await session.commit()
                    return
            except Exception:
                await session.rollback()
                logger.exception(f"Chunk clone failed for document {document_id}")

        await self.ingest_document(document_id=document_id)


ingestion_service = IngestionService(
    document_repo=document_repository, chunk_repo=document_chunk_repository
)
