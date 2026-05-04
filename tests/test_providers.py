"""Tests for the sift-robust multi-provider layer.

Covers (per the architect-approved proposal sift-robust-multi-provider-2026-05-04):

1. AnthropicProvider.classify returns Classification (mock client)
2. AnthropicProvider.draft returns DraftedResponse (mock client)
3. OpenAIProvider.classify returns Classification (mock client)
4. OpenAIProvider.draft returns DraftedResponse (mock client)
5. SiftRobustOrchestrator: primary success returns (result, primary.name)
6. SiftRobustOrchestrator: falls back on RateLimitError
7. SiftRobustOrchestrator: falls back on APIConnectionError
8. SiftRobustOrchestrator: falls back on InternalServerError (overload)
9. SiftRobustOrchestrator: does NOT fall back on auth errors

Plus a couple of supporting cases (no secondary, both providers fail).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from anthropic import APIConnectionError as AnthropicAPIConnectionError
from anthropic import (
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)

from app.providers import (
    AnthropicProvider,
    OpenAIProvider,
    SiftRobustOrchestrator,
)
from app.schemas import Category, Classification, KBArticle, Priority, Sentiment, Ticket


def _ticket() -> Ticket:
    return Ticket(
        id="t-providers-1",
        subject="SSO redirect loop after cert rotation",
        body="Half our team gets bounced back to Okta after we rotated certs.",
        priority=Priority.HIGH,
        category=Category.LOGIN,
        sentiment=Sentiment.NEGATIVE,
    )


def _articles() -> list[KBArticle]:
    return [
        KBArticle(
            id="KB-LOGIN-01",
            title="SSO troubleshooting",
            body="If users hit a redirect loop after IdP cert rotation, re-upload the cert.",
            categories=[Category.LOGIN],
        )
    ]


def _httpx_response(status: int = 429) -> httpx.Response:
    """Build a real httpx.Response for use with anthropic exception types."""
    return httpx.Response(
        status_code=status,
        request=httpx.Request("POST", "https://api.test/v1/messages"),
    )


def _anthropic_classify_response(tool_input: dict) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name="classify_ticket", input=tool_input)
    return SimpleNamespace(content=[block], stop_reason="tool_use")


def _anthropic_text_response(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason="end_turn")


def _openai_tool_response(args: dict) -> SimpleNamespace:
    """Mimic the shape of an OpenAI ChatCompletion with a tool_call."""
    tool_call = SimpleNamespace(
        function=SimpleNamespace(name="classify_ticket", arguments=json.dumps(args))
    )
    message = SimpleNamespace(tool_calls=[tool_call], content=None)
    choice = SimpleNamespace(message=message, finish_reason="tool_calls")
    return SimpleNamespace(choices=[choice])


def _openai_text_response(text: str) -> SimpleNamespace:
    message = SimpleNamespace(tool_calls=None, content=text)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(choices=[choice])


# --- 1. AnthropicProvider.classify ---------------------------------------


def test_anthropic_provider_classify_returns_classification() -> None:
    client = AsyncMock()
    client.messages.create.return_value = _anthropic_classify_response(
        {"priority": "high", "category": "login_issue", "sentiment": "negative"}
    )
    provider = AnthropicProvider(client=client)
    result = asyncio.run(provider.classify(_ticket()))
    assert isinstance(result, Classification)
    assert result.priority == Priority.HIGH
    assert result.category == Category.LOGIN


# --- 2. AnthropicProvider.draft ------------------------------------------


def test_anthropic_provider_draft_returns_drafted_response() -> None:
    client = AsyncMock()
    client.messages.create.return_value = _anthropic_text_response(
        "Per [KB-LOGIN-01], re-upload the cert and ask affected users to clear cookies."
    )
    provider = AnthropicProvider(client=client)
    drafted = asyncio.run(provider.draft(_ticket(), _articles()))
    assert drafted.cited_kb_ids == ["KB-LOGIN-01"]


# --- 3. OpenAIProvider.classify ------------------------------------------


def test_openai_provider_classify_returns_classification() -> None:
    client = AsyncMock()
    client.chat.completions.create.return_value = _openai_tool_response(
        {"priority": "high", "category": "login_issue", "sentiment": "negative"}
    )
    provider = OpenAIProvider(client=client)
    result = asyncio.run(provider.classify(_ticket()))
    assert isinstance(result, Classification)
    assert result.priority == Priority.HIGH
    assert result.category == Category.LOGIN


# --- 4. OpenAIProvider.draft ---------------------------------------------


def test_openai_provider_draft_returns_drafted_response() -> None:
    client = AsyncMock()
    client.chat.completions.create.return_value = _openai_text_response(
        "Sorry about the redirect loop. Per [KB-LOGIN-01], re-upload the rotated cert."
    )
    provider = OpenAIProvider(client=client)
    drafted = asyncio.run(provider.draft(_ticket(), _articles()))
    assert drafted.cited_kb_ids == ["KB-LOGIN-01"]


# --- 5. Orchestrator: primary success ------------------------------------


def test_orchestrator_primary_success_returns_primary_name() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.return_value = Classification(
        priority=Priority.HIGH, category=Category.LOGIN, sentiment=Sentiment.NEGATIVE
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    result, name = asyncio.run(orch.classify(_ticket()))

    assert name == "anthropic"
    secondary.classify.assert_not_awaited()
    assert isinstance(result, Classification)


# --- 6. Orchestrator: fallback on RateLimitError -------------------------


def test_orchestrator_falls_back_on_rate_limit_error() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.side_effect = RateLimitError(
        message="rate limited",
        response=_httpx_response(429),
        body={},
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    secondary.classify.return_value = Classification(
        priority=Priority.NORMAL, category=Category.LOGIN, sentiment=Sentiment.NEUTRAL
    )
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    result, name = asyncio.run(orch.classify(_ticket()))

    assert name == "openai"
    secondary.classify.assert_awaited_once()
    assert result.priority == Priority.NORMAL


# --- 7. Orchestrator: fallback on APIConnectionError ---------------------


def test_orchestrator_falls_back_on_connection_error() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.side_effect = AnthropicAPIConnectionError(
        request=httpx.Request("POST", "https://api.test/v1/messages"),
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    secondary.classify.return_value = Classification(
        priority=Priority.LOW, category=Category.FEATURE_REQUEST, sentiment=Sentiment.POSITIVE
    )
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    result, name = asyncio.run(orch.classify(_ticket()))

    assert name == "openai"
    assert result.category == Category.FEATURE_REQUEST


# --- 8. Orchestrator: fallback on InternalServerError (overload) ---------


def test_orchestrator_falls_back_on_internal_server_error() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.side_effect = InternalServerError(
        message="overloaded",
        response=_httpx_response(503),
        body={},
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    secondary.classify.return_value = Classification(
        priority=Priority.URGENT, category=Category.BUG_REPORT, sentiment=Sentiment.FRUSTRATED
    )
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    result, name = asyncio.run(orch.classify(_ticket()))

    assert name == "openai"
    assert result.priority == Priority.URGENT


# --- 9. Orchestrator: does NOT fall back on auth errors ------------------


def test_orchestrator_does_not_fall_back_on_auth_error() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.side_effect = AuthenticationError(
        message="bad api key",
        response=_httpx_response(401),
        body={},
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    with pytest.raises(AuthenticationError):
        asyncio.run(orch.classify(_ticket()))

    secondary.classify.assert_not_awaited()


# --- Supporting: no secondary ---------------------------------------------


def test_orchestrator_no_secondary_propagates_primary_error() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.side_effect = RateLimitError(
        message="rate limited",
        response=_httpx_response(429),
        body={},
    )
    orch = SiftRobustOrchestrator(primary=primary, secondary=None)

    with pytest.raises(RateLimitError):
        asyncio.run(orch.classify(_ticket()))


# --- Supporting: both providers fail --------------------------------------


def test_orchestrator_both_providers_fail_propagates_secondary_error() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.classify.side_effect = RateLimitError(
        message="rate limited",
        response=_httpx_response(429),
        body={},
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    secondary.classify.side_effect = ValueError("openai exploded")
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    with pytest.raises(ValueError, match="openai exploded"):
        asyncio.run(orch.classify(_ticket()))


# --- Draft path: orchestrator falls back the same way ---------------------


def test_orchestrator_draft_falls_back_on_rate_limit() -> None:
    primary = AsyncMock()
    primary.name = "anthropic"
    primary.draft.side_effect = RateLimitError(
        message="rate limited",
        response=_httpx_response(429),
        body={},
    )
    from app.drafter import DraftedResponse

    fallback_drafted = DraftedResponse(
        ticket_id="t-providers-1",
        retrieved_kb_ids=["KB-LOGIN-01"],
        response="Fallback says: per [KB-LOGIN-01], re-upload the cert.",
        cited_kb_ids=["KB-LOGIN-01"],
    )
    secondary = AsyncMock()
    secondary.name = "openai"
    secondary.draft.return_value = fallback_drafted
    orch = SiftRobustOrchestrator(primary=primary, secondary=secondary)

    result, name = asyncio.run(orch.draft(_ticket(), _articles()))

    assert name == "openai"
    assert result.cited_kb_ids == ["KB-LOGIN-01"]
