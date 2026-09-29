import asyncio

from google import genai
from google.genai import types

from core.config import settings
from modules.ai.models import EMBEDDING_DIM

_client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def _embed_once(text: str) -> list[float]:
    result = await _client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
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
