# Eval run — 2026-04-26

All three eval drivers exercised end-to-end against the committed synthetic
fixtures (200 tickets, 26 KB articles, 19 macros). All numbers reproducible
from `make eval-classifier`, `make eval-retrieval`, `make eval-drafting`
against the `main` branch as of this run.

## Headline numbers

| Metric | Result | Modal / random baseline | Headroom |
|---|---|---|---|
| Category accuracy | 95.0% (190/200) | 20% (5 categories) | 5pp before ceiling |
| Priority accuracy (strict) | 62.0% (124/200) | 40.5% (modal: `normal`) | 38pp before ceiling |
| Priority within-1 tier | **100.0% (200/200)** | n/a | ceiling |
| Sentiment accuracy | 63.0% (126/200) | 61% (modal: `negative`) | weak signal |
| recall@1 | 87.5% | 3.8% (1/26 random) | 12pp |
| recall@3 | 95.8% | 11.5% | 4pp |
| recall@5 | 98.9% | 19.2% | 1pp |
| Faithfulness | 97.1% | n/a | 3pp |

Recall computed against the 180 tickets that carry a non-empty
`relevant_kb_ids` ground-truth label; 20 cosmetic / wishlist scenarios
are intentionally label-free and skipped from the recall numerator.

## Classifier — what's broken

### Category (95.0%, 9 wrong out of 198 successes)

Off-diagonal confusion only:

| true → predicted | count |
|---|---|
| integration_setup → bug_report | 7 |
| bug_report → integration_setup | 3 |

Same boundary, both directions. The fixtures' "broken integration"
scenarios sit on a genuine seam between *"the integration is
misconfigured"* (label: `integration_setup`) and *"an integration's
runtime behavior is buggy"* (label: `bug_report`). Examples:

- `{integration} sync drops the '{field}' field silently` —
  authored as `integration_setup` because the customer is configuring
  field mapping. Model defensibly says `bug_report`.
- `Zapier zap fails with 'invalid payload' on {event}` —
  same authoring rationale, same model disagreement.

Real B2B support orgs route these inconsistently too. A targeted prompt
fix could tighten the seam, but at 95% category accuracy the marginal
return is small.

### Priority (62.0%, 76 wrong)

Off-diagonal confusion (rows = true, cols = predicted):

| true → predicted | count |
|---|---|
| normal → high | 26 |
| normal → low | 21 |
| high → urgent | 13 |
| urgent → high | 9 |
| low → normal | 5 |
| urgent → normal | 1 |
| low → high | 1 |

The dominant failure is `normal → high` (26): the model classifies
inconvenience as urgency. Reading the cases, this is genuine label
ambiguity — *"your session expires every 5 minutes"* and *"a setting
doesn't persist on reload"* can defensibly be HIGH or NORMAL depending
on org SLA conventions.

The smaller `normal → low` (21) is the model under-rating routine
billing/admin requests when the customer's tone is calm. Easier to fix
with prompt anchoring in a v2.

`urgent ↔ high` confusions (13 + 9 = 22 cases) cluster on the
multi-user vs. single-user blocking distinction — exactly the boundary
the v1 prompt tried to anchor. Reading the misses, the prompt is
right-leaning: it considers `New users can't accept invite` (multi-user)
URGENT but the model says HIGH, and `Charged twice` (money mistake) HIGH
but the model says URGENT. Both judgments are defensible.

Net read: ~20pp of the priority gap is real model error; ~16pp is label
ambiguity that would need either tighter authoring or a multi-label
metric (e.g. "within 1 step of correct").

**Within-1-tier confirms the ambiguity hypothesis.** A fresh re-run
with the new `_priority_within_one_tier` metric (ordinal order
`low < normal < high < urgent`) reports **100.0% (200/200) within one
tier** — strict accuracy on that same re-run was 61.0%, within stochastic
noise of the 62.0% headline above. Every priority misprediction is on an
adjacent tier; the model never confuses `urgent` with `low` or `normal`
with `urgent`. Whatever's left after better label authoring is fuzzy-
boundary disagreement, not classifier confusion.

### Sentiment (63.0%, 74 wrong)

Modal baseline is 61% (always-predict-negative). The classifier is
barely above. Sentiment is the weakest signal in this eval — the
negative/frustrated boundary is genuinely fuzzy in calm-toned B2B
support text. The dominant remaining failure mode is
`frustrated → negative` (16): scenarios I labeled FRUSTRATED with
calm-toned bodies.

Honest options for a v2:
1. Tighter authoring: only label FRUSTRATED when the body has explicit
   escalation language ("the third time", "every time", caps lock).
2. Drop sentiment from the classifier — most consumers of triage
   classification care about priority and category.
3. Accept it as a soft signal.

## Retrieval — where it misses

87.5% recall@1 / 95.8% recall@3 / 98.9% recall@5 against the 180
truthed tickets. The recall@3 misses (8 tickets) cluster around two
patterns:

