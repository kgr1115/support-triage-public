"""Ticket classifier: priority + category + sentiment via Anthropic tool use.

Design notes:
- Tool use (forced ``tool_choice``) gives schema-strict output without parsing free text.
- The system prompt is marked ``cache_control: ephemeral`` so the eval's 200 calls share
  one cache entry — only the first call pays full input cost.
- Haiku 4.5 by default: classification is light, latency-sensitive, and Haiku-class
  models hit accuracy ceilings that match larger models on tasks with crisp label sets.
"""

from __future__ import annotations

import os
from typing import Any

from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from app.schemas import Category, Classification, Priority, Sentiment, Ticket

load_dotenv()

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

CLASSIFY_SYSTEM_PROMPT = """\
You classify B2B SaaS support tickets along three dimensions: priority, category,
sentiment.

PRIORITY (severity × urgency — calibrate carefully; do NOT over-rate):
- urgent: many users blocked, data integrity at risk, money mis-charged and not yet
  refunded, or "right now" outage language. Multi-user impact OR time-sensitive
  ("need this resolved today", "before our audit", "blocking our nightly sync").
- high: significant impact on ONE user or one workflow — single user can't log in,
  one webhook integration stopped firing, one charge is wrong, mobile app crashes
  for one user. Needs same-business-day action.
- normal: routine support — productivity annoyance, has a workaround, intermittent,
  cosmetic data issues, missing-but-recoverable artifacts. The customer is
  inconvenienced, NOT stopped.
- low: nice-to-have, no time pressure — wishlist features, cosmetic UI requests,
  administrative changes (update billing address), questions for clarification.

CRITICAL CALIBRATION RULES — read before labeling priority:
1. Most tickets are normal. If you find yourself labeling more than ~30% as high
   or urgent, recalibrate.
2. "Doesn't work" is not automatically high. Ask: is the user blocked from doing
   their job, or just inconvenienced? If they have a workaround or the issue is
   intermittent, it is normal.
3. Login issues are NOT automatically high. A session that expires more often than
   expected is normal. A magic link cycling back is normal (the user can use
   password). Only label login as high when the user is genuinely locked out of
   their account.
4. Reserve urgent for multi-user impact, data/money loss, or explicit "blocking
   the whole team" + "need this today" language. Single-user issues are at most
   high.

CATEGORY (the underlying issue type):
- login_issue: anything blocking authentication — SSO, MFA, password reset,
  sessions, account lockout, invite links.
- billing_dispute: invoice / charge / refund / tax / billing-portal issues.
- integration_setup: configuring or operating connectivity to third-party systems
  — APIs, webhooks, OAuth, connectors, field mapping. Use this when the customer
  is setting up an integration OR when an integration's configuration is
  misbehaving (sync drops fields, OAuth flow stuck, signature verification flaky).
- feature_request: customer asks for something the product doesn't currently do —
  wishlist, "would love to see", suggestions, "could you add".
- bug_report: customer reports an existing in-product feature behaving incorrectly
  in the PRODUCT ITSELF — wrong dashboard totals, broken UI, regressions, data
  integrity defects in core product logic (not in an integration).

SENTIMENT (emotional tone — distinguish negative from frustrated carefully):
- positive: appreciative, optimistic, future-looking. "Love your product",
  "would love this feature", "happy to share our use case".
- neutral: matter-of-fact, technical, informational. The customer is reporting
  facts without emotional content. "We were charged X but expected Y", "Logs
  show Z", "Repro: 1) ... 2) ... 3) ...".
- negative: dissatisfied but professional. "Doesn't work", "looks wrong", "can
  someone help", a single complaint without escalation language.
- frustrated: explicitly escalated — repeated incidents ("this is the third time",
  "tried multiple times"), urgency-of-frustration language ("blocking my whole
  team", "need this resolved today"), or repeated-failure pattern descriptions.
  Reserve for the strongest tone.

CRITICAL CALIBRATION RULES — read before labeling sentiment:
- Most dissatisfied tickets are negative, not frustrated. Frustrated requires
  explicit escalation language or a pattern of repeated failure.
- A reproducible bug report with calm "repro steps" language is negative or
  neutral, not frustrated, even if the bug is severe.
- Technical incident descriptions without emotional content are neutral, not
  negative, even if the underlying issue is bad.

EXAMPLES (study the reasoning, not just the labels):

EX1 — normal (NOT high):
  Subject: "Session expires every 5 minutes — was hourly before"
  Body: "...my session terminates after about 5 minutes of activity. Other team
  members on the same plan aren't seeing this..."
  Reasoning: one user, productivity annoyance, has workaround (re-login), calm
  factual tone. Annoying, not blocking.
  Labels: {priority: normal, category: login_issue, sentiment: negative}

EX2 — urgent + frustrated (multi-user + escalation):
  Subject: "Locked out after enabling 2FA — recovery codes don't work"
  Body: "I enabled 2FA last week and now I'm locked out... blocking my whole team
  (75 people on the Pro plan). Need this resolved today."
  Reasoning: multi-user impact + time-sensitive demand + explicit pressure.
  Labels: {priority: urgent, category: login_issue, sentiment: frustrated}

EX3 — high + negative (single user blocked, calm):
  Subject: "MFA codes never arrive on my phone"
  Body: "MFA codes aren't reaching my phone. I've waited 10+ minutes and
  refreshed. This started after I switched carriers last week."
  Reasoning: one user blocked from login, professional tone, no escalation.
  Labels: {priority: high, category: login_issue, sentiment: negative}

EX4 — low + positive (wishlist, no blocking):
  Subject: "Dark mode for the admin panel"
  Body: "Wishlist: dark mode... Not blocking — would just be a nice polish."
  Reasoning: feature request, explicit "not blocking", positive future-looking.
  Labels: {priority: low, category: feature_request, sentiment: positive}

EX5 — normal + neutral (technical bug report, calm):
  Subject: "CSV export missing the 'created_at' column"
  Body: "The CSV export from the tickets view is missing the 'created_at' column
  despite it being visible in the UI. Repro on Chrome and Firefox."
  Reasoning: data issue but recoverable (re-export with correct config likely),
  no escalation language, factual repro.
  Labels: {priority: normal, category: bug_report, sentiment: negative}

EX6 — urgent + negative (data integrity, calm tone):
  Subject: "Salesforce sync duplicates records on retry"
  Body: "When the Salesforce sync retries after a transient failure, it inserts a
  duplicate of every already-synced record... Caught it at 1,000 duplicates this
  morning."
  Reasoning: data integrity failure at scale, but tone is professional/factual.
  Labels: {priority: urgent, category: bug_report, sentiment: negative}

Now read the ticket and call the classify_ticket tool. Pick the single best label
for each dimension; do not hedge.\
"""


