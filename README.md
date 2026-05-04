# support-triage

[![CI](https://github.com/kgr1115/support-triage-public/actions/workflows/ci.yml/badge.svg)](https://github.com/kgr1115/support-triage-public/actions/workflows/ci.yml)

A local-first AI tool for B2B SaaS support teams: classify tickets, retrieve KB context via embeddings, draft citation-grounded responses, and surface the top-3 macros — with an eval harness scoring faithfulness and recall@k.

📊 **Latest eval cycle** → [`eval_runs/2026-04-26-eval-summary.md`](eval_runs/2026-04-26-eval-summary.md) — strict faithfulness 97.1%, recall@3 95.8%, classifier 95% category / 100% within-1-tier priority. Full worst-offender analysis + reproduction runbook.

Designed for one operator on one workspace. No SaaS, no multi-tenant, no telemetry.

## Who this is for

B2B SaaS support teams who want a local-first triage assistant they can self-host and audit.

## Demo

The agent workstation is `frontend/` (Vite + React + TypeScript). Pick a sample
ticket from the dropdown, click **Triage**, and the right pane fills in with
classification badges, the top-3 retrieved KB articles (with similarity scores),
an editable drafted reply with citations highlighted, and the top-3 suggested
macros — all from a single `POST /triage` call to the FastAPI backend.

<!-- Once docs/demo.gif exists, replace the two static screenshots below with: ![demo](docs/demo.gif) -->

Empty state — pick a sample or paste a ticket:

![empty state](docs/screenshots/01-empty-state.png)

After triage — classification, retrieved KB, drafted reply with `[KB-…]` citations:

![triage result](docs/screenshots/02-triage-result.png)

## Requirements

- **Python**: 3.11+ (managed via [`uv`](https://docs.astral.sh/uv/)).
- **Node**: 20+ (managed via [`pnpm`](https://pnpm.io/) for the frontend).
- **OS**: developed on Windows 11; should run on macOS/Linux (no platform-specific code; the dev launcher is pure Python).
- **API key**: an Anthropic key for end-to-end runs. `make eval-retrieval` runs offline with no API key (see "Try without an API key" below).
- **Disk**: the FAISS index for the synthetic KB is small (<10 MB). Real KBs scale linearly.

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

## Try without an API key

Before paying for an Anthropic key, you can run the retrieval eval offline:

```bash
uv sync
make eval-retrieval
```

This loads the 200 synthetic tickets + 26 KB articles from `fixtures/synthetic/`, runs `sentence-transformers` + FAISS retrieval, and prints recall@1, @3, @5. No API calls. Should finish in under a minute.

What this DOES tell you: whether the embedding-based retrieval finds the right KB articles for synthetic support tickets across 5 categories.

What this does NOT tell you: classifier accuracy, draft faithfulness, or end-to-end UX. Those need an API key (`make eval-classifier`, `make eval-drafting`, `make dev`).

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

## Customize for your org

The reference implementation is opinionated about defaults but the swap-points are isolated:

- **Your KB articles** — replace `fixtures/synthetic/kb/articles.jsonl` with your own JSONL (one JSON object per line: `id`, `title`, `body`, `categories[]`). Restart the app — the FAISS index rebuilds in-memory from the JSONL on startup. The retrieval layer doesn't know or care that the articles are synthetic.
- **Your tickets** — `fixtures/synthetic/tickets.jsonl` is the labeled fixture set the eval harness uses. For triaging your own tickets, the `/triage` endpoint accepts a `Ticket` POST body directly — see `app/schemas.py:Ticket` for the shape (`subject`, `body`, plus optional `priority`, `category`, `sentiment`, `relevant_kb_ids` for eval). To bulk-triage a Zendesk/Salesforce export, write an adapter that maps export rows into `Ticket` shape and POSTs them to `/triage`.
- **Your macros** — replace `fixtures/synthetic/macros/macros.jsonl` with your team's canned-reply templates (same JSONL shape: `id`, `title`, `body`, `categories[]`). Restart the app.
- **Your LLM provider** — the classifier and drafter are in `app/classifier.py` and `app/drafter.py`. Currently Anthropic-only (Sonnet 4.6 drafter, Haiku 4.5 classifier + scorer). Swap to OpenAI / local model by replacing the client construction in those two files. The "Limitations" section below notes the original spec referenced a multi-provider abstraction — that's where it would slot in.

What's NOT a clean swap right now: changing the embedding model means changing it in `app/retrieval.py` (the only place embeddings are loaded). Since the index is rebuilt in-memory on startup, there's no stale-index risk — but if you've persisted an index elsewhere, rebuild it with the new model.

## Limitations

- **Priority classifier: 62% strict, 100% within-1 tier.** Every priority misprediction lands on an adjacent ordinal tier — the strict gap is fuzzy-boundary disagreement (billing/admin requests defensibly HIGH or NORMAL by SLA convention), not classifier confusion. Worst-offender breakdown in [`eval_runs/2026-04-26-eval-summary.md`](eval_runs/2026-04-26-eval-summary.md).
- **Sentiment is barely above modal baseline (63% vs 61%).** The negative/frustrated boundary is fuzzy in calm-toned B2B support text; the model often disagrees with my labels in cases where the labels are arguably wrong. Tighten or scrap in v2.
- **Drafter occasionally extrapolates beyond KB.** ~17% of responses have at least one unsupported claim, mostly defining KB terms in its own words ("a fresh browser session means…") or predicting outcomes of documented workarounds ("chunking should fix it"). Five representative cases analysed in `eval_runs/2026-04-26-eval-summary.md` with proposed prompt mitigations.
- **Prompt engineering contributes ~28pp of faithfulness.** Re-running the same drafter with a permissive "be helpful" prompt (no grounding rules) yields 69.2% faithfulness vs the strict prompt's 97.1% — same model, same retrieval, same scorer. Drafts get 43% longer and pick up speculation like *"this error typically means…"* and *"the April 24 release probably changed…"* — neither in the KB. Full contrast in [`eval_runs/2026-04-26-eval-summary.md`](eval_runs/2026-04-26-eval-summary.md).
- **Single-provider LLM layer.** Anthropic-only in this build (Sonnet 4.6 drafter, Haiku 4.5 classifier + scorer). No fallback. The original spec referenced a multi-provider abstraction — that would slot in at `app/classifier.py` and `app/drafter.py` if needed.

## License

MIT.
