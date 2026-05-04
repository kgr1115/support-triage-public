"""Multi-provider LLM layer (sift-robust pattern).

Wraps classifier + drafter behind a Provider interface so the /triage endpoint
can fall back from a primary to a secondary provider on transient errors
(rate-limit, overload, connection error). Provider used per call surfaces in
the API response so silent drift between providers is impossible.

Currently ships with two providers:
- AnthropicProvider — Sonnet 4.6 drafter, Haiku 4.5 classifier (the project's
  default; uses the existing app.classifier and app.drafter implementations).
- OpenAIProvider — gpt-4o drafter, gpt-4o-mini classifier (cost-matched fallback).

The faithfulness scorer (app.faithfulness) deliberately stays Anthropic-only —
keeping the eval scorer fixed preserves comparability of faithfulness numbers
across runs even when the drafting provider varies.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from typing import Protocol

from anthropic import (
    APIConnectionError as AnthropicAPIConnectionError,
)
from anthropic import (
    AsyncAnthropic,
)
from anthropic import (
    InternalServerError as AnthropicInternalServerError,
)
from anthropic import (
    RateLimitError as AnthropicRateLimitError,
)

from app import classifier as _anthropic_classifier
from app import drafter as _anthropic_drafter
from app.classifier import (
    CLASSIFY_SYSTEM_PROMPT,
    CLASSIFY_TOOL,
    ClassifierError,
    _build_user_message,
)
from app.drafter import (
    DRAFTER_SYSTEM_PROMPT,
    DraftedResponse,
    DrafterError,
    _extract_citations,
    _format_articles,
)
from app.schemas import Classification, KBArticle, Ticket

logger = logging.getLogger(__name__)


class Provider(Protocol):
    """Structural-typing interface for an LLM provider.

    A provider exposes ``classify`` and ``draft`` async methods that produce
    the same Pydantic shapes the existing classifier / drafter return. The
    ``name`` attribute is the short identifier surfaced in the API response
    via ``provider_used`` so callers can audit which provider answered.

    Forkers can inject their own providers (Cohere, Gemini, local model, etc.)
    by implementing this Protocol — no subclassing required.
    """

    name: str

    async def classify(self, ticket: Ticket) -> Classification: ...

    async def draft(
        self,
        ticket: Ticket,
        articles: Sequence[KBArticle],
        *,
        system_prompt: str = DRAFTER_SYSTEM_PROMPT,
    ) -> DraftedResponse: ...


# ----- Anthropic -----------------------------------------------------------


class AnthropicProvider:
    """Provider implementation backed by Anthropic.

    Delegates to the existing ``app.classifier`` and ``app.drafter`` modules so
    the canonical Anthropic logic lives in exactly one place.
    """

    name = "anthropic"

    def __init__(
        self,
        client: AsyncAnthropic | None = None,
        *,
        classifier_model: str = _anthropic_classifier.DEFAULT_MODEL,
        drafter_model: str = _anthropic_drafter.DEFAULT_MODEL,
    ) -> None:
        self._client = client
        self.classifier_model = classifier_model
        self.drafter_model = drafter_model

    async def classify(self, ticket: Ticket) -> Classification:
        return await _anthropic_classifier.classify(
            ticket, client=self._client, model=self.classifier_model
        )

    async def draft(
        self,
        ticket: Ticket,
        articles: Sequence[KBArticle],
        *,
        system_prompt: str = DRAFTER_SYSTEM_PROMPT,
    ) -> DraftedResponse:
        return await _anthropic_drafter.draft_response(
            ticket,
            articles,
            client=self._client,
            model=self.drafter_model,
            system_prompt=system_prompt,
        )


# ----- OpenAI --------------------------------------------------------------

# OpenAI errors are imported lazily so the openai package is not required at
# import time — forkers who never use the OpenAI provider don't need it
# installed. The imports happen inside __init__ and method calls.


class OpenAIProvider:
    """Provider implementation backed by OpenAI.

    Mirrors the Anthropic provider's behavior using OpenAI's tool-calling for
    classification and plain chat completion for drafting. Default models
    (gpt-4o-mini for classify, gpt-4o for draft) are cost-matched against the
    Anthropic defaults (Haiku 4.5 / Sonnet 4.6).
    """

    name = "openai"

    def __init__(
        self,
        client=None,  # AsyncOpenAI | None — typed loosely so import stays lazy
        *,
        classifier_model: str = "gpt-4o-mini",
        drafter_model: str = "gpt-4o",
    ) -> None:
        if client is None:
            from openai import AsyncOpenAI

            if not os.environ.get("OPENAI_API_KEY"):
                raise RuntimeError(
                    "OPENAI_API_KEY is not set — required to construct OpenAIProvider "
                    "without an explicit client."
                )
            client = AsyncOpenAI(max_retries=8)
        self._client = client
        self.classifier_model = classifier_model
        self.drafter_model = drafter_model

    async def classify(self, ticket: Ticket) -> Classification:
        response = await self._client.chat.completions.create(
            model=self.classifier_model,
            max_tokens=256,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(ticket)},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": CLASSIFY_TOOL["name"],
                        "description": CLASSIFY_TOOL["description"],
                        "parameters": CLASSIFY_TOOL["input_schema"],
                    },
                }
            ],
            tool_choice={
                "type": "function",
                "function": {"name": CLASSIFY_TOOL["name"]},
            },
        )

        message = response.choices[0].message
        if not message.tool_calls:
            raise ClassifierError(
                f"OpenAI returned no tool_calls. finish_reason="
                f"{response.choices[0].finish_reason!r}"
            )
        args = json.loads(message.tool_calls[0].function.arguments)
        return Classification.model_validate(args)

    async def draft(
        self,
        ticket: Ticket,
        articles: Sequence[KBArticle],
        *,
        system_prompt: str = DRAFTER_SYSTEM_PROMPT,
    ) -> DraftedResponse:
        if not articles:
            raise DrafterError("draft requires at least one KB article as context.")
        user_message = (
            "CUSTOMER TICKET\n"
            f"Subject: {ticket.subject}\n\n"
            f"Body: {ticket.body}\n\n"
            "---\n\n"
            "AVAILABLE KB ARTICLES:\n\n"
            f"{_format_articles(articles)}"
        )
        response = await self._client.chat.completions.create(
            model=self.drafter_model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        text = response.choices[0].message.content or ""
        if not text.strip():
            raise DrafterError(
                f"OpenAI returned no text content. finish_reason="
                f"{response.choices[0].finish_reason!r}"
            )
        return DraftedResponse(
            ticket_id=ticket.id,
            retrieved_kb_ids=[a.id for a in articles],
            response=text,
            cited_kb_ids=_extract_citations(text),
        )


# ----- Sift-robust orchestrator --------------------------------------------


def _transient_error_types() -> tuple[type[Exception], ...]:
    """Errors that should trigger fallback to the secondary provider.

    Anthropic's RateLimitError, APIConnectionError, and InternalServerError are
    transient (rate-limited, network blip, overload). The OpenAI equivalents
    are imported lazily so the openai package is optional. Auth errors are
    deliberately NOT in this set — they're configuration bugs, not failover
    candidates, and silently falling back hides them.
    """
    types: list[type[Exception]] = [
        AnthropicRateLimitError,
        AnthropicAPIConnectionError,
        AnthropicInternalServerError,
    ]
    try:
        from openai import APIConnectionError as OpenAIAPIConnectionError
        from openai import InternalServerError as OpenAIInternalServerError
        from openai import RateLimitError as OpenAIRateLimitError

        types.extend(
            [OpenAIRateLimitError, OpenAIAPIConnectionError, OpenAIInternalServerError]
        )
    except ImportError:
        pass
    return tuple(types)


class SiftRobustOrchestrator:
    """Wraps a primary provider with optional secondary fallback.

    On transient errors (rate-limit, overload, connection error) from the
    primary, the secondary is tried. Auth and other config errors propagate
    immediately — those are bugs, not failover candidates.

    If ``secondary`` is ``None``, the orchestrator runs primary-only and any
    error from the primary propagates to the caller.

    Returns ``(result, provider_name)`` tuples so callers can surface which
    provider answered each call.
    """

    def __init__(self, primary: Provider, secondary: Provider | None = None) -> None:
        self.primary = primary
        self.secondary = secondary

    async def classify(self, ticket: Ticket) -> tuple[Classification, str]:
        try:
            return await self.primary.classify(ticket), self.primary.name
        except _transient_error_types() as exc:
            if self.secondary is None:
                raise
            logger.warning(
                "primary provider %s failed (%s); falling back to %s",
                self.primary.name,
                type(exc).__name__,
                self.secondary.name,
            )
            return await self.secondary.classify(ticket), self.secondary.name

    async def draft(
        self,
        ticket: Ticket,
        articles: Sequence[KBArticle],
        *,
        system_prompt: str = DRAFTER_SYSTEM_PROMPT,
    ) -> tuple[DraftedResponse, str]:
        try:
            return (
                await self.primary.draft(ticket, articles, system_prompt=system_prompt),
                self.primary.name,
            )
        except _transient_error_types() as exc:
            if self.secondary is None:
                raise
            logger.warning(
                "primary provider %s failed (%s); falling back to %s",
                self.primary.name,
                type(exc).__name__,
                self.secondary.name,
            )
            return (
                await self.secondary.draft(
                    ticket, articles, system_prompt=system_prompt
                ),
                self.secondary.name,
            )


def build_default_orchestrator() -> SiftRobustOrchestrator:
    """Construct the orchestrator the /triage endpoint uses by default.

    Anthropic primary; OpenAI secondary IF ``OPENAI_API_KEY`` is set in the
    environment. If the OpenAI key is absent, runs primary-only and logs a
    warning at startup — forkers without an OpenAI account can still use the
    tool, they just don't get fallback.
    """
    primary = AnthropicProvider()
    if os.environ.get("OPENAI_API_KEY"):
        try:
            secondary: Provider | None = OpenAIProvider()
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "OPENAI_API_KEY is set but OpenAIProvider construction failed: %s. "
                "Running primary-only.",
                exc,
            )
            secondary = None
    else:
        logger.warning(
            "sift-robust fallback unavailable; OPENAI_API_KEY is not set. "
            "Running with Anthropic primary only."
        )
        secondary = None
    return SiftRobustOrchestrator(primary, secondary)