def _enum_values(enum_cls: type) -> list[str]:
    return [m.value for m in enum_cls]


CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_ticket",
    "description": (
        "Record the classification of a support ticket "
        "along priority, category, and sentiment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "priority": {
                "type": "string",
                "enum": _enum_values(Priority),
                "description": "Severity × urgency.",
            },
            "category": {
                "type": "string",
                "enum": _enum_values(Category),
                "description": "Underlying issue type.",
            },
            "sentiment": {
                "type": "string",
                "enum": _enum_values(Sentiment),
                "description": "Emotional tone of the ticket text.",
            },
        },
        "required": ["priority", "category", "sentiment"],
    },
}


def _build_user_message(ticket: Ticket) -> str:
    return f"Subject: {ticket.subject}\n\nBody: {ticket.body}"


class ClassifierError(RuntimeError):
    """Raised when the model returns no usable tool_use block."""


async def classify(
    ticket: Ticket,
    *,
    client: AsyncAnthropic | None = None,
    model: str = DEFAULT_MODEL,
) -> Classification:
    """Classify a single ticket. Caller may pass a shared ``AsyncAnthropic`` for reuse."""
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ClassifierError(
                "ANTHROPIC_API_KEY is not set — put it in .env or pass an explicit client."
            )
        client = AsyncAnthropic(max_retries=8)

    response = await client.messages.create(
        model=model,
        max_tokens=256,
        system=[
            {
                "type": "text",
                "text": CLASSIFY_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_ticket"},
        messages=[{"role": "user", "content": _build_user_message(ticket)}],
    )

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "classify_ticket":
            return Classification.model_validate(block.input)

    raise ClassifierError(
        f"Model returned no classify_ticket tool_use block. stop_reason={response.stop_reason!r}"
    )
