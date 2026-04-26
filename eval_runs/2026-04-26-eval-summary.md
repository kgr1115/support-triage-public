# Eval run — 2026-04-26

All three eval drivers exercised end-to-end against the committed synthetic
fixtures (200 tickets, 26 KB articles, 19 macros). All numbers reproducible
from `make eval-classifier`, `make eval-retrieval`, `make eval-drafting`
against the `main` branch as of this run.

## Headline numbers

| Metric | Result | Modal / random baseline | Headroom |
|---|---|---|---|
| Category accuracy | 95.0% (190/200) | 20% (5 categories) | 5pp before ceiling |
| Priority accuracy | 62.0% (124/200) | 40.5% (modal: `normal`) | 38pp before ceiling |
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

2. **Permissive-prompt baseline** — re-run drafter+faithfulness with a
   minimal "be helpful" prompt (no grounding rules) to put the 97.1%
   in context. The delta is the prompt-engineering value. **One-day
   eval cycle.**

3. **Priority labels v2** — re-grade ~15 borderline scenarios where
   the model and the labeler can both defend their answer. Closes
   ~10pp of the priority gap. **Half-day.**

4. **Retrieval ground truth v2** — fix the 5 over-generous KB labels
   (Zapier scenarios pointing at `KB-INT-05`, etc.). Lifts recall@3
   to ~98%. **One hour.**

5. **Confusion-aware classifier metric** — report "within 1 priority
   tier" alongside strict accuracy. Distinguishes "model is confused"
   from "labels and model disagree on a fuzzy boundary" without
   relabeling. **Two hours.**

— Logged 2026-04-26 by the maintainer.
