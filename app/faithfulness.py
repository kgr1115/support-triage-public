"""Faithfulness scorer — clean-room implementation of the ragas faithfulness metric.

Two-step process collapsed into a single tool-use call:
1. Decompose the answer into atomic factual claims.
2. For each claim, judge whether it is supported by the provided context.

faithfulness = (# supported claims) / (# total claims).

We avoid the langchain/ragas dependency tree to keep the project lean — the metric
is small and inspecting our own prompt+rubric is more useful for a portfolio piece
than calling into a third-party scorer.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from app.schemas import KBArticle, Ticket

load_dotenv()

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

FAITHFULNESS_SYSTEM_PROMPT = """\
You verify whether a drafted support response is grounded. Your job is to
detect hallucinations — claims in the answer that are not supported by the
sources the agent had available.

The agent had two sources:
1. The customer's own ticket (subject + body) — claims that restate or
   paraphrase what the customer reported are supported by this source. The
   customer already knows what they wrote; the agent acknowledging it is fine.
2. KB articles — claims about how the product works, troubleshooting steps,
   policies, etc. must come from these.

Procedure:
1. Decompose the answer into atomic factual claims. Each claim states ONE fact.
2. For each claim, judge supported (the ticket OR the KB states / clearly
   implies it) or unsupported (neither source contains this fact, or they
   contradict it).

Rules:
- Generic politeness ("Sorry you're hitting this", "Let me know if I can help
  further") is NOT a factual claim — skip it.
- Citations themselves ("[KB-LOGIN-02]") are not claims — they reference the
  source. Judge the surrounding fact.
- Paraphrasing the customer's report is supported. Adding new specifics the
  customer did not mention is unsupported.
- Be strict on KB grounding: if the answer says "you can do X by clicking Y"
  and the KB only says "you can do X", the added detail "by clicking Y" is
  unsupported.
- An honest "the KB does not address this; let me escalate" is supported.

Output via the report_claims tool.
"""


CLAIMS_TOOL: dict[str, Any] = {
    "name": "report_claims",
    "description": "Report the decomposed claims from the answer and their grounding verdict.",
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The atomic claim, paraphrased for clarity.",
                        },
                        "supported": {
                            "type": "boolean",
                            "description": "True iff the context supports this claim.",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "One-sentence justification for the verdict.",
                        },
                    },
                    "required": ["text", "supported", "reasoning"],
                },
            }
        },
        "required": ["claims"],
    },
}


class Claim(BaseModel):
    text: str
    supported: bool
    reasoning: str


class FaithfulnessReport(BaseModel):
    """Per-answer report. ``score`` is supported / total, or 1.0 for an empty claim list."""

    answer: str
    claims: list[Claim]

    @property
    def score(self) -> float:
        if not self.claims:
            return 1.0
        return sum(1 for c in self.claims if c.supported) / len(self.claims)

    @property
    def n_supported(self) -> int:
        return sum(1 for c in self.claims if c.supported)

    @property
    def n_unsupported(self) -> int:
        return sum(1 for c in self.claims if not c.supported)


class FaithfulnessError(RuntimeError):
    pass


def _format_kb_context(articles: Sequence[KBArticle]) -> str:
    return "\n\n---\n\n".join(f"[{a.id}] {a.title}\n\n{a.body}" for a in articles)


def _format_ticket_context(ticket: Ticket) -> str:
    return f"Subject: {ticket.subject}\n\nBody: {ticket.body}"


async def score_faithfulness(
    answer: str,
    contexts: Sequence[KBArticle],
    *,
    ticket: Ticket | None = None,
    client: AsyncAnthropic | None = None,
    model: str = DEFAULT_MODEL,
) -> FaithfulnessReport:
    """Decompose ``answer`` into claims and verify each against ``ticket`` + ``contexts``.

    If ``ticket`` is provided, claims that paraphrase the customer's own report are
    counted as supported by the ticket. KB-grounding rules still apply to product
    facts.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise FaithfulnessError("ANTHROPIC_API_KEY is not set.")
        client = AsyncAnthropic(max_retries=8)

    parts = [f"ANSWER:\n{answer}"]
    if ticket is not None:
        parts.append(
            "CUSTOMER TICKET (claims paraphrasing this are supported):\n\n"
            f"{_format_ticket_context(ticket)}"
        )
    parts.append(
        "KB ARTICLES (the only product facts the answer may use):\n\n"
        f"{_format_kb_context(contexts)}"
    )
    user = "\n\n---\n\n".join(parts)

    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": FAITHFULNESS_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[CLAIMS_TOOL],
        tool_choice={"type": "tool", "name": "report_claims"},
        messages=[{"role": "user", "content": user}],
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "report_claims":
            claims = [Claim.model_validate(c) for c in block.input["claims"]]
            return FaithfulnessReport(answer=answer, claims=claims)

    raise FaithfulnessError(
        f"Model returned no report_claims tool_use block. stop_reason={response.stop_reason!r}"
    )
