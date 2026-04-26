"""Evaluate KB retrieval against the labeled fixtures.

For each ticket with non-empty ``relevant_kb_ids``, embed (subject + body), retrieve
top-k from the KB, and compute recall@k = |retrieved ∩ relevant| / |relevant|.

No API calls — embeddings run locally via sentence-transformers.

Usage:
    uv run python -m scripts.eval_retrieval
    uv run python -m scripts.eval_retrieval --k 1 3 5 10
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from app.fixtures import load_tickets
from app.kb import load_articles
from app.retrieval import build_index
from app.schemas import Ticket

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = _ROOT / "fixtures" / "synthetic" / "tickets.jsonl"
DEFAULT_KB = _ROOT / "fixtures" / "synthetic" / "kb" / "articles.jsonl"


def _query(ticket: Ticket) -> str:
    return f"{ticket.subject}\n\n{ticket.body}"


def _recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def _print_failures(
    tickets: Sequence[Ticket], rankings: dict[str, list[str]], k: int, n_max: int = 10
) -> None:
    """Print up to n_max tickets where recall@k < 1.0 (ground truth missed in top-k)."""
    print(f"\nFirst {n_max} tickets where recall@{k} < 1.0:")
    shown = 0
    for t in tickets:
        relevant = set(t.relevant_kb_ids)
        if not relevant:
            continue
        retrieved = rankings[t.id][:k]
        missed = relevant - set(retrieved)
        if not missed:
            continue
        subject = t.subject if len(t.subject) <= 60 else t.subject[:57] + "..."
        print(
            f"  {t.id} | want {sorted(relevant)} | got {retrieved} "
            f"| missed {sorted(missed)} | {subject}"
        )
        shown += 1
        if shown >= n_max:
            break
    if shown == 0:
        print(f"  (none — perfect recall@{k})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB)
    parser.add_argument(
        "--k",
        type=int,
        nargs="+",
        default=[1, 3, 5],
        help="K values for recall@k. Default: 1 3 5.",
    )
    args = parser.parse_args()

    tickets = load_tickets(args.fixtures)
    articles = load_articles(args.kb)
    eval_tickets = [t for t in tickets if t.relevant_kb_ids]
    skipped = len(tickets) - len(eval_tickets)

    print(f"KB articles:        {len(articles)}")
    print(f"Total tickets:      {len(tickets)}")
    print(f"With ground truth:  {len(eval_tickets)}")
    print(f"Skipped (no truth): {skipped}")
    print()

    t0 = time.perf_counter()
    print("Building FAISS index...")
    index = build_index(articles)
    build_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    max_k = max(args.k)
    rankings: dict[str, list[str]] = {}
    for t in eval_tickets:
        results = index.search(_query(t), k=max_k)
        rankings[t.id] = [aid for aid, _ in results]
    search_s = time.perf_counter() - t0

    print(f"Index build:        {build_s:.1f}s")
    print(f"Search ({len(eval_tickets)} queries): {search_s:.1f}s")
    print()

    for k in sorted(args.k):
        total = 0.0
        perfect = 0
        for t in eval_tickets:
            r = _recall_at_k(rankings[t.id], set(t.relevant_kb_ids), k)
            total += r
            if r == 1.0:
                perfect += 1
        avg = total / len(eval_tickets)
        print(
            f"recall@{k}: {avg:.1%}   "
            f"(perfect on {perfect}/{len(eval_tickets)} = {perfect / len(eval_tickets):.1%})"
        )

    # Article hit-rate distribution: which KB articles are over- or under-retrieved?
    top1_hits: Counter[str] = Counter()
    for t in eval_tickets:
        top1_hits[rankings[t.id][0]] += 1
    print("\nTop-1 article hit-rate (top 5):")
    for aid, n in top1_hits.most_common(5):
        print(f"  {aid}: {n}")

    _print_failures(eval_tickets, rankings, k=3, n_max=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
