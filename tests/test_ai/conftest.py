import pytest

import modules.ai.retrieval as retrieval_module
import modules.ai.services.assistant as assistant_module


@pytest.fixture(autouse=True)
def _fake_gemini(monkeypatch):
    """Fakes embeddings and chat so tests never hit the real Gemini API —
    patched at the name each caller imported it under (patching
    modules.ai.embeddings/chat directly wouldn't reach these, since each
    caller already bound its own reference via `from ... import ...`)."""

    async def _fake_get_embeddings(texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    async def _fake_generate_answer(*, question: str, context: str) -> str:
        return f"fake answer for: {question}"

    async def _fake_generate_answer_stream(*, question: str, context: str):
        for piece in ("fake ", "streamed ", "answer"):
            yield piece

    monkeypatch.setattr(retrieval_module, "get_embeddings", _fake_get_embeddings)
    monkeypatch.setattr(assistant_module, "generate_answer", _fake_generate_answer)
    monkeypatch.setattr(
        assistant_module, "generate_answer_stream", _fake_generate_answer_stream
    )
