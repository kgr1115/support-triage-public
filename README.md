# support-triage

[![CI](https://github.com/kgr1115/support-triage-public/actions/workflows/ci.yml/badge.svg)](https://github.com/kgr1115/support-triage-public/actions/workflows/ci.yml)

A local-first AI tool for B2B SaaS support teams: classify tickets, retrieve KB context via embeddings, draft citation-grounded responses, and surface the top-3 macros — with an eval harness scoring faithfulness and recall@k.

Designed for one operator on one workspace. No SaaS, no multi-tenant, no telemetry.

## Who this is for

B2B SaaS support teams who want a local-first triage assistant they can self-host and audit.

## Screenshots

Empty state — pick a sample or paste a ticket:

![empty state](docs/screenshots/01-empty-state.png)

After triage — classification, retrieved KB, drafted reply with `[KB-…]` citations:

![triage result](docs/screenshots/02-triage-result.png)

## Quick start

```bash
# install
uv sync && pnpm --dir frontend install

# put your Anthropic key in .env (gitignored)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# run dev — backend on :8000, frontend on :5173 (Vite dev-proxies API calls)
# Either of these — both spawn both processes with prefixed logs.
uv run python -m scripts.dev
make dev

# tests (no API calls)
make test

# eval drivers (one runs offline; the others hit Anthropic)
make eval-retrieval        # recall@k — local sentence-transformers, no key needed
make eval-classifier       # priority/category/sentiment accuracy
make eval-drafting         # citation-grounded reply + faithfulness
```

## What's here

- `app/` — FastAPI backend.
  - `main.py` — `POST /triage` endpoint (classify + retrieve + draft + macros).
  - `classifier.py`, `drafter.py`, `faithfulness.py` — Anthropic-powered components.
  - `retrieval.py` — sentence-transformers + FAISS for KB and macros.
  - `kb.py`, `macros.py`, `fixtures.py`, `schemas.py` — loaders and Pydantic models.
- `frontend/` — Vite + React + TypeScript triage workstation.
- `scripts/` — fixture/KB/macro generators and three eval drivers.
- `fixtures/synthetic/` — 200 labeled tickets, 26 KB articles, 19 macros.
- `tests/` — unit + integration tests (mocked LLM, real retrieval).
- `CLAUDE.md` — standing brief for Claude Code.
- `.claude/agents/worker.md`, `.claude/skills/core-workflow/SKILL.md`, `.claude/commands/run.md` — single-agent workflow setup.

## How it works

1. Load tickets from a Zendesk/Salesforce export (or the synthetic fixture set).
2. Classify each ticket: priority + category + sentiment (Anthropic tool use, prompt-cached).
3. Embed ticket text with `sentence-transformers/all-MiniLM-L6-v2` and retrieve top-k from a FAISS index over the KB.
4. Draft a citation-grounded response (Sonnet 4.6) restricted to facts in the retrieved articles or paraphrasing the customer's own report. Citations render inline as `[KB-…]`.
5. Surface the top-3 most-likely macros via the same embedding similarity over a separate macro index.

## Eval baselines

Run on the 200-ticket synthetic fixture set. All numbers reproducible from the committed fixtures + a fresh API key.

| Metric | Result | Random / modal baseline |
|---|---|---|
| Category accuracy | 95.0% | 20% |
| Priority accuracy | 62.0% | 40.5% (modal) |
| Sentiment accuracy | 63.0% | 61% (modal) |
| recall@1 | 87.5% | 3.8% |
| recall@3 | 95.8% | 11.5% |
| recall@5 | 98.9% | 19.2% |
| Faithfulness | 97.1% | n/a |

- Classifier: `claude-haiku-4-5` with prompt caching.
- Retrieval: local sentence-transformers + FAISS flat-IP. No API calls.
- Drafting: `claude-sonnet-4-6`. Faithfulness scored by `claude-haiku-4-5` — a clean-room implementation of the ragas faithfulness metric (decompose answer into atomic claims, judge each against ticket + retrieved KB).

### Where the evals fail (read-with-self-awareness)

Full breakdown with worst-offender analysis: `eval_runs/2026-04-26-eval-summary.md`.

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
- **Drafter occasionally extrapolates beyond KB.** ~17% of responses have at least one unsupported claim, mostly defining KB terms in its own words ("a fresh browser session means…") or predicting outcomes of documented workarounds ("chunking should fix it"). Five representative cases analysed in `eval_runs/2026-04-26-eval-summary.md` with proposed prompt mitigations.
- **No baseline-drafter contrast yet.** The 97.1% faithfulness number needs a permissive-prompt counterpart to put the prompt-engineering delta in context. Tracked as a follow-up eval.
- **Single-provider LLM layer.** Anthropic-only in this build (Sonnet 4.6 drafter, Haiku 4.5 classifier + scorer). No fallback. The original spec referenced a multi-provider abstraction — that would slot in at `app/classifier.py` and `app/drafter.py` if needed.

## License

MIT.
