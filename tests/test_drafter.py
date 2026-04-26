"""Mocked unit tests for the drafter — no real API calls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.drafter import DrafterError, _extract_citations, draft_response
from app.schemas import Category, KBArticle, Priority, Sentiment, Ticket


def _ticket() -> Ticket:
    return Ticket(
        id="t-001",
        subject="Can't log in after 2FA",
        body="Recovery codes don't work either.",
        priority=Priority.HIGH,
        category=Category.LOGIN,
        sentiment=Sentiment.NEGATIVE,
        relevant_kb_ids=["KB-LOGIN-02"],
    )


def _articles() -> list[KBArticle]:
    return [
        KBArticle(
            id="KB-LOGIN-02",
            title="2FA recovery",
            body="If recovery codes don't work, an admin can disable 2FA.",
            categories=[Category.LOGIN],
        )
    ]


def _mock_text(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason="end_turn")


def test_extract_citations_finds_unique_kb_ids() -> None:
    text = (
        "An admin on your account can disable 2FA [KB-LOGIN-02]. "
        "If you've also lost access to email, see [KB-LOGIN-03]. "
        "[KB-LOGIN-02] handles the recovery code case."
    )
    assert _extract_citations(text) == ["KB-LOGIN-02", "KB-LOGIN-03"]


def test_draft_response_parses_text_and_citations() -> None:
    client = AsyncMock()
    client.messages.create.return_value = _mock_text(
        "Sorry to hear you're locked out. Per [KB-LOGIN-02], an admin can disable 2FA. "
        "Could you ask an admin and let us know if that resolves it?"
    )
    drafted = asyncio.run(draft_response(_ticket(), _articles(), client=client))

    assert drafted.ticket_id == "t-001"
    assert "[KB-LOGIN-02]" in drafted.response
    assert drafted.cited_kb_ids == ["KB-LOGIN-02"]
    assert drafted.retrieved_kb_ids == ["KB-LOGIN-02"]


def test_draft_response_rejects_empty_articles() -> None:
    client = AsyncMock()
    with pytest.raises(DrafterError):
        asyncio.run(draft_response(_ticket(), [], client=client))


def test_draft_response_passes_cached_system_prompt() -> None:
    client = AsyncMock()
    client.messages.create.return_value = _mock_text("Reply.")
    asyncio.run(draft_response(_ticket(), _articles(), client=client))

    kwargs = client.messages.create.call_args.kwargs
    system = kwargs["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_draft_response_raises_on_empty_text() -> None:
    """If the model returns no text content, DrafterError fires."""
    client = AsyncMock()
    client.messages.create.return_value = SimpleNamespace(content=[], stop_reason="end_turn")
    with pytest.raises(DrafterError):
        asyncio.run(draft_response(_ticket(), _articles(), client=client))
