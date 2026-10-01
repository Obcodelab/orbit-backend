import asyncio
from collections.abc import AsyncIterator

from google import genai

from core.config import settings

_client = genai.Client(api_key=settings.GEMINI_API_KEY)

_SYSTEM_INSTRUCTION = (
    "You are a project assistant. Answer only using the provided context. "
    "If the context doesn't contain the answer, say so plainly rather than "
    "guessing or using outside knowledge."
)


def _build_prompt(*, question: str, context: str) -> str:
    return f"{_SYSTEM_INSTRUCTION}\n\nContext:\n{context}\n\nQuestion: {question}"


async def generate_answer(*, question: str, context: str) -> str:
    """Retries once with a short backoff on any failure — same reasoning
    as get_embeddings: not worth a full retry framework for one call.
    Goes through a fresh Chat per call (no history — we build our own
    prompt) since the SDK recommends that over calling Models directly."""
    prompt = _build_prompt(question=question, context=context)
    try:
        result = await _client.aio.chats.create(model=settings.CHAT_MODEL).send_message(
            prompt
        )
    except Exception:
        await asyncio.sleep(2)
        result = await _client.aio.chats.create(model=settings.CHAT_MODEL).send_message(
            prompt
        )
    return result.text


async def _start_stream(prompt: str):
    chat = _client.aio.chats.create(model=settings.CHAT_MODEL)
    return await chat.send_message_stream(prompt)


async def generate_answer_stream(*, question: str, context: str) -> AsyncIterator[str]:
    """Retries once if the stream fails before yielding anything (e.g. a
    transient 503) — safe since nothing's reached the caller yet. Once a
    chunk has been yielded, a failure just ends the stream instead;
    retrying then would duplicate output already delivered."""
    prompt = _build_prompt(question=question, context=context)
    stream = await _start_stream(prompt)
    started = False
    already_retried = False
    while True:
        try:
            chunk = await anext(stream)
        except StopAsyncIteration:
            return
        except Exception:
            if started:
                return
            if already_retried:
                raise
            already_retried = True
            await asyncio.sleep(2)
            stream = await _start_stream(prompt)
            continue
        started = True
        if chunk.text:
            yield chunk.text
