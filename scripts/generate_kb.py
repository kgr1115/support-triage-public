"""Generate the synthetic KB corpus: ~26 plausible support articles.

The committed ``fixtures/synthetic/kb/articles.jsonl`` is the canonical artifact;
regenerate via ``make kb``. Articles are hand-written here (no LLM), keeping the
corpus stable and inspectable.

Coverage maps to the ticket scenarios so each ticket has at least one
``relevant_kb_ids`` ground-truth match for recall@k evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas import Category, KBArticle

DEFAULT_OUT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "kb" / "articles.jsonl"
)


# Each article: id, title, body, categories.
# Bodies are plausible-doc style — terminology mirrors ticket scenarios so that
# embedding-based retrieval has signal to work with.
ARTICLES: list[dict] = [
    # ---------------- LOGIN ----------------
    {
        "id": "KB-LOGIN-01",
        "title": "Troubleshooting SSO sign-in issues",
        "categories": [Category.LOGIN],
        "body": (
            "If users encounter an SSO redirect loop after authenticating with their identity "
            "provider (Okta, Azure AD, OneLogin, Auth0, Google Workspace), the most common "
            "cause is a stale or rotated signing certificate. After rotating an IdP signing "
            "certificate, re-upload the new cert in your workspace's SSO settings and ask "
            "affected users to clear cookies for both your IdP and our domain. SAML assertions "
            "rejected with no error detail typically mean a cert mismatch between IdP and SP. "
            "If a SAML assertion is being POSTed successfully but rejected, verify the SP entity "
            "ID and ACS URL in your IdP configuration match exactly what we display in the SSO "
            "settings page. For IdP-initiated flows, ensure the RelayState is preserved end to end."
        ),
    },
    {
        "id": "KB-LOGIN-02",
        "title": "Recovering from a 2FA or MFA lockout",
        "categories": [Category.LOGIN],
        "body": (
            "If you are locked out after enabling 2FA and your recovery codes do not work, "
            "an admin on the account can disable 2FA on your behalf from the Team Members page. "
            "If MFA codes never arrive on your phone (SMS) after switching carriers, your number "
            "may need to be re-verified — go to Profile > Security > Reverify phone. For "
            "Authenticator app codes that don't work, confirm your device clock is in sync; "
            "TOTP codes drift if the device clock is off. Hardware key (YubiKey) registration "
            "must be redone after a key replacement. If the whole team is locked out (e.g. after "
            "a forced 2FA enrollment), contact support — we can re-enable a temporary recovery "
            "window for the workspace."
        ),
    },
    {
        "id": "KB-LOGIN-03",
        "title": "Password reset email not received",
        "categories": [Category.LOGIN],
        "body": (
            "If a password reset email never arrives, first check your spam folder and any inbox "
            "filters that route 'noreply' addresses elsewhere. If other emails from our domain "
            "do reach you but the reset email does not, check that the registered email address "
            "in your profile matches the one you're requesting the reset for — typos in the "
            "registered address are a common cause. Reset emails are sent from "
            "no-reply@example.com; whitelist this address in your mail provider. If you've "
            "requested resets multiple times in a short window, our system rate-limits to one "
            "every 15 minutes; wait and retry. As a last resort, an admin on the account can "
            "issue a magic link from the admin panel."
        ),
    },
    {
        "id": "KB-LOGIN-04",
        "title": "Session timeouts, magic links, and invite expiration",
        "categories": [Category.LOGIN],
        "body": (
            "Default session lifetime is 8 hours. If your session is expiring more frequently "
            "than expected (e.g. every 5–15 minutes), check Workspace > Security > Session "
            "Settings — a recently changed 'reauthorize after inactivity' policy often explains "
            "this. Magic link logins that cycle back to the sign-in screen typically indicate a "
            "browser cookie issue: try in an incognito window or clear cookies for the domain. "
            "Invite links expire after 72 hours by default; if newly-sent invites show 'expired' "
            "on first click, your workspace's invite-link TTL has been set to a very short "
            "value — check Workspace > Settings > Invitations to extend it."
        ),
    },
    {
        "id": "KB-LOGIN-05",
        "title": "Account suspension and access denial",
        "categories": [Category.LOGIN],
        "body": (
            "An 'account suspended' message at sign-in despite current billing usually means the "
            "workspace was flagged by an automated abuse check, not a billing issue. If billing "
            "is current and your team is blocked, contact support with the workspace ID — we can "
            "review and unsuspend within one business hour. Suspensions caused by genuine billing "
            "failures show a 'past due' message, not 'suspended'. If only some users see "
            "'suspended' while others sign in normally, the user accounts in question may have "
            "been individually disabled — check the Team Members page."
        ),
    },

    # ---------------- BILLING ----------------
    {
        "id": "KB-BILL-01",
        "title": "Disputing duplicate or incorrect charges",
        "categories": [Category.BILLING],
        "body": (
            "If you were charged twice for the same billing period or charged at the wrong rate "
            "(for example, a renewal hit the card at the new pricing despite a grandfathered "
            "rate from sales), open a billing dispute in the billing portal and include the "
            "charge dates and the expected amount. We refund verified duplicate charges within "
            "5–7 business days. Grandfathered-pricing disputes require attaching the email from "
            "sales confirming the original rate; refunds for these are processed manually and "
            "may take up to 10 business days."
        ),
    },
    {
        "id": "KB-BILL-02",
        "title": "Mid-cycle plan changes and pro-ration",
        "categories": [Category.BILLING],
        "body": (
            "Upgrading or downgrading mid-cycle pro-rates the difference between your old and "
            "new plan based on the days remaining in the cycle. For an upgrade from Starter to "
            "Pro on day 10 of a 30-day cycle, you'll be charged (Pro − Starter) × 20/30. The "
            "pro-rated charge appears on your next regular invoice, not as a separate charge, "
            "unless the upgrade triggers a card-on-file capture for an immediate seat bump. If "
            "your pro-rated math doesn't match ours, the most common cause is a mid-cycle seat "
            "count change that we factored into the calculation. Contact support and we'll walk "
            "through the line items."
        ),
    },
    {
        "id": "KB-BILL-03",
        "title": "Cancellation, auto-renewal, and refunds",
        "categories": [Category.BILLING],
        "body": (
            "To stop auto-renewal, go to Billing > Subscription > Cancel renewal at least 24 "
            "hours before your renewal date. You'll receive a confirmation email; keep this for "
            "your records. If auto-renewal fired despite a cancellation, check that your "
            "cancellation was confirmed (not just initiated) — an unfinished cancellation flow "
            "leaves the subscription active. Refunds for incorrectly-fired auto-renewals are "
            "issued within 5 business days. Cancelling seats mid-cycle does not pro-rate; you "
            "keep the seats until the end of the cycle and the seat count is reduced on the "
            "next invoice."
        ),
    },
    {
        "id": "KB-BILL-04",
        "title": "Invoices, taxes, and the billing portal",
        "categories": [Category.BILLING],
        "body": (
            "Invoices appear in the billing portal within 24 hours of the billing date. If a "
            "monthly invoice is missing despite a successful charge, the invoice was generated "
            "but failed to attach to your portal — contact support with the billing month and "
            "we'll re-issue. Tax rates are computed based on the billing address on file; if a "
            "tax line item is incorrect for your country (UK, DE, FR, etc.), update the billing "
            "address first, then request a re-issue of the affected invoice. For US customers, "
            "we collect sales tax in states where we have nexus."
        ),
    },
    {
        "id": "KB-BILL-05",
        "title": "Payment methods: cards, ACH, and failed payments",
        "categories": [Category.BILLING],
        "body": (
            "We accept major credit cards on all plans. ACH payment is available on Growth, Pro, "
            "and Enterprise — if the checkout shows only credit card options, switch to a "
            "supported plan or contact sales. 'Payment failed' notifications when your card is "
            "valid and has available credit usually indicate a 3-D Secure challenge that wasn't "
            "completed or a billing-address mismatch with the card issuer. Update the billing "
            "address to match the card and retry. Persistent failures despite a valid card may "
            "be a fraud-check block on the card issuer's side; call your bank to authorize the "
            "merchant."
        ),
    },
    {
        "id": "KB-BILL-06",
        "title": "Discount codes and promotional pricing",
        "categories": [Category.BILLING],
        "body": (
            "Discount codes apply to renewals automatically when entered in the Billing > "
            "Promotions panel before the renewal date. If a discount code from a renewal email "
            "didn't apply and you were charged the full amount, the code may have a single-use "
            "or first-renewal-only restriction. Contact support with the code and the renewal "
            "invoice; we'll refund the difference where the code was eligible. Multiple "
            "discounts cannot be stacked on a single renewal."
        ),
    },

    # ---------------- INTEGRATION ----------------
    {
        "id": "KB-INT-01",
        "title": "Webhook subscriptions, retries, and signature verification",
        "categories": [Category.INTEGRATION],
        "body": (
            "Webhook subscriptions deliver events (ticket.created, ticket.updated, user.created, "
            "subscription.cancelled, payment.failed, deal.closed_won, etc.) to your endpoint via "
            "HTTPS POST. Each delivery carries an HMAC-SHA256 signature in the X-Signature "
            "header; verify using your webhook secret. If signature verification fails "
            "intermittently (e.g. 1 in 50 deliveries), the most common cause is using the wrong "
            "secret across subscription rotations. Outbound webhook delivery has a 10-second "
            "default timeout; if your receiver is slower, you can extend to 30 seconds in the "
            "subscription settings. Webhooks that haven't fired for hours despite the endpoint "
            "being healthy usually indicate a paused subscription — check Subscriptions > Status."
        ),
    },
    {
        "id": "KB-INT-02",
        "title": "API authentication: keys, scopes, OAuth, and refresh tokens",
        "categories": [Category.INTEGRATION],
        "body": (
            "API keys carry a scope (admin, read-only, custom). An admin-scoped key returning "
            "403 on /v1/tickets or /v1/users while working on /v1/me typically means the key was "
            "scoped to a specific resource type during creation — generate a fresh admin key "
            "from Settings > API. For OAuth applications, refresh tokens are valid for 90 days "
            "by default. If your refresh tokens expire after 7–30 days instead, the user has "
            "explicitly reduced their token lifetime in the OAuth app settings. Custom OAuth "
            "apps stuck at the consent screen typically have a redirect URI mismatch."
        ),
    },
    {
        "id": "KB-INT-03",
        "title": "API rate limits and 429 errors",
        "categories": [Category.INTEGRATION],
        "body": (
            "Rate limits scale with plan: Starter 60 req/min, Growth 300, Pro 600, Enterprise "
            "1,000. If you're hitting 429s at a lower rate than your plan documents, check that "
            "you're authenticating with the correct key — keys generated under a previous plan "
            "tier inherit that tier's limit until rotated. For nightly syncs that exceed any "
            "tier's limit, batch endpoints (POST /v1/tickets/bulk) consume a single rate-limit "
            "token regardless of payload size."
        ),
    },
    {
        "id": "KB-INT-04",
        "title": "Setting up the Slack integration",
        "categories": [Category.INTEGRATION],
        "body": (
            "After authorizing the Slack integration, configure the destination channel in "
            "Integrations > Slack > Channel Routing. If messages are landing in #general "
            "despite a different configured channel, the bot user wasn't invited to the target "
            "channel; in Slack, run /invite @your-bot-name in the destination channel. "
            "Re-authorizing the integration does not fix this — it's a Slack-side membership "
            "issue, not an OAuth issue."
        ),
    },
    {
        "id": "KB-INT-05",
        "title": "CRM connectors: Salesforce, HubSpot, Zendesk, Jira",
        "categories": [Category.INTEGRATION],
        "body": (
            "When a CRM connector (Salesforce, HubSpot, Zendesk, Jira) is stuck in 'connecting' "
            "indefinitely, check the integration logs for the underlying error. '401 "
            "unauthorized' indicates an OAuth token expired or was revoked — re-authorize. "
            "'connection refused' usually means an IP allowlist on the CRM side that doesn't "
            "include our outbound IPs (listed in our security docs). 'rate_limit_exceeded' from "
            "the CRM side requires you to request a higher API rate limit from that vendor. "
            "'invalid_grant' or 'OAuth state mismatch' means the consent flow didn't complete "
            "cleanly — start the flow again from a fresh browser session."
        ),
    },
    {
        "id": "KB-INT-06",
        "title": "Custom field mapping and sync errors",
        "categories": [Category.INTEGRATION],
        "body": (
            "When a custom field is silently dropped during sync, check that the field exists on "
            "BOTH sides with matching types. Multi-select fields require an explicit list-of-"
            "strings mapping; lookup fields need the related object configured first; rollup and "
            "formula fields are read-only and cannot be mapped as sync targets. After fixing the "
            "mapping, trigger a manual re-sync from Integrations > [vendor] > Sync now. The "
            "sync log will show 'mapping resolved' for fields that now flow correctly."
        ),
    },

    # ---------------- PRODUCT / FEATURE ----------------
    {
        "id": "KB-PROD-01",
        "title": "Bulk operations: export, reassign, and tag",
        "categories": [Category.FEATURE_REQUEST, Category.BUG_REPORT],
        "body": (
            "The bulk action menu (Tickets > select rows > Actions) supports bulk reassign, bulk "
            "tag, and bulk export to CSV. Bulk export from any view includes all columns visible "
            "in that view — to export columns not in the current view, customize the view first. "
            "If a bulk reassign appears to complete (success toast) but the assignees revert "
            "after a page reload, you've hit a known issue with bulk operations on more than 500 "
            "tickets — chunk the operation into batches of 250."
        ),
    },
    {
        "id": "KB-PROD-02",
        "title": "Roles and permissions",
        "categories": [Category.FEATURE_REQUEST],
        "body": (
            "Built-in roles are admin (full access), member (default — can edit assigned items), "
            "and read-only viewer (Pro and Enterprise plans). For more granular access, custom "
            "roles can be defined in Settings > Roles. A 'viewer' role that can view dashboards "
            "but not edit anything is the read-only viewer role — assign from Team Members. "
            "Custom roles support per-resource permissions (tickets, macros, integrations, "
            "billing)."
        ),
    },
    {
        "id": "KB-PROD-03",
        "title": "Saved views, filters, and tags",
        "categories": [Category.FEATURE_REQUEST, Category.BUG_REPORT],
        "body": (
            "Saved views persist filters, sort order, and column selection per user. Views can "
            "be shared to teams in Workspace > Views > Sharing. To filter saved views by team "
            "membership in the picker, use the team filter in the picker dropdown. Filters "
            "include tag, priority, assignee, channel, and date. Tags containing hyphens (e.g. "
            "'vip-customer') are searched exactly as written; if a hyphenated tag returns no "
            "search results, verify the tag spelling in Tags > Manage."
        ),
    },
    {
        "id": "KB-PROD-04",
        "title": "Dashboards and analytics",
        "categories": [Category.FEATURE_REQUEST, Category.BUG_REPORT],
        "body": (
            "Analytics dashboards default to preset date ranges (7d, 30d, 90d). Custom date "
            "ranges are available on Pro and Enterprise plans — click the date picker and "
            "select 'Custom'. Dashboard totals are computed at query time over the filtered "
            "set. If a dashboard total appears to double-count after a tag filter is applied, "
            "you may be seeing tickets that were merged into others — toggle 'Include merged' "
            "off in the view settings to deduplicate."
        ),
    },
    {
        "id": "KB-PROD-05",
        "title": "Audit log and compliance reporting",
        "categories": [Category.FEATURE_REQUEST, Category.BUG_REPORT],
        "body": (
            "The audit log records all administrative actions, including bulk operations. Each "
            "entry includes the actor (the agent who performed the action), timestamp, action "
            "type, and target. If audit log entries for bulk operations show the actor as "
            "'system' instead of the agent, your workspace is on the legacy bulk-operation "
            "path; contact support to migrate. Audit log export is available via the "
            "/v1/audit_log API endpoint (admin scope) and via the UI on Pro and Enterprise."
        ),
    },

    # ---------------- BUGS / KNOWN ISSUES ----------------
    {
        "id": "KB-BUG-01",
        "title": "Known issues: dashboard counting and tag search",
        "categories": [Category.BUG_REPORT],
        "body": (
            "Two known issues currently affect the dashboard and search: (1) when a tag filter "
            "is applied, totals can double-count tickets that have been merged into other "
            "tickets — the workaround is to toggle 'Include merged' off in view settings; "
            "(2) tag search does not match tags containing hyphens consistently across all "
            "indexes — the fix is rolling out and tracked under issue #4521. As an interim "
            "workaround, search using the tag's underscore equivalent or rename hyphenated tags."
        ),
    },
    {
        "id": "KB-BUG-02",
        "title": "CSV export troubleshooting",
        "categories": [Category.BUG_REPORT],
        "body": (
            "If a CSV export is missing a column that's visible in the UI (created_at, "
            "assignee_email, tag_list, external_id, first_response_at), the export view does "
            "not match the UI view's column selection. Customize the export view in Views > "
            "Export Settings to add the missing column. CSV export timestamps are emitted in "
            "UTC by default; the column header is named the same as the UI's localized header, "
            "which can lead to off-by-TZ-offset confusion. To export in your local timezone, "
            "enable Settings > Exports > Localize timestamps."
        ),
    },
    {
        "id": "KB-BUG-03",
        "title": "Mobile app crashes and recovery",
        "categories": [Category.BUG_REPORT],
        "body": (
            "If the iOS mobile app crashes immediately on a specific screen (settings, billing, "
            "team, notifications, macros) after an update, force-quit the app, clear "
            "background apps, and reopen. If the crash persists, your app version may be "
            "incompatible with a recent server-side change — update to the latest version from "
            "the App Store. App version 4.2.1 has a known crash on the macros screen, fixed in "
            "4.2.2. The drag-and-drop reorder bug on the macros settings page (changes don't "
            "persist on reload) is fixed in 4.2.2 as well."
        ),
    },
    {
        "id": "KB-BUG-04",
        "title": "Sync duplication and retry behavior",
        "categories": [Category.BUG_REPORT, Category.INTEGRATION],
        "body": (
            "When a CRM sync (Salesforce, HubSpot, Zapier) retries after a transient failure, "
            "an issue in the de-duplication logic could insert duplicates of already-synced "
            "records instead of skipping. This affected syncs running between specific dates "
            "and is now patched. To deduplicate after a known affected run, contact support "
            "with the run ID — we can run a server-side deduplication pass using the natural "
            "key (external_id where available, otherwise email + created_at)."
        ),
    },
]


def main() -> int:
    out = DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    # Validate via Pydantic before writing.
    articles = [KBArticle.model_validate(a) for a in ARTICLES]
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for a in articles:
            fh.write(json.dumps(a.model_dump(mode="json"), sort_keys=True))
            fh.write("\n")
    print(f"Wrote {len(articles)} articles to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
