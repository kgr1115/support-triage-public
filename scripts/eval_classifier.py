"""Evaluate the classifier against the labeled synthetic fixtures.

Runs ``classify`` over every ticket in ``fixtures/synthetic/tickets.jsonl`` with bounded
concurrency and reports per-dimension accuracy + a category confusion matrix. Uses prompt
caching so only the first call pays full system-prompt input cost.

Usage:
    uv run python -m scripts.eval_classifier
    uv run python -m scripts.eval_classifier --limit 20    # quick smoke test
    uv run python -m scripts.eval_classifier --concurrency 5
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from anthropic import AsyncAnthropic

from app.classifier import classify
from app.fixtures import load_tickets
from app.schemas import Category, Classification, Priority, Sentiment, Ticket

DEFAULT_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "tickets.jsonl"


@dataclass
class EvalRow:
    ticket: Ticket
    pred: Classification | None
    error: str | None
    elapsed_s: float


class _RateLimiter:
    """Minimum-interval async limiter to stay under Anthropic's RPM ceiling.

    Anthropic's free/standard tier on Haiku 4.5 caps at 50 RPM independently of
    the 50K TPM ceiling. With concurrency alone, parallel kickoffs exceed RPM
    even at modest worker counts; this serializes the *start* of each request.
    """

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


async def _run_one(
    ticket: Ticket,
    client: AsyncAnthropic,
    sem: asyncio.Semaphore,
    limiter: _RateLimiter,
) -> EvalRow:
    async with sem:
        await limiter.acquire()
        t0 = time.perf_counter()
        try:
            pred = await classify(ticket, client=client)
            return EvalRow(ticket=ticket, pred=pred, error=None, elapsed_s=time.perf_counter() - t0)
        except Exception as e:  # noqa: BLE001 — eval driver must keep going
            return EvalRow(
                ticket=ticket, pred=None, error=f"{type(e).__name__}: {e}",
                elapsed_s=time.perf_counter() - t0,
            )


async def run(tickets: Sequence[Ticket], concurrency: int, rpm: int) -> list[EvalRow]:
    client = AsyncAnthropic(max_retries=8)
    sem = asyncio.Semaphore(concurrency)
    limiter = _RateLimiter(rpm=rpm)
    return await asyncio.gather(*(_run_one(t, client, sem, limiter) for t in tickets))


def _accuracy(rows: Sequence[EvalRow], attr: str) -> tuple[int, int]:
    ok = 0
    n = 0
    for r in rows:
        if r.pred is None:
            continue
        n += 1
        if getattr(r.pred, attr) == getattr(r.ticket, attr):
            ok += 1
    return ok, n


def _confusion_matrix(rows: Sequence[EvalRow], attr: str) -> dict[tuple[str, str], int]:
    cm: Counter[tuple[str, str]] = Counter()
    for r in rows:
        if r.pred is None:
            continue
        true_v = getattr(r.ticket, attr).value
        pred_v = getattr(r.pred, attr).value
        cm[(true_v, pred_v)] += 1
    return dict(cm)


def _print_confusion(
    rows: Sequence[EvalRow], attr: str, levels: list[str], label: str
) -> None:
    print(f"\n{label} confusion (rows = true, cols = predicted, only off-diagonal shown):")
    cm = _confusion_matrix(rows, attr)
    offdiag = {k: v for k, v in cm.items() if k[0] != k[1]}
    if not offdiag:
        print(f"  (none — perfect {label.lower()} accuracy)")
        return
    for true_v in levels:
        for pred_v in levels:
            if true_v == pred_v:
                continue
            v = cm.get((true_v, pred_v), 0)
            if v > 0:
                print(f"  {true_v:>20s} -> {pred_v:<20s} : {v}")


def _print_mispredictions(
    rows: Sequence[EvalRow], attr: str, label: str, n_max: int = 10
) -> None:
    print(f"\nFirst {n_max} {label.lower()} mispredictions (id | true -> pred | subject):")
    shown = 0
    for r in rows:
        if r.pred is None:
            continue
        true_v = getattr(r.ticket, attr).value
        pred_v = getattr(r.pred, attr).value
        if true_v == pred_v:
            continue
        subject = r.ticket.subject
        if len(subject) > 80:
            subject = subject[:77] + "..."
        print(f"  {r.ticket.id} | {true_v:>10s} -> {pred_v:<10s} | {subject}")
        shown += 1
        if shown >= n_max:
            break
    if shown == 0:
        print(f"  (none — perfect {label.lower()} accuracy)")


def _print_report(rows: list[EvalRow], wall_s: float) -> None:
    n = len(rows)
    n_ok = sum(1 for r in rows if r.pred is not None)
    n_err = n - n_ok

    cat_ok, _ = _accuracy(rows, "category")
    pri_ok, _ = _accuracy(rows, "priority")
    sen_ok, _ = _accuracy(rows, "sentiment")

    print(f"Tickets:        {n}")
    print(f"Successes:      {n_ok}")
    print(f"Errors:         {n_err}")
    print(f"Wall time:      {wall_s:.1f}s")
    print()
    if n_ok > 0:
        print(f"Category acc:   {cat_ok}/{n_ok}  = {cat_ok / n_ok:.1%}")
        print(f"Priority acc:   {pri_ok}/{n_ok}  = {pri_ok / n_ok:.1%}")
        print(f"Sentiment acc:  {sen_ok}/{n_ok}  = {sen_ok / n_ok:.1%}")

        _print_confusion(rows, "category", [c.value for c in Category], "Category")
        _print_confusion(rows, "priority", [p.value for p in Priority], "Priority")
        _print_confusion(rows, "sentiment", [s.value for s in Sentiment], "Sentiment")

        _print_mispredictions(rows, "priority", "Priority")
        _print_mispredictions(rows, "sentiment", "Sentiment")

    if n_err > 0:
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
    parser.add_argument(
        "--limit", type=int, default=None, help="If set, only evaluate the first N tickets."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max in-flight requests. Rate limiter still enforces RPM cap.",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=45,
        help="Requests-per-minute cap. 45 stays under Haiku 4.5's 50 RPM ceiling.",
    )
    args = parser.parse_args()

    tickets = load_tickets(args.fixtures)
    if args.limit is not None:
        tickets = tickets[: args.limit]

    print(
        f"Evaluating classifier on {len(tickets)} tickets, "
        f"concurrency={args.concurrency}, rpm={args.rpm}"
    )
    print()
    t0 = time.perf_counter()
    rows = asyncio.run(run(tickets, concurrency=args.concurrency, rpm=args.rpm))
    wall = time.perf_counter() - t0
    _print_report(rows, wall)

    return 0 if all(r.pred is not None for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
