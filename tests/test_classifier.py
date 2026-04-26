"""Mocked unit tests for the classifier — no real API calls.

The eval script exercises the live API against the labeled fixtures. These tests cover
the parsing / error paths so they're fast, deterministic, and don't burn tokens.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.classifier import CLASSIFY_TOOL, ClassifierError, classify
from app.schemas import Category, Classification, Priority, Sentiment, Ticket


def _ticket() -> Ticket:
    return Ticket(
        id="test-001",
        subject="Can't log in after 2FA reset",
        body="Recovery codes don't work either. Locked out.",
        priority=Priority.HIGH,
        category=Category.LOGIN,
        sentiment=Sentiment.FRUSTRATED,
    )


def _mock_response(tool_input: dict) -> SimpleNamespace:
    """Mimic the shape of an anthropic Message with one tool_use block."""
    block = SimpleNamespace(type="tool_use", name="classify_ticket", input=tool_input)
    return SimpleNamespace(content=[block], stop_reason="tool_use")


def test_classify_parses_tool_use_block() -> None:
    client = AsyncMock()
    client.messages.create.return_value = _mock_response(
        {"priority": "high", "category": "login_issue", "sentiment": "frustrated"}
    )

    result: Classification = asyncio.run(classify(_ticket(), client=client))

    assert result.priority == Priority.HIGH
    assert result.category == Category.LOGIN
    assert result.sentiment == Sentiment.FRUSTRATED


def test_classify_raises_when_no_tool_use_block() -> None:
    client = AsyncMock()
    text_only = SimpleNamespace(type="text", text="I refuse to use the tool.")
    client.messages.create.return_value = SimpleNamespace(
        content=[text_only], stop_reason="end_turn"
    )

    with pytest.raises(ClassifierError):
        asyncio.run(classify(_ticket(), client=client))


def test_classify_passes_cached_system_prompt() -> None:
    """System block must carry cache_control so the eval's 200 calls share one cache entry."""
    client = AsyncMock()
    client.messages.create.return_value = _mock_response(
        {"priority": "low", "category": "feature_request", "sentiment": "neutral"}
    )

    asyncio.run(classify(_ticket(), client=client))

    call_kwargs = client.messages.create.call_args.kwargs
    system = call_kwargs["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "classify_ticket"}


def test_classify_tool_schema_uses_full_enum_sets() -> None:
    """Sanity: the tool's enum lists must match the Pydantic enums or the model can label
    invalidly. Drift here silently breaks classification accuracy."""
    props = CLASSIFY_TOOL["input_schema"]["properties"]
    assert set(props["priority"]["enum"]) == {p.value for p in Priority}
    assert set(props["category"]["enum"]) == {c.value for c in Category}
    assert set(props["sentiment"]["enum"]) == {s.value for s in Sentiment}
