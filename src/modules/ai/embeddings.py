import asyncio

from google import genai
from google.genai import types

from core.config import settings
from modules.ai.models import EMBEDDING_DIM

_client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def _embed_batch_once(texts: list[str]) -> list[list[float]]:
    result = await _client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
    )
    return [embedding.values for embedding in result.embeddings]


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """One batched call for every chunk instead of one call per chunk —
    retries the whole batch once with a short backoff on failure, same
    reasoning as before: not worth a full retry framework for this."""
    if not texts:
        return []
    try:
        return await _embed_batch_once(texts)
    except Exception:
        await asyncio.sleep(2)
        return await _embed_batch_once(texts)
