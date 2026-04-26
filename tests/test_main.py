"""Tests for the FastAPI app — /health and /triage.

The /triage endpoint exercises retrieval against the real synthetic KB + macros
(fast — model is cached) and a mocked Anthropic client (no real API calls).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app, get_client


def _mock_classifier_response() -> SimpleNamespace:
    block = SimpleNamespace(
        type="tool_use",
        name="classify_ticket",
        input={
            "priority": "high",
            "category": "login_issue",
            "sentiment": "frustrated",
        },
    )
    return SimpleNamespace(content=[block], stop_reason="tool_use")


def _mock_drafter_response() -> SimpleNamespace:
    block = SimpleNamespace(
        type="text",
        text=(
            "Sorry to hear you're locked out. Per [KB-LOGIN-02], an admin on your "
            "workspace can disable 2FA on your behalf. Please ask an admin and let "
            "us know once they've done so."
        ),
    )
    return SimpleNamespace(content=[block], stop_reason="end_turn")


def _mock_anthropic_client() -> AsyncMock:
    """Return a mock that satisfies both the classifier and drafter calls.

    Routing: classifier calls pass tools=[CLASSIFY_TOOL]; drafter calls do not.
    """
    client = AsyncMock()

    async def create(**kwargs):
        if kwargs.get("tools"):
            return _mock_classifier_response()
        return _mock_drafter_response()

    client.messages.create.side_effect = create
    return client


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_triage_returns_full_pipeline_view() -> None:
    app.dependency_overrides[get_client] = lambda: _mock_anthropic_client()
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
    finally:
        app.dependency_overrides.clear()


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
