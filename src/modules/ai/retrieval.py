from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ai.embeddings import get_embeddings
from modules.ai.models import DocumentChunk
from modules.files.models import Document

# top_k alone always returns the "least bad" matches, even when nothing
# in the project is relevant. This cutoff (cosine distance; 1 = orthogonal)
# is an unvalidated starting point — tune against real queries later.
_MAX_RELEVANT_DISTANCE = 0.5


async def retrieve_relevant_chunks(
    session: AsyncSession, *, project_id: UUID, query: str, top_k: int = 5
) -> list[DocumentChunk]:
    """Project-scoped inside the query itself (JOIN + WHERE), not a
    post-filter on results — this is a security property: there's no
    filter step to accidentally skip, so a project's assistant can never
    surface another project's document content."""
    embeddings = await get_embeddings([query])
    if not embeddings:
        return []
    query_embedding = embeddings[0]

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.project_id == project_id, distance < _MAX_RELEVANT_DISTANCE)
        .order_by(distance)
        .limit(top_k)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
