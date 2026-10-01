class ConversationNotFoundError(Exception):
    """No conversation exists with this id in this project."""


class AssistantUnavailableError(Exception):
    """Retrieval or generation failed even after their built-in retry —
    Gemini is down, overloaded, or the quota's exhausted."""