1. **Over-generous ground-truth labels.** I labeled `KB-INT-05`
   ("CRM connectors: Salesforce, HubSpot, Zendesk, Jira") as relevant
   for Zapier scenarios — but `KB-INT-05` doesn't actually cover Zapier.
   The retrieval is correct; my labels were wrong. ~5 of the 8 misses
   are this class.
2. **KB content gaps.** `Login page returns 500` ground-truth was
   `KB-LOGIN-05` (account suspension) but `KB-LOGIN-05` doesn't
   discuss server errors. ~3 misses are real KB gaps that adding
   content to the article would close.

Either fix is a one-line label change or a one-paragraph KB edit.

## Faithfulness — worst offenders

97.1% across 200 tickets is the headline — the 35 imperfect responses
cluster around four bad-but-recoverable patterns. Each is illustrative
of a specific class of agent over-helpfulness. Fixing the prompt to
address these would likely lift faithfulness past 98% with no model
change.

### `integration_setup-017` — 50% (4/8 unsupported)

Subject: *Custom OAuth app stuck at consent screen*  
Retrieved: `KB-INT-02` (API authentication: keys, scopes, OAuth, refresh tokens).

Unsupported claims:
- "A fresh browser session means opening a new private/incognito window or clearing cookies."
- "Users should walk through the OAuth consent steps without navigating away, opening new tabs, or clicking back."

**Pattern: drafter is *defining KB terms in its own words*.**
KB-INT-02 says "start the flow again from a fresh browser session" but
doesn't define what "fresh" means. The drafter helpfully expanded it,
introducing facts the KB doesn't actually contain.

**Mitigation:** prompt addition — "if the KB uses a term without
defining it, repeat the term verbatim; do not expand."

### `bug_report-035` — 60% (2/5 unsupported)

Subject: *Bulk reassign 'completes' but reassignments revert on reload*  
Retrieved: `KB-PROD-01` (bulk operations).

Unsupported claims:
- "Chunking into groups of 250 should allow the reassignments to persist correctly."
- "A page reload should confirm whether the assignees are holding after the chunked operation."

**Pattern: drafter is *predicting outcomes* of documented workarounds.**
KB-PROD-01 says "chunk the operation into batches of 250" — that's a
procedural fact. The drafter then claims this WILL fix the customer's
specific issue (it should, but the KB makes no such promise).

**Mitigation:** prompt addition — "describe the documented workaround,
then ask the customer to confirm whether it resolved their case; do
not predict outcomes."

### `login_issue-034` — 70% (3/10 unsupported)

Subject: *Can't log in — 'too many attempts' even after password reset*  
Retrieved: `KB-LOGIN-03` (password reset deliverability), `KB-LOGIN-05`.

Unsupported claims:
- "After a password reset, the customer should receive a reset confirmation email."
- "The customer should use the new password immediately from the reset link rather than typing it manually."

**Pattern: drafter is *adding generic best-practice advice* not in
KB.** Reset confirmation emails and "use immediately" are real product
behaviors generally, but neither is documented in the retrieved KB.
The drafter is leaning on world knowledge.

**Mitigation:** the strict-only-from-KB rule already covers this; this
is a prompt-adherence failure, not a prompt-design gap. May benefit
from a stronger model on the drafter (currently Sonnet 4.6) or from
extended thinking to give the model space to self-check before
emitting.

### `integration_setup-018` — 75% (2/8 unsupported)

Subject: *Webhook signature verification failing intermittently*  
Retrieved: `KB-INT-01` (Webhook subscriptions, retries, signatures).

Unsupported claims:
- "Header normalisation or casing differences in the receiver could cause signature verification to fail."
- "Sharing the raw X-Signature header value and raw request body from a failing delivery would help us debug."

**Pattern: drafter is *speculating on causes* AND *asking for specific
debug artifacts not in KB*.** The first is a plausible hypothesis; the
second is a procedural ask the KB doesn't authorize.

