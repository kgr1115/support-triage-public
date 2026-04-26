# support-triage (private fork)

[![CI](https://github.com/kgr1115/support-triage/actions/workflows/ci.yml/badge.svg)](https://github.com/kgr1115/support-triage/actions/workflows/ci.yml)

A local-first AI tool for B2B SaaS support teams: classify tickets, retrieve KB context via embeddings, draft citation-grounded responses, and surface the top-3 macros — with an eval harness scoring faithfulness and recall@k.

This is the **private** working fork. Real Zendesk/Salesforce exports live here. The clean, shippable mirror is at `../support-triage-public/`.

## Who this is for

Open-source — anyone running a B2B SaaS support org who wants to evaluate or self-host a local-first triage assistant. The maintainer is dogfooding it as a portfolio piece.

## Screenshots

The agent workstation lives at `frontend/` (Vite + React + TypeScript). Pick a sample
ticket from the dropdown, click **Triage**, and the right pane fills in with
classification badges, the top-3 retrieved KB articles (with similarity scores),
an editable drafted reply with citations highlighted, and the top-3 suggested
macros — all from a single `POST /triage` call to the FastAPI backend.

Empty state — pick a sample or paste a ticket:

![empty state](docs/screenshots/01-empty-state.png)

After triage — classification, retrieved KB, drafted reply with `[KB-…]`
citations:

![triage result](docs/screenshots/02-triage-result.png)

## Quick start

```bash
# install
uv sync && pnpm --dir frontend install

# put your Anthropic key in .env (gitignored)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# run dev — backend on :8000, frontend on :5173 (Vite dev-proxies API calls)
# Either of these — both spawn both processes with prefixed logs and Ctrl-C
# propagation. The Python launcher works without GNU make.
uv run python -m scripts.dev
make dev

# tests
make test                  # all unit/integration tests (no API calls)
make eval-classifier       # priority/category/sentiment accuracy
make eval-retrieval        # recall@k (no API key needed)
make eval-drafting         # citation-grounded reply + faithfulness
```

## What's here

- `app/` — FastAPI backend.
  - `main.py` — `/triage` endpoint (classify + retrieve + draft + macros).
  - `classifier.py`, `drafter.py`, `faithfulness.py` — Anthropic-powered components.
  - `retrieval.py` — sentence-transformers + FAISS for KB and macros.
  - `kb.py`, `macros.py`, `fixtures.py`, `schemas.py` — loaders and Pydantic models.
- `frontend/` — Vite + React + TypeScript triage workstation.
- `scripts/` — fixture/KB/macro generators and three eval drivers.
- `fixtures/synthetic/` — 200 labeled tickets, 26 KB articles, 19 macros.
- `tests/` — unit + integration tests (mocked LLM, real retrieval).
- `CLAUDE.md` — standing brief. Read first.
- `ARCHITECTURE.md` — improvement-pipeline philosophy.
- `.claude/agents/`, `.claude/skills/`, `.claude/commands/improve.md` — improvement pipeline.
- `blocked-paths.txt` — paths the publisher refuses to push (PII guard).

## Eval baselines

Run on the 200-ticket synthetic fixture set. All numbers reproducible from the committed fixtures + a fresh API key. Full breakdown with worst-offender analysis — and a "How to reproduce these numbers" section listing the exact commands and which calls cost API credits — in `eval_runs/2026-04-26-eval-summary.md`.

| Metric | Result | Random / modal baseline |
|---|---|---|
| Category accuracy | 95.0% | 20% |
| Priority accuracy | 62.0% | 40.5% (modal) |
| Sentiment accuracy | 63.0% | 61% (modal) |
| recall@1 | 87.5% | 3.8% |
| recall@3 | 95.8% | 11.5% |
| recall@5 | 98.9% | 19.2% |
| Faithfulness | 97.1% | n/a |

### Where the evals fail (read-with-self-awareness)

Category confusion (off-diagonal only):

| true → predicted | count |
|---|---|
| `integration_setup` → `bug_report` | 7 |
| `bug_report` → `integration_setup` | 3 |

Same boundary, both directions — the genuine seam between *integration is misconfigured* and *integration's runtime behavior is buggy*.

Priority confusion (off-diagonal only) — the biggest open gap:

| true → predicted | count |
|---|---|
| `normal` → `high` | 26 |
| `normal` → `low` | 21 |
| `high` → `urgent` | 13 |
| `urgent` → `high` | 9 |
| `low` → `normal` | 5 |
| `urgent` → `normal` | 1 |
| `low` → `high` | 1 |

Dominant failure is `normal → high`: model classifies inconvenience as urgency. Reading the misses, ~16pp of the 38pp gap is genuine label ambiguity (*"session expires every 5 min"* defensibly HIGH or NORMAL by org SLA convention) and ~20pp is real model error.

## Limits and known failure modes

- **Sentiment is barely above modal baseline (63% vs 61%).** The negative/frustrated boundary is fuzzy in calm-toned B2B support text; the model often disagrees with my labels in cases where the labels are arguably wrong. Tighten or scrap in v2.
- **Drafter occasionally extrapolates beyond KB.** ~17% of responses have at least one unsupported claim, mostly defining KB terms in its own words ("a fresh browser session means…") or predicting outcomes of documented workarounds ("chunking should fix it"). Representative cases analysed in `eval_runs/2026-04-26-eval-summary.md`.
- **Prompt engineering contributes ~28pp of faithfulness.** Re-running the same drafter with a permissive "be helpful" prompt (no grounding rules) yields 69.2% faithfulness vs the strict prompt's 97.1% — same model, same retrieval, same scorer. Drafts get 43% longer and pick up speculation like *"this error typically means…"* and *"the April 24 release probably changed…"* — neither in the KB. Full contrast in `eval_runs/2026-04-26-eval-summary.md`.
- **Single-provider LLM layer.** Anthropic-only in this build (Sonnet 4.6 drafter, Haiku 4.5 classifier + scorer). No fallback. The original spec referenced a multi-provider "SiftRobust pattern" — that abstraction would slot in at `app/classifier.py` and `app/drafter.py` if needed.

## Improvement pipeline

`/improve` runs: researcher → architect → implementer → tester → publisher (and debugger on failure). See `ARCHITECTURE.md` for the handoff contracts.

## License

MIT.
