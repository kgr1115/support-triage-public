"""Tests for the retrieval module.

The slow embedding-model load is shared via a module-scoped fixture so it runs
exactly once per test session — typically 2–5s on a warm cache, ~15s cold.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.kb import load_articles
from app.retrieval import EMBEDDING_DIM, RetrievalIndex, build_index, embed
from app.schemas import Category, KBArticle

KB_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "kb" / "articles.jsonl"


@pytest.fixture(scope="module")
def synthetic_index() -> Iterator[RetrievalIndex]:
    """One real index built once for the whole test module."""
    articles = load_articles(KB_PATH)
    yield build_index(articles)


def test_embed_returns_normalized_384d_vectors() -> None:
    vectors = embed(["password reset email not received", "discount code didn't apply"])
    assert vectors.shape == (2, EMBEDDING_DIM)
    # L2 norm should be ~1 (normalize_embeddings=True).
    norms = (vectors**2).sum(axis=1) ** 0.5
    for n in norms:
        assert 0.99 <= n <= 1.01


def test_build_index_rejects_empty() -> None:
    with pytest.raises(ValueError):
        build_index([])


def test_search_returns_at_most_k_results() -> None:
    articles = [
        KBArticle(
            id="A1",
            title="Login troubleshooting",
            body="Steps to debug login.",
            categories=[Category.LOGIN],
        ),
        KBArticle(
            id="A2",
            title="Billing FAQ",
            body="How charges work.",
            categories=[Category.BILLING],
        ),
        KBArticle(
            id="A3",
            title="Webhooks setup",
            body="HMAC signatures and retries.",
            categories=[Category.INTEGRATION],
        ),
    ]
    idx = build_index(articles)
    results = idx.search("how do I debug a failing webhook signature?", k=2)
    assert len(results) == 2
    # Webhook article should rank highest for that query.
    assert results[0][0] == "A3"


def test_synthetic_index_finds_obvious_matches(synthetic_index: RetrievalIndex) -> None:
    """End-to-end sanity: queries with strong topical overlap should retrieve the right article."""
    cases = [
        ("password reset email never arrives in my inbox", "KB-LOGIN-03"),
        ("my session keeps expiring after 5 minutes", "KB-LOGIN-04"),
        ("we got charged twice for the same month", "KB-BILL-01"),
        ("webhook signature verification fails sometimes", "KB-INT-01"),
        ("dashboard total is double-counting after I apply a tag filter", "KB-BUG-01"),
    ]
    for query, expected_id in cases:
        results = synthetic_index.search(query, k=3)
        retrieved = [aid for aid, _ in results]
        assert expected_id in retrieved, (
            f"{query!r} -> {retrieved}, expected {expected_id} in top-3"
        )


def test_kb_load_returns_26_articles() -> None:
    articles = load_articles(KB_PATH)
    assert len(articles) == 26
    ids = [a.id for a in articles]
    assert len(ids) == len(set(ids))  # unique