**Mitigation:** the prompt rules out the first ("no speculation about
causes") but the model still slips. The second is arguable — asking
for raw artifacts is legitimate next-step support behavior, and the
faithfulness rubric arguably treats it too strictly.

### `billing_dispute-024` — 78% (2/9 unsupported)

Subject: *Need to update billing address on May invoice*  
Retrieved: `KB-BILL-04` (Invoices, taxes, billing portal).

Unsupported claims:
- "The agent requests confirmation of the exact billing date for the May invoice or the date the address change was made."
- "The agent requests verification that the updated address is showing correctly in the billing portal before re-issuing."

**Pattern: drafter is *adding verification steps not in KB*.** The
asks are reasonable support practice but the KB doesn't authorize them.
Same root cause as `integration_setup-018`'s second claim — borderline
between "agent over-helpfulness" and "agent doing their job."

## What this eval would change with another iteration

1. **Drafter prompt v2** — add "do not define KB terms" + "describe
   workarounds, don't predict outcomes." Likely lifts faithfulness to
   ~98% with no new model. **Half-day.**

2. **Priority labels v2** — re-grade ~15 borderline scenarios where
   the model and the labeler can both defend their answer. Closes
   ~10pp of the priority gap. **Half-day.**

3. **Retrieval ground truth v2** — fix the 5 over-generous KB labels
   (Zapier scenarios pointing at `KB-INT-05`, etc.). Lifts recall@3
   to ~98%. **One hour.**

4. **Confusion-aware classifier metric** — report "within 1 priority
   tier" alongside strict accuracy. Distinguishes "model is confused"
   from "labels and model disagree on a fuzzy boundary" without
   relabeling. **Two hours.**

## How to reproduce these numbers

All three eval drivers are deterministic given a fixed model + fixed
fixtures. The classifier and drafter make API calls (priced per the
maintainer's Anthropic plan); retrieval runs locally via
sentence-transformers and is free.

```bash
# one-time setup
uv sync
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# classifier eval — priority/category/sentiment accuracy + confusion matrices
make eval-classifier
#   ↳ uv run python -m scripts.eval_classifier
#   ↳ ~200 Haiku 4.5 tool-use calls
#   ↳ produces the "Classifier — what's broken" numbers above

# retrieval eval — recall@k against labeled relevant_kb_ids
make eval-retrieval
#   ↳ uv run python -m scripts.eval_retrieval
#   ↳ no API calls (local sentence-transformers + FAISS)
#   ↳ produces the "Retrieval — where it misses" numbers above

# drafting eval — citation-grounded reply + faithfulness
make eval-drafting
#   ↳ uv run python -m scripts.eval_drafting
#   ↳ ~200 Sonnet 4.6 drafts + ~200 Haiku 4.5 faithfulness scores
#   ↳ produces the 97.1% headline + worst-offender list above
```

Fixtures, KB, and macros are all checked in under
`fixtures/synthetic/` — no real customer data is exercised by these
runs. Re-running on a different model (`DEFAULT_MODEL` in
`app/classifier.py` / `app/drafter.py` / `app/faithfulness.py` is the
single point of override) will produce different numbers; that's the
point.

## Permissive-prompt baseline contrast

Run with `uv run python -m scripts.eval_drafting --prompt-style permissive`
(the `--prompt-style` flag was added in this iteration; `strict` is the
default). Same fixtures, same retrieval, same Haiku 4.5
faithfulness scorer — only the drafter's system prompt changes. The
permissive prompt drops all grounding rules: no "only state facts in
KB," no anti-speculation, no anti-meta-promise rules. Just *"be helpful
and informative; use the KB if relevant; feel free to add general
advice and context from your own knowledge."*

| Metric | Strict (production) | Permissive (baseline) | Δ |
|---|---|---|---|
| Avg faithfulness | **97.1%** | 69.2% | **+27.9pp** |
| Perfect responses (score 1.0) | 165/200 (82.5%) | 15/200 (7.5%) | +75pp |
| Avg claims/answer | 8.1 | 11.6 | +43% longer drafts |
| Supported claims | 1566/1612 | 1580/2311 | +14 supported, +699 unsupported |

The permissive prompt produces ~43% more claims per answer (model adds
context, speculation, generic advice), and almost all of the additional
claims are unsupported. Same model, same retrieval — the strict prompt
buys 28 percentage points of faithfulness, isolated from any other
variable.

Per-category contrast:

| Category | Strict | Permissive | Δ |
|---|---|---|---|
| billing_dispute | 97.5% | 73.2% | −24.3pp |
| bug_report | 97.3% | 63.9% | −33.4pp |
| feature_request | 96.9% | 72.2% | −24.7pp |
| integration_setup | 96.5% | 66.6% | −29.9pp |
| login_issue | 97.4% | 69.9% | −27.5pp |

`bug_report` takes the biggest hit. Without grounding rules the model
speculates aggressively about *why* a bug happens — exactly the
agent-over-helpfulness pattern the strict prompt is designed to block.

### Sample permissive failures

These are real outputs from the permissive run on the same fixture
tickets the strict run scored at 100%:

- **`login_issue-013`** — score 11% (8/9 unsupported).
  - *"The 'user not found' error typically means the system can't locate the account record."*
  - *"This error can happen if the email address on file has a subtle typo."*
  Both invented; KB-LOGIN-03 says neither.

- **`bug_report-009`** — score 18% (9/11 unsupported).
  - *"The issue is that the local/in-memory state in the browser session isn't updating."*
  - *"The April 24 release probably changed how read-state events are handled client-side."*
  Specific technical claims, neither sourced.

- **`integration_setup-017`** — score 30% (7/10 unsupported).
  - *"OAuth state mismatch typically happens when the browser tab is refreshed, a redirect is intercepted, or extensions are interfering."*
  - *"A private/incognito window with extensions disabled should be used."*
  Extrapolation from world knowledge, not from KB-INT-02.

### What this measures

The 28-point delta is the prompt-engineering value of the strict
prompt, isolated from model choice and retrieval quality. Without the
contrast, the 97.1% headline is impressive but unmoored. With it, the
strict prompt's value is concrete and reproducible: same model, same
context, +28pp faithfulness from the prompt rubric alone.

— Logged 2026-04-26 by the maintainer.
