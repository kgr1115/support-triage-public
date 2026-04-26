"""Generate the synthetic macro library: ~18 pre-canned reply templates.

Macros are response templates ('what the agent says'), distinct from KB articles
('what the product does'). They're embedded into the same FAISS index style for
top-k similarity-based suggestion.

The committed ``fixtures/synthetic/macros/macros.jsonl`` is the canonical artifact;
regenerate via ``make macros``.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.schemas import Category, Macro

DEFAULT_OUT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "macros" / "macros.jsonl"
)


MACROS: list[dict] = [
    # ---------------- LOGIN ----------------
    {
        "id": "MACRO-LOGIN-PASSWORD-RESET-DELIVERABILITY",
        "title": "Password reset email — deliverability checklist",
        "categories": [Category.LOGIN],
        "body": (
            "Sorry you're having trouble receiving the password reset email. A few "
            "things to check on your side: confirm the email isn't in your spam folder "
            "or any 'noreply' filter, whitelist no-reply@example.com in your mail "
            "provider, and verify the registered email address on your account is "
            "spelled correctly. Our system also rate-limits resets to one every 15 "
            "minutes; if you've requested several recently, please wait and try again. "
            "If none of that resolves it, an admin on your account can issue a magic "
            "link from the admin panel."
        ),
    },
    {
        "id": "MACRO-LOGIN-2FA-ADMIN-ASSIST",
        "title": "2FA / MFA lockout — admin can disable",
        "categories": [Category.LOGIN],
        "body": (
            "Sorry to hear you're locked out. The fastest path is to ask any admin on "
            "your workspace to disable 2FA on your account from the Team Members page; "
            "you can then sign in normally and re-enable 2FA from your profile. If your "
            "MFA codes were arriving and suddenly stopped, this is often a device-clock "
            "drift issue — please confirm your phone or authenticator is syncing time "
            "correctly. Let me know once you've reached an admin and we can confirm "
            "it's been disabled on our side."
        ),
    },
    {
        "id": "MACRO-LOGIN-SSO-CERT-ROTATION",
        "title": "SSO redirect loop — IdP cert rotation",
        "categories": [Category.LOGIN],
        "body": (
            "An SSO redirect loop right after an IdP update is almost always caused by "
            "a stale signing certificate on our side. Could you re-upload the new "
            "certificate in Workspace > SSO Settings, then ask affected users to clear "
            "cookies for both your IdP and our domain? If the issue continues after "
            "that, please share the timestamp of a recent failed login and the SAML "
            "response from your IdP debugger so we can dig in."
        ),
    },
    {
        "id": "MACRO-LOGIN-INVITE-TTL",
        "title": "Invite links expiring — TTL setting",
        "categories": [Category.LOGIN],
        "body": (
            "Invite links default to a 72-hour expiration, but workspaces can configure "
            "a shorter TTL. Could you check Workspace > Settings > Invitations and "
            "confirm the current setting? If the TTL has been shortened to a value "
            "like a few minutes, that would explain links showing 'expired' on first "
            "click. Once you've extended the TTL, please re-send the invites and let "
            "us know if the issue persists."
        ),
    },
    {
        "id": "MACRO-LOGIN-ACCOUNT-SUSPENDED",
        "title": "Account suspended despite current billing",
        "categories": [Category.LOGIN],
        "body": (
            "An 'account suspended' message while billing is current is usually our "
            "abuse-detection system flagging unusual activity, not a billing issue. "
            "Could you share your workspace ID and the time the suspension started? "
            "We can review and unsuspend within one business hour once we've confirmed "
            "the workspace isn't actually under abuse."
        ),
    },
    # ---------------- BILLING ----------------
    {
        "id": "MACRO-BILLING-DUPLICATE-CHARGE",
        "title": "Duplicate charge — refund process",
        "categories": [Category.BILLING],
        "body": (
            "Sorry about the duplicate charge — that's clearly not what should have "
            "happened. To process the refund, could you confirm the two charge dates "
            "and amounts as they appear on your statement, plus your account ID? "
            "Verified duplicate charges are refunded within 5–7 business days. We'll "
            "also review the underlying billing-system event to make sure it doesn't "
            "recur."
        ),
    },
    {
        "id": "MACRO-BILLING-AUTO-RENEWAL-CANCEL",
        "title": "Auto-renewal fired despite cancellation",
        "categories": [Category.BILLING],
        "body": (
            "Apologies that auto-renewal fired despite your cancellation request. "
            "Could you forward the cancellation confirmation email so we can verify "
            "the original request was completed? Once confirmed, we'll issue a refund "
            "within 5 business days and ensure the subscription is fully cancelled on "
            "our side. You should also see the cancelled state reflected in Billing > "
            "Subscription."
        ),
    },
    {
        "id": "MACRO-BILLING-INVOICE-MISSING",
        "title": "Invoice missing from billing portal",
        "categories": [Category.BILLING],
        "body": (
            "If a monthly invoice didn't appear in the billing portal despite a "
            "successful charge, the invoice was generated on our side but failed to "
            "attach to the portal. Could you share the billing month and the charge "
            "amount as it appears on your statement? Once we locate the record, we "
            "can re-issue the invoice to your portal within one business day."
        ),
    },
    {
        "id": "MACRO-BILLING-DISCOUNT-NOT-APPLIED",
        "title": "Discount code didn't apply at renewal",
        "categories": [Category.BILLING],
        "body": (
            "Discount codes can have restrictions — single-use, first-renewal-only, or "
            "plan-specific — that aren't always obvious from the code itself. Could "
            "you share the exact code and the affected renewal invoice? We'll check "
            "the code's eligibility against your renewal and refund the difference if "
            "the code should have applied. We can't stack multiple discounts on a "
            "single renewal."
        ),
    },
    # ---------------- INTEGRATION ----------------
    {
        "id": "MACRO-INT-WEBHOOK-DELIVERY-CHECK",
        "title": "Webhook subscription troubleshooting",
        "categories": [Category.INTEGRATION],
        "body": (
            "When webhook subscriptions stop firing, the most common causes are a "
            "paused subscription on our side or a receiver issue on yours. Could you: "
            "1) check Subscriptions > Status for the affected event type, and 2) "
            "verify your endpoint returns 200 to a curl test from outside your "
            "network? If both look healthy, please share a delivery ID from a recent "
            "expected event and we'll trace it through our delivery system."
        ),
    },
    {
        "id": "MACRO-INT-API-KEY-SCOPE",
        "title": "API key 403 — generate fresh admin key",
        "categories": [Category.INTEGRATION],
        "body": (
            "An admin-scoped API key returning 403 on specific endpoints usually means "
            "the key was narrowed to certain resource types when it was generated. "
            "The cleanest fix is to generate a fresh admin-scoped key from Settings > "
            "API and retry the call. If the new key also returns 403 on the affected "
            "endpoint, please share the request ID from the response headers so we "
            "can check the auth path."
        ),
    },
    {
        "id": "MACRO-INT-RATE-LIMITS",
        "title": "API rate limits by plan tier",
        "categories": [Category.INTEGRATION],
        "body": (
            "Rate limits scale with your plan: Starter 60 req/min, Growth 300, Pro "
            "600, Enterprise 1,000. If you're hitting 429s below your plan's "
            "documented limit, the most common cause is an API key generated under a "
            "previous plan tier — those inherit the old tier's limit until rotated. "
            "For high-volume sync, our batch endpoints (e.g. POST /v1/tickets/bulk) "
            "consume a single rate-limit token regardless of payload size."
        ),
    },
    {
        "id": "MACRO-INT-OAUTH-CONSENT-LOOP",
        "title": "OAuth consent loop — redirect URI",
        "categories": [Category.INTEGRATION],
        "body": (
            "OAuth apps cycling back to the consent screen typically have a redirect "
            "URI mismatch — even minor differences (trailing slash, http vs. https, "
            "casing) cause this. Could you compare the exact redirect URI registered "
            "for your OAuth app with the one your auth flow is using? If they match "
            "byte-for-byte and the issue persists, please share the OAuth app ID and "
            "we'll check our side."
        ),
    },
    {
        "id": "MACRO-INT-FIELD-MAPPING",
        "title": "Custom field mapping — type compatibility",
        "categories": [Category.INTEGRATION],
        "body": (
            "Silently dropped fields during sync usually mean a type mismatch between "
            "the source and destination, even when both sides have a field with the "
            "same name. Multi-select fields need an explicit list-of-strings mapping; "
            "lookup fields require the related object to be configured first; rollup "
            "and formula fields are read-only and can't be sync targets. Could you "
            "share the affected field name and its type on both sides?"
        ),
    },
    # ---------------- PRODUCT / FEATURE ----------------
    {
        "id": "MACRO-PROD-BULK-EXPORT",
        "title": "Bulk export — view-driven columns",
        "categories": [Category.FEATURE_REQUEST],
        "body": (
            "Bulk CSV export is available from any view via Actions > Export. The "
            "export includes the columns visible in the current view, so if you're "
            "missing columns in the export, customize the view first to add them and "
            "re-export. For very large exports, we recommend exporting in batches of "
            "a few thousand rows."
        ),
    },
    {
        "id": "MACRO-PROD-VIEWER-ROLE",
        "title": "Read-only viewer role availability",
        "categories": [Category.FEATURE_REQUEST],
        "body": (
            "A read-only viewer role is built into Pro and Enterprise plans — assign "
            "from Team Members > Role > Viewer. For more granular access (e.g. "
            "view-only on specific resources), custom roles can be defined in "
            "Settings > Roles on Enterprise. Let me know which combination of "
            "permissions you need and we can confirm whether a built-in or custom "
            "role fits."
        ),
    },
    {
        "id": "MACRO-PROD-FEATURE-ACK",
        "title": "Feature request — acknowledged and tracked",
        "categories": [Category.FEATURE_REQUEST],
        "body": (
            "Thanks for the suggestion — passing it to our product team. We log every "
            "request and weight by user impact, so context like the use case you "
            "described and the workaround you're using today is genuinely useful for "
            "prioritization. I can't commit to a timeline, but you'll hear from us "
            "if it lands on the roadmap."
        ),
    },
    # ---------------- BUGS ----------------
    {
        "id": "MACRO-BUG-DASHBOARD-MERGED",
        "title": "Dashboard double-count — merged tickets workaround",
        "categories": [Category.BUG_REPORT],
        "body": (
            "This is a known issue with our dashboard totals when a tag filter is "
            "applied — totals can double-count tickets that have been merged into "
            "others. The workaround is to toggle 'Include merged' off in your view "
            "settings, which will deduplicate the count. We're tracking the fix; "
            "I'll update this thread when it ships."
        ),
    },
    {
        "id": "MACRO-BUG-ESCALATE-WITH-REPRO",
        "title": "Bug confirmed — escalating with repro details",
        "categories": [Category.BUG_REPORT],
        "body": (
            "Thanks for the detailed repro — that helps. To make sure engineering can "
            "reproduce this, could you share: 1) your account ID, 2) the exact "
            "timestamp of a recent occurrence, and 3) the browser + OS you reproduced "
            "on? Once I have those, I'll file the bug and link the issue here so you "
            "can track it."
        ),
    },
]


def main() -> int:
    out = DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    macros = [Macro.model_validate(m) for m in MACROS]
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for m in macros:
            fh.write(json.dumps(m.model_dump(mode="json"), sort_keys=True))
            fh.write("\n")
    print(f"Wrote {len(macros)} macros to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
