"""Tests for the FastAPI app — /health and /triage.

The /triage endpoint exercises retrieval against the real synthetic KB + macros
(fast — model is cached) and a mocked sift-robust orchestrator (no real API calls).
"""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app, get_client
from app.providers import SiftRobustOrchestrator
from app.schemas import Category, Classification, Priority, Sentiment


def _mock_classification() -> Classification:
    return Classification(
        priority=Priority.HIGH,
        category=Category.LOGIN,
        sentiment=Sentiment.FRUSTRATED,
    )


def _mock_drafted_text() -> str:
    return (
        "Sorry to hear you're locked out. Per [KB-LOGIN-02], an admin on your "
        "workspace can disable 2FA on your behalf. Please ask an admin and let "
        "us know once they've done so."
    )


def _mock_provider(name: str) -> AsyncMock:
    """Mock provider that returns a fixed classification + drafted response."""
    from app.drafter import DraftedResponse

    provider = AsyncMock()
    provider.name = name
    provider.classify.return_value = _mock_classification()

    async def _draft(ticket, articles, *, system_prompt=None):
        return DraftedResponse(
            ticket_id=ticket.id,
            retrieved_kb_ids=[a.id for a in articles],
            response=_mock_drafted_text(),
            cited_kb_ids=["KB-LOGIN-02"],
        )

    provider.draft.side_effect = _draft
    return provider


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_triage_returns_full_pipeline_view() -> None:
    """/triage uses the orchestrator from app.state. We override it with a mock
    that returns a fixed Classification + DraftedResponse so the test is
    deterministic and doesn't hit any real API."""
    primary = _mock_provider("anthropic")
    app.state.orchestrator = SiftRobustOrchestrator(primary=primary, secondary=None)
    app.dependency_overrides[get_client] = lambda: AsyncMock()  # bypass api-key gate
    try:
        with TestClient(app) as client:
            payload = {
                "subject": "Locked out after enabling 2FA",
                "body": "Recovery codes don't work either. Need help.",
            }
            response = client.post("/triage", json=payload)
            assert response.status_code == 200
            data = response.json()

            assert data["classification"] == {
                "priority": "high",
                "category": "login_issue",
                "sentiment": "frustrated",
            }
            # Retrieval should surface a 2FA-related KB article in the top 3
            kb_ids = {item["id"] for item in data["retrieved_kb"]}
            assert "KB-LOGIN-02" in kb_ids, f"expected KB-LOGIN-02 in {kb_ids}"

            # Drafted response carries the citation we put in the mock
            assert "[KB-LOGIN-02]" in data["drafted_response"]["response"]
            assert data["drafted_response"]["cited_kb_ids"] == ["KB-LOGIN-02"]

            # Three macro suggestions, each with a score
            assert len(data["suggested_macros"]) == 3
            for m in data["suggested_macros"]:
                assert {"id", "title", "score"} <= m.keys()

            # provider_used surfaces (sift-robust audit trail)
            assert data["classification_provider"] == "anthropic"
            assert data["drafting_provider"] == "anthropic"
    finally:
        app.dependency_overrides.clear()
        if hasattr(app.state, "orchestrator"):
            delattr(app.state, "orchestrator")


def test_triage_returns_503_without_api_key(monkeypatch) -> None:
    """If ANTHROPIC_API_KEY is missing and no override is set, /triage 503s cleanly."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app.dependency_overrides.clear()  # ensure no override masks the env check
    with TestClient(app) as client:
        response = client.post(
            "/triage",
            json={"subject": "Test", "body": "Test"},
        )
        assert response.status_code == 503
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]
