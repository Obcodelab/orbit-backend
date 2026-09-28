import asyncio

from google import genai

from core.config import settings

_client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def _embed_once(text: str) -> list[float]:
    result = await _client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL, contents=text
    )
    return result.embeddings[0].values


async def get_embedding(text: str) -> list[float]:
    """Retries once with a short backoff on any failure — a full retry
    framework isn't worth it for a single external call inside a
    background task."""
    try:
        return await _embed_once(text)
    except Exception:
        await asyncio.sleep(2)
        return await _embed_once(text)
