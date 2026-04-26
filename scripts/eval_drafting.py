"""Evaluate the drafting + faithfulness pipeline.

For each ticket: retrieve top-k KB articles, draft a response, score faithfulness.
Reports aggregate faithfulness, per-category breakdown, and the worst offenders
(answers with the most unsupported claims).

Usage:
    uv run python -m scripts.eval_drafting                      # full 200-ticket eval
    uv run python -m scripts.eval_drafting --limit 5            # smoke test
    uv run python -m scripts.eval_drafting --k 5                # use top-5 retrieval
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from anthropic import AsyncAnthropic

from app.drafter import DraftedResponse, draft_response
from app.faithfulness import FaithfulnessReport, score_faithfulness
from app.fixtures import load_tickets
from app.kb import load_articles
from app.retrieval import RetrievalIndex, build_index
from app.schemas import KBArticle, Ticket

_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = _ROOT / "fixtures" / "synthetic" / "tickets.jsonl"
DEFAULT_KB = _ROOT / "fixtures" / "synthetic" / "kb" / "articles.jsonl"


@dataclass
class DraftingRow:
    ticket: Ticket
    draft: DraftedResponse | None
    faithfulness: FaithfulnessReport | None
    error: str | None
    elapsed_s: float


class _RateLimiter:
    """Same min-interval limiter as the classifier eval — keeps us under per-model RPM caps."""

    def __init__(self, rpm: int) -> None:
        self.min_interval_s = 60.0 / rpm
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self.min_interval_s - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


def _retrieve_articles(
    ticket: Ticket, index: RetrievalIndex, articles_by_id: dict[str, KBArticle], k: int
) -> list[KBArticle]:
    query = f"{ticket.subject}\n\n{ticket.body}"
    results = index.search(query, k=k)
    return [articles_by_id[aid] for aid, _ in results]


async def _process_one(
    ticket: Ticket,
    retrieved: list[KBArticle],
    client: AsyncAnthropic,
    sem: asyncio.Semaphore,
    drafter_limiter: _RateLimiter,
    scorer_limiter: _RateLimiter,
) -> DraftingRow:
    async with sem:
        t0 = time.perf_counter()
        try:
            await drafter_limiter.acquire()
            draft = await draft_response(ticket, retrieved, client=client)
            await scorer_limiter.acquire()
            report = await score_faithfulness(
                draft.response, retrieved, ticket=ticket, client=client
            )
            return DraftingRow(
                ticket=ticket,
                draft=draft,
                faithfulness=report,
                error=None,
                elapsed_s=time.perf_counter() - t0,
            )
        except Exception as e:  # noqa: BLE001
            return DraftingRow(
                ticket=ticket,
                draft=None,
                faithfulness=None,
                error=f"{type(e).__name__}: {e}",
                elapsed_s=time.perf_counter() - t0,
            )


async def run(
    tickets: Sequence[Ticket],
    articles: Sequence[KBArticle],
    *,
    k: int,
    concurrency: int,
    drafter_rpm: int,
    scorer_rpm: int,
) -> list[DraftingRow]:
    index = build_index(list(articles))
    articles_by_id = {a.id: a for a in articles}
    client = AsyncAnthropic(max_retries=8)
    sem = asyncio.Semaphore(concurrency)
    drafter_limiter = _RateLimiter(rpm=drafter_rpm)
    scorer_limiter = _RateLimiter(rpm=scorer_rpm)

    tasks = []
    for t in tickets:
        retrieved = _retrieve_articles(t, index, articles_by_id, k)
        tasks.append(_process_one(t, retrieved, client, sem, drafter_limiter, scorer_limiter))
    return await asyncio.gather(*tasks)


def _print_report(rows: list[DraftingRow], wall_s: float) -> None:
    n = len(rows)
    ok = [r for r in rows if r.faithfulness is not None]
    n_err = n - len(ok)

    print(f"Tickets:        {n}")
    print(f"Successes:      {len(ok)}")
    print(f"Errors:         {n_err}")
    print(f"Wall time:      {wall_s:.1f}s")
    if not ok:
        return

    avg_score = sum(r.faithfulness.score for r in ok) / len(ok)
    perfect = sum(1 for r in ok if r.faithfulness.score == 1.0)
    total_claims = sum(len(r.faithfulness.claims) for r in ok)
    total_supported = sum(r.faithfulness.n_supported for r in ok)

    print()
    print(f"Avg faithfulness:   {avg_score:.1%}")
    print(f"Perfect (1.0):      {perfect}/{len(ok)}  ({perfect / len(ok):.1%})")
    print(f"Claims supported:   {total_supported}/{total_claims}")
    print(f"Avg claims/answer:  {total_claims / len(ok):.1f}")

    # Per-category breakdown.
    by_cat: dict[str, list[float]] = defaultdict(list)
    for r in ok:
        by_cat[r.ticket.category.value].append(r.faithfulness.score)
    print("\nFaithfulness by category:")
    for cat, scores in sorted(by_cat.items()):
        avg = sum(scores) / len(scores)
        print(f"  {cat:>20s}: {avg:.1%}  (n={len(scores)})")

    # Worst offenders.
    worst = sorted(ok, key=lambda r: r.faithfulness.score)[:5]
    print("\nWorst 5 (lowest faithfulness):")
    for r in worst:
        unsupported = [c for c in r.faithfulness.claims if not c.supported]
        print(
            f"  {r.ticket.id} | score={r.faithfulness.score:.0%} | "
            f"{r.faithfulness.n_unsupported}/{len(r.faithfulness.claims)} unsupported"
        )
        for c in unsupported[:2]:
            txt = c.text if len(c.text) <= 90 else c.text[:87] + "..."
            print(f"    UNSUPPORTED: {txt}")

    if n_err:
        print("\nFirst few errors:")
        shown = 0
        for r in rows:
            if r.error is None:
                continue
            print(f"  {r.ticket.id}: {r.error}")
            shown += 1
            if shown >= 5:
                break


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB)
    parser.add_argument(
        "--limit", type=int, default=None, help="Evaluate only the first N tickets."
    )
    parser.add_argument("--k", type=int, default=3, help="Top-k articles to feed the drafter.")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--drafter-rpm",
        type=int,
        default=45,
        help="Sonnet 4.6 RPM cap. Adjust to your tier.",
    )
    parser.add_argument(
        "--scorer-rpm",
        type=int,
        default=45,
        help="Haiku 4.5 RPM cap (also 50 on the standard tier).",
    )
    args = parser.parse_args()

    tickets = load_tickets(args.fixtures)
    if args.limit is not None:
        tickets = tickets[: args.limit]
    articles = load_articles(args.kb)

    print(
        f"Drafting eval: {len(tickets)} tickets, {len(articles)} KB articles, "
        f"k={args.k}, concurrency={args.concurrency}"
    )
    print()
    t0 = time.perf_counter()
    rows = asyncio.run(
        run(
            tickets,
            articles,
            k=args.k,
            concurrency=args.concurrency,
            drafter_rpm=args.drafter_rpm,
            scorer_rpm=args.scorer_rpm,
        )
    )
    wall = time.perf_counter() - t0
    _print_report(rows, wall)
    return 0 if all(r.faithfulness is not None for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
