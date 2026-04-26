"""Mocked unit tests for the faithfulness scorer — no real API calls."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.faithfulness import (
    CLAIMS_TOOL,
    Claim,
    FaithfulnessError,
    FaithfulnessReport,
    score_faithfulness,
)
from app.schemas import Category, KBArticle


def _articles() -> list[KBArticle]:
    return [
        KBArticle(
            id="KB-LOGIN-02",
            title="2FA recovery",
            body="If recovery codes don't work, an admin can disable 2FA.",
            categories=[Category.LOGIN],
        )
    ]


def _mock_response(claims: list[dict]) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name="report_claims", input={"claims": claims})
    return SimpleNamespace(content=[block], stop_reason="tool_use")


def test_report_score_when_all_supported() -> None:
    report = FaithfulnessReport(
        answer="...",
        claims=[
            Claim(text="A", supported=True, reasoning="..."),
            Claim(text="B", supported=True, reasoning="..."),
        ],
    )
    assert report.score == 1.0
    assert report.n_supported == 2
    assert report.n_unsupported == 0


def test_report_score_with_mixed_support() -> None:
    report = FaithfulnessReport(
        answer="...",
        claims=[
            Claim(text="A", supported=True, reasoning="..."),
            Claim(text="B", supported=False, reasoning="..."),
            Claim(text="C", supported=True, reasoning="..."),
        ],
    )
    assert report.score == pytest.approx(2 / 3)


def test_report_score_empty_claims_is_one() -> None:
    """Empty claim list = vacuously faithful (e.g. politeness-only response)."""
    report = FaithfulnessReport(answer="thanks!", claims=[])
    assert report.score == 1.0


def test_score_faithfulness_parses_tool_use() -> None:
    client = AsyncMock()
    client.messages.create.return_value = _mock_response(
        [
            {"text": "An admin can disable 2FA.", "supported": True, "reasoning": "in KB"},
            {
                "text": "Recovery happens within 5 minutes.",
                "supported": False,
                "reasoning": "no support",
            },
        ]
    )
    answer = "An admin can disable 2FA [KB-LOGIN-02]. Recovery happens within 5 minutes."

    report = asyncio.run(score_faithfulness(answer, _articles(), client=client))

    assert len(report.claims) == 2
    assert report.score == 0.5
    assert report.claims[0].supported is True
    assert report.claims[1].supported is False


def test_score_faithfulness_raises_when_no_tool_use() -> None:
    client = AsyncMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="I refuse.")],
        stop_reason="end_turn",
    )
    with pytest.raises(FaithfulnessError):
        asyncio.run(score_faithfulness("answer", _articles(), client=client))


def test_claims_tool_schema_is_well_formed() -> None:
    """Sanity: tool schema requires the three fields the parser depends on."""
    props = CLAIMS_TOOL["input_schema"]["properties"]["claims"]["items"]["properties"]
    assert set(props.keys()) == {"text", "supported", "reasoning"}
    assert props["supported"]["type"] == "boolean"
