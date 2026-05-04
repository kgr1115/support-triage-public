# Contributing to support-triage

Thanks for the interest. This is a small open-source reference implementation maintained for B2B SaaS support orgs to fork and self-host. Contributions are welcome — read this first.

## Before opening an issue

- **Check the README first** for setup, customization, and the "Try without an API key" path.
- **Check the eval reproduction runbook** at `eval_runs/2026-04-26-eval-summary.md` for the published numbers and how to reproduce them.
- **Bug reports** use the bug template; **feature requests** use the feature template. Both ask for the context that lets the maintainer triage quickly.

## Before opening a PR

### What's in scope

- Bug fixes that don't change documented behavior.
- Eval improvements (better faithfulness, better recall@k, better classifier accuracy) **with before/after numbers on the committed fixture set**.
- Adapters for new ticket sources (Zendesk variant, Salesforce, Intercom, Help Scout, etc.) — see `scripts/triage_zendesk_export.py` for the reference shape.
- Adapters for new KB sources (Notion, Confluence, markdown directory, etc.).
- New LLM provider implementations behind the existing `app/classifier.py` / `app/drafter.py` interfaces.
- Documentation improvements.
- Test coverage on existing code paths.

### What's out of scope

The locked principles in `CLAUDE.md`:

- **No hosted-infra dependencies** beyond LLM/embedding API calls. No Vercel/AWS/GCP/Railway. Local-first only.
- **No multi-tenant features.** Single operator, single workspace.
- **No telemetry / phone-home.** Ever.
- **No auto-replies to customers.** This tool augments human agents; every output is for human review.

PRs that touch these are closed politely with a pointer to the principle.

### How to propose a change

1. **Open an issue first** for non-trivial changes. Lets the maintainer give you "yes, sounds in scope" before you sink time into implementation.
2. **Fork + branch.** Use a descriptive branch name (`feat/intercom-adapter`, `fix/recall-on-empty-kb`).
3. **Match the project's conventions** — see "Code style" below.
4. **Include tests.** Bug fixes get a regression test. New code gets coverage.
5. **For methodology changes** (different embedding model, new prompt, new LLM provider) — include before/after eval numbers on the committed `fixtures/synthetic/` set. Numbers without a comparison are not enough.
6. **Open the PR** against `main`. The CI runs the test suite + retrieval eval (no API key needed).
7. **Squash-merge convention.** PRs squash to a single commit on main. Use a Conventional Commits prefix in the PR title (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).

## Code style

- **Python**: PEP 8 + ruff defaults. Type hints on public functions.
- **TypeScript**: Prettier defaults (2-space indent, single quotes are fine).
- **Comments**: docstrings on public APIs (FastAPI route handlers, public Python functions, exported React component prop types). Internal helpers stay uncommented unless the WHY is non-obvious.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).

## Testing locally

```bash
# all tests (no API calls)
make test

# eval drivers
make eval-retrieval        # offline; no API key needed
make eval-classifier       # needs ANTHROPIC_API_KEY
make eval-drafting         # needs ANTHROPIC_API_KEY
```

## What you'll need an API key for

The classifier, drafter, and faithfulness scorer all use Anthropic. If your contribution is in those code paths, you'll need an `ANTHROPIC_API_KEY` to run the relevant evals locally. If your contribution is in retrieval / fixtures / docs / adapters, `make eval-retrieval` is enough to validate.

## License

MIT. By submitting a PR you agree your contribution is MIT-licensed.

## Maintainer notes

This is a small project. Response times on issues and PRs are best-effort. If you need a feature urgently for your own org, the fastest path is usually to fork and add it locally — the project is designed to be customized.
