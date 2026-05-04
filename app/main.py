"""FastAPI app for support-triage.

Endpoints:
- GET  /health  - liveness probe.
- POST /triage  - run the full pipeline (classify + KB retrieval + draft + macro
                  suggestion) on a single ticket and return the agent's view.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from anthropic import AsyncAnthropic
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.drafter import DraftedResponse
from app.kb import load_articles
from app.macros import load_macros
from app.providers import SiftRobustOrchestrator, build_default_orchestrator
from app.retrieval import build_index
from app.schemas import Category, Classification, Priority, Sentiment, Ticket

_ROOT = Path(__file__).resolve().parents[1]
KB_PATH = _ROOT / "fixtures" / "synthetic" / "kb" / "articles.jsonl"
MACRO_PATH = _ROOT / "fixtures" / "synthetic" / "macros" / "macros.jsonl"


class TriageRequest(BaseModel):
    """Inbound ticket — just the customer-visible fields."""

    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)


class RetrievedItem(BaseModel):
    """A retrieved KB article or macro with its similarity score."""

    id: str
    title: str
    score: float


class TriageResponse(BaseModel):
    """Everything the agent's UI needs to triage one ticket."""

    classification: Classification
    retrieved_kb: list[RetrievedItem]
    drafted_response: DraftedResponse
    suggested_macros: list[RetrievedItem]
    classification_provider: str = Field(
        ...,
        description=(
            "Which LLM provider answered the classify call (e.g. 'anthropic', 'openai'). "
            "Surfaces sift-robust fallbacks so silent provider drift is impossible."
        ),
    )
    drafting_provider: str = Field(
        ...,
        description=(
            "Which LLM provider answered the draft call. "
            "Same audit purpose as classification_provider."
        ),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the retrieval indices + sift-robust orchestrator once on startup.
    Idempotent — tests can pre-populate ``app.state`` and the loader will skip work."""
    if not hasattr(app.state, "kb_index"):
        articles = load_articles(KB_PATH)
        app.state.kb_index = build_index(articles)
        app.state.kb_by_id = {a.id: a for a in articles}
    if not hasattr(app.state, "macro_index"):
        macros = load_macros(MACRO_PATH)
        app.state.macro_index = build_index(macros)
        app.state.macro_by_id = {m.id: m for m in macros}
    if not hasattr(app.state, "orchestrator"):
        app.state.orchestrator = build_default_orchestrator()
    yield


app = FastAPI(title="support-triage", version="0.1.0", lifespan=lifespan)


def get_client() -> AsyncAnthropic:
    """Anthropic client dependency. Tests override via ``app.dependency_overrides``."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set; classifier and drafter unavailable.",
        )
    return AsyncAnthropic(max_retries=8)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — confirms the API is reachable."""
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
async def triage(
    payload: TriageRequest,
    request: Request,
    _: AsyncAnthropic = Depends(get_client),  # noqa: B008 — FastAPI idiom; gate on key presence
) -> TriageResponse:
    """Classify, retrieve KB + macros, draft a citation-grounded reply.

    Classification and drafting run in parallel through the sift-robust
    orchestrator (Anthropic primary; OpenAI fallback if OPENAI_API_KEY is set).
    Retrieval is synchronous (FAISS flat-IP over ~26 articles + 18 macros — sub-100ms).
    """
    state = request.app.state
    orchestrator: SiftRobustOrchestrator = state.orchestrator
    query = f"{payload.subject}\n\n{payload.body}"

    kb_hits = state.kb_index.search(query, k=3)
    macro_hits = state.macro_index.search(query, k=3)
    kb_articles = [state.kb_by_id[aid] for aid, _ in kb_hits]

    # The classifier and drafter accept a Ticket; we construct a scratch one with
    # placeholder labels (overwritten by the classifier's output before the
    # response goes out, and unused by the drafter).
    scratch = Ticket(
        id="triage-request",
        subject=payload.subject,
        body=payload.body,
        priority=Priority.NORMAL,
        category=Category.LOGIN,
        sentiment=Sentiment.NEUTRAL,
    )

    (classification, classification_provider), (drafted, drafting_provider) = await asyncio.gather(
        orchestrator.classify(scratch),
        orchestrator.draft(scratch, kb_articles),
    )

    return TriageResponse(
        classification=classification,
        retrieved_kb=[
            RetrievedItem(id=aid, title=state.kb_by_id[aid].title, score=score)
            for aid, score in kb_hits
        ],
        drafted_response=drafted,
        suggested_macros=[
            RetrievedItem(id=mid, title=state.macro_by_id[mid].title, score=score)
            for mid, score in macro_hits
        ],
        classification_provider=classification_provider,
        drafting_provider=drafting_provider,
    )
