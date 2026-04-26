"""Draft a citation-grounded support response from a ticket + retrieved KB articles.

The drafter is instructed to ONLY state facts present in the provided KB articles
and to cite each with ``[KB-ID]``. The faithfulness scorer (app/faithfulness.py)
then checks whether the response actually obeys that constraint.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from app.schemas import KBArticle, Ticket

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-4-6"

PERMISSIVE_DRAFTER_SYSTEM_PROMPT = """\
You are a B2B SaaS support agent drafting a reply to a customer ticket. The
customer has described a problem and we've attached some KB articles that
may be useful.

Be helpful and informative. Use the KB articles when they're relevant, but
feel free to add general advice and context from your own knowledge of how
similar products work. Keep the response professional and friendly.

Aim for 3–5 short paragraphs. End with a clear next step.
"""

DRAFTER_SYSTEM_PROMPT = """\
You are a B2B SaaS support agent drafting a reply to a customer ticket. The
customer has described a problem; you've been given KB articles that may or
may not address their issue.

RULES (non-negotiable):
1. Only state facts that appear in the provided KB articles or that paraphrase
   the customer's own report. Do NOT invent details, recall product knowledge
   from outside the articles, speculate about likely causes, or describe what
   internal teams will do.
2. Cite each product / process claim with the KB article ID in square brackets,
   e.g. [KB-LOGIN-02]. Place the citation immediately after the claim it
   supports. Paraphrasing the customer's own words does not need a citation.
3. If the provided KB articles do not address the customer's issue, say so
   honestly and ask for the specific information you would need next (e.g.
   "could you share the exact error message and the time it occurred?"). Do
   NOT promise that engineering will investigate, that you will pull logs,
   or that escalation will happen — those are decisions for the agent who
   reviews this draft, not for you to commit to.
4. Generic politeness ("Sorry you're hitting this", "Happy to help") is fine
   and does not need a citation. Only factual product / process claims need
   one.
5. No speculation. If KB-LOGIN-04 says "invite links expire after 72 hours by
   default" and the customer reports invites expiring immediately, you may
   say what the KB documents and ask the customer to verify their TTL setting
   — but do not guess that the cause is "likely a config issue", do not
   predict what the fix will be, and do not promise outcomes.

FORMAT:
- 3-5 short paragraphs.
- Plain language. No headers, no bullet lists unless the steps require them.
- End with a clear next step for the customer (a question they can answer or
  a setting they can check). Do not commit to actions on the agent's side.
- Do not include a name in the sign-off — keep it template-friendly.
"""


_CITATION_PATTERN = re.compile(r"\[(KB-[A-Z]+-\d+)\]")


def _extract_citations(text: str) -> list[str]:
    """Return unique cited KB IDs in order of first appearance."""
    seen: dict[str, None] = {}
    for match in _CITATION_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return list(seen.keys())


def _format_articles(articles: Sequence[KBArticle]) -> str:
    parts: list[str] = []
    for a in articles:
        parts.append(f"[{a.id}] {a.title}\n\n{a.body}")
    return "\n\n---\n\n".join(parts)


class DraftedResponse(BaseModel):
    """The drafter's output. ``cited_kb_ids`` is parsed from the response text."""

    ticket_id: str
    retrieved_kb_ids: list[str]
    response: str
    cited_kb_ids: list[str]


class DrafterError(RuntimeError):
    pass


async def draft_response(
    ticket: Ticket,
    articles: Sequence[KBArticle],
    *,
    client: AsyncAnthropic | None = None,
    model: str = DEFAULT_MODEL,
    system_prompt: str = DRAFTER_SYSTEM_PROMPT,
) -> DraftedResponse:
    """Draft a reply for ``ticket`` using ``articles`` as context.

    Defaults to the strict citation-grounded prompt. Pass
    ``system_prompt=PERMISSIVE_DRAFTER_SYSTEM_PROMPT`` to get the
    "be helpful, no grounding rules" baseline used by the eval contrast.
    """
    if not articles:
        raise DrafterError("draft_response requires at least one KB article as context.")
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise DrafterError("ANTHROPIC_API_KEY is not set.")
        client = AsyncAnthropic(max_retries=8)

    user_message = (
        "CUSTOMER TICKET\n"
        f"Subject: {ticket.subject}\n\n"
        f"Body: {ticket.body}\n\n"
        "---\n\n"
        "AVAILABLE KB ARTICLES:\n\n"
        f"{_format_articles(articles)}"
    )

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text
    if not text.strip():
        raise DrafterError(
            f"Model returned no text content. stop_reason={response.stop_reason!r}"
        )

    return DraftedResponse(
        ticket_id=ticket.id,
        retrieved_kb_ids=[a.id for a in articles],
        response=text,
        cited_kb_ids=_extract_citations(text),
    )
