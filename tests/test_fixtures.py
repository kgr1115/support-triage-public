from collections import Counter
from pathlib import Path

import pytest

from app.fixtures import load_tickets
from app.schemas import Category, Priority, Sentiment, Ticket
from scripts.generate_synthetic_fixtures import generate

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "tickets.jsonl"


@pytest.fixture(scope="module")
def synthetic_tickets() -> list[Ticket]:
    return load_tickets(FIXTURE_PATH)


def test_synthetic_fixture_loads(synthetic_tickets: list[Ticket]) -> None:
    """The committed JSONL exists and parses cleanly into 200 Tickets."""
    assert len(synthetic_tickets) == 200


def test_categories_are_balanced(synthetic_tickets: list[Ticket]) -> None:
    """All 5 categories present, each with 40 tickets — eval recall@k depends on this."""
    counts = Counter(t.category for t in synthetic_tickets)
    assert set(counts.keys()) == set(Category)
    for category, n in counts.items():
        assert n == 40, f"{category.value} has {n} tickets, expected 40"


def test_all_enums_used(synthetic_tickets: list[Ticket]) -> None:
    """At least one ticket per Priority and per Sentiment value — checks the weighted dists fire."""
    priorities = {t.priority for t in synthetic_tickets}
    sentiments = {t.sentiment for t in synthetic_tickets}
    assert priorities == set(Priority)
    assert sentiments == set(Sentiment)


def test_ids_are_unique(synthetic_tickets: list[Ticket]) -> None:
    ids = [t.id for t in synthetic_tickets]
    assert len(ids) == len(set(ids))


def test_no_unfilled_placeholders(synthetic_tickets: list[Ticket]) -> None:
    """A '{' in subject or body means a placeholder leaked through unfilled."""
    for t in synthetic_tickets:
        assert "{" not in t.subject, f"unfilled placeholder in subject of {t.id}: {t.subject!r}"
        assert "{" not in t.body, f"unfilled placeholder in body of {t.id}: {t.body!r}"


def test_generator_is_deterministic() -> None:
    """Two runs with the same seed produce identical (subject, body) sequences."""
    a = generate(count_per_category=5, seed=123)
    b = generate(count_per_category=5, seed=123)
    assert [(t.subject, t.body) for t in a] == [(t.subject, t.body) for t in b]


def test_committed_fixtures_match_generator() -> None:
    """The on-disk JSONL matches what the generator currently produces with the default seed.

    Drift means someone hand-edited the fixtures or the templates changed without a regenerate.
    Either is a red flag for the eval harness — those numbers are the portfolio.
    """
    in_memory = generate()
    on_disk = load_tickets(FIXTURE_PATH)
    assert len(in_memory) == len(on_disk)
    for a, b in zip(in_memory, on_disk, strict=True):
        assert a.model_dump(mode="json") == b.model_dump(mode="json"), (
            f"drift at {a.id}: regenerate via `make fixtures`"
        )
