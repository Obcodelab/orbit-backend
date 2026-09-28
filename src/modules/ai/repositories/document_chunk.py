from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from modules.ai.models import DocumentChunk


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def create_chunks(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if not chunks:
            return
        instances = [
            self.model(
                document_id=document_id,
                chunk_index=i,
                content=content,
                embedding=embedding,
            )
            for i, (content, embedding) in enumerate(
                zip(chunks, embeddings, strict=True)
            )
        ]
        await self.add_and_flush_instances(session, instances)

    async def clone_chunks(
        self,
        session: AsyncSession,
        *,
        source_chunks: list[DocumentChunk],
        document_id: UUID,
    ) -> None:
        instances = [
            self.model(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=chunk.embedding,
            )
            for chunk in source_chunks
        ]
        await self.add_and_flush_instances(session, instances)


document_chunk_repository = DocumentChunkRepository()
