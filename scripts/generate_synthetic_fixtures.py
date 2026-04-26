"""Generate the deterministic synthetic fixture set: 200 labeled support tickets.

Templates + parameter substitution + a fixed RNG seed means this script produces
byte-identical output every run. The committed ``fixtures/synthetic/tickets.jsonl``
is the canonical artifact; regenerate via ``make fixtures``.

Each ticket scenario pairs a coherent subject + body — drawing the subject and
body independently produces ticket bodies that don't match their headers, which
cripples downstream classifier and retrieval evaluation. The Scenario type
enforces the pairing.

Future: an LLM-augmented mode (per CLAUDE.md) will replace template bodies with
generated text. For now, templates give us schema-valid, plausible diversity
without burning API tokens or requiring keys at install time.
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.fixtures import write_tickets
from app.schemas import Category, Priority, Sentiment, Ticket

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic" / "tickets.jsonl"
DEFAULT_COUNT_PER_CATEGORY = 40
DEFAULT_SEED = 42

# Generic placeholder pools shared by every category.
PLANS = ["Starter", "Growth", "Pro", "Enterprise"]
BROWSERS = ["Chrome 120", "Firefox 122", "Safari 17.2", "Edge 119"]
OSES = ["macOS 14.3", "Windows 11", "Ubuntu 22.04", "iOS 17.2", "Android 14"]
ACCOUNT_IDS = ["acct_8c4f", "acct_2b91", "acct_7a3e", "acct_d508", "acct_19fa", "acct_c2bd"]
TIMES = ["8:14 AM", "11:30 AM", "2:47 PM", "4:02 PM", "9:18 PM"]
TEAM_SIZES = ["12", "30", "75", "200", "450"]


@dataclass
class Scenario:
    """A coherent (subject, body) pair with fixed labels chosen to match the text tone.

    Priority and sentiment are scenario-level (not sampled) so the labels are actually
    derivable from the text — the classifier eval would otherwise be measuring noise.
    """

    subject: str
    body: str
    priority: Priority
    sentiment: Sentiment
    placeholders: dict[str, Sequence[str]] = field(default_factory=dict)


@dataclass
class CategorySpec:
    category: Category
    scenarios: list[Scenario]
    shared_placeholders: dict[str, Sequence[str]]


# ---------------- LOGIN ----------------
LOGIN = CategorySpec(
    category=Category.LOGIN,
    shared_placeholders={
        "plan": PLANS,
        "browser": BROWSERS,
        "os": OSES,
        "account_id": ACCOUNT_IDS,
        "time": TIMES,
        "team_size": TEAM_SIZES,
    },
    scenarios=[
        Scenario(
            subject="Can't log in — '{error}' even after password reset",
            body=(
                "Hi team, I tried to log in at {time} and got '{error}'. Already cleared cookies, "
                "tried incognito, and reset my password twice. Plan: {plan}. Browser: {browser}. "
                "Account: {account_id}. Can someone unblock me?"
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.FRUSTRATED,
            placeholders={
                "error": [
                    "invalid credentials",
                    "user not found",
                    "too many attempts",
                    "account suspended",
                ],
            },
        ),
        Scenario(
            subject="SSO redirect loop after {idp} update",
            body=(
                "Started this morning — every login attempt redirects me through {idp} and back "
                "to the sign-in page in a loop. Browser console shows nothing useful. {plan} "
                "customer, account {account_id}. Worked fine yesterday before the {idp} update."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"idp": ["Okta", "Azure AD", "Google Workspace", "OneLogin", "Auth0"]},
        ),
        Scenario(
            subject="Locked out after enabling 2FA — recovery codes don't work",
            body=(
                "I enabled 2FA last week and now I'm locked out. The recovery codes I saved also "
                "return 'invalid'. This is blocking my whole team ({team_size} people on the "
                "{plan} plan). Need this resolved today. Account: {account_id}."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.FRUSTRATED,
        ),
        Scenario(
            subject="MFA codes never arrive on my {device}",
            body=(
                "MFA codes aren't reaching my {device}. I've waited 10+ minutes and refreshed. "
                "This started after I switched carriers last week. Browser: {browser}. "
                "Account: {account_id}, {plan} plan."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"device": ["phone (SMS)", "Authenticator app", "hardware key (YubiKey)"]},
        ),
        Scenario(
            subject="Password reset email never received (checked spam)",
            body=(
                "Reset my password three times in the last hour. None of the reset emails arrive. "
                "Other emails from your domain do reach me. Account: {account_id}. Registered "
                "email is on Gmail. {plan} plan."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Session expires every {minutes} minutes — was hourly before",
            body=(
                "Logged in from {os} on {browser} and now my session terminates after about "
                "{minutes} minutes of activity. Other team members on the same {plan} plan "
                "aren't seeing this. Account: {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"minutes": ["3", "5", "10", "15"]},
        ),
        Scenario(
            subject="Login page returns 500 on {browser}",
            body=(
                "The login page returns a 500 error on {browser} (works on {alt_browser}). I'm "
                "on {os}. Account: {account_id}, {plan} plan. Started about an hour ago."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"alt_browser": BROWSERS},
        ),
        Scenario(
            subject="'Account suspended' message but billing is current",
            body=(
                "Got an 'account suspended' message at login this morning. Billing portal shows "
                "we're paid through next quarter on the {plan} plan. Account: {account_id}. "
                "This is blocking {team_size} users."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.FRUSTRATED,
        ),
        Scenario(
            subject="SAML assertion rejected with no error detail",
            body=(
                "Our SAML login fails with 'assertion rejected' — the {idp} side reports a "
                "successful POST but your IdP-initiated flow rejects it. No detail in our logs. "
                "{plan} plan, account {account_id}. Started after we rotated our signing cert."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"idp": ["Okta", "Azure AD", "OneLogin"]},
        ),
        Scenario(
            subject="Magic link login keeps cycling back to sign-in",
            body=(
                "Click the magic link in my email, get redirected to your domain, then sent "
                "back to the sign-in screen. Repro on {browser} and {alt_browser}. Account: "
                "{account_id}, {plan} plan."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"alt_browser": BROWSERS},
        ),
        Scenario(
            subject="New users can't accept invite — link expired immediately",
            body=(
                "Sent {team_size} invites this morning. Every recipient reports the invite link "
                "shows 'expired' on first click. Resending produces the same result. {plan}, "
                "account {account_id}."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.NEGATIVE,
        ),
    ],
)

# ---------------- BILLING ----------------
BILLING = CategorySpec(
    category=Category.BILLING,
    shared_placeholders={
        "plan": PLANS,
        "account_id": ACCOUNT_IDS,
        "amount": ["499", "1,299", "2,400", "4,800", "12,000", "24,500"],
        "expected": ["399", "999", "1,800", "3,600", "9,000", "18,000"],
        "month": ["March", "April", "May", "June", "July", "August"],
        "date": ["April 3", "April 12", "March 28", "February 15", "May 1"],
        "seats": ["5", "12", "25", "50", "100", "250"],
    },
    scenarios=[
        Scenario(
            subject="Charged twice for {plan} plan in {month}",
            body=(
                "We were charged ${amount} on {date} and again on {date2} for the same {plan} "
                "billing period. Account {account_id}, {seats} seats. Please refund the duplicate "
                "and confirm there isn't an underlying billing-system issue."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"date2": ["April 5", "April 14", "March 30", "February 17", "May 3"]},
        ),
        Scenario(
            subject="Annual renewal billed at wrong rate — expected ${expected}, charged ${amount}",
            body=(
                "Our {plan} renewal hit the card today for ${amount}, which is the new pricing. "
                "We were grandfathered at ${expected} when we signed in {prior_year}. Email from "
                "sales confirming this is on file. Account {account_id}, {seats} seats."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"prior_year": ["2023", "2024", "2025"]},
        ),
        Scenario(
            subject="Pro-rated upgrade charge looks wrong",
            body=(
                "Upgraded from {old_plan} to {plan} mid-cycle on {date}. Pro-rated charge came "
                "in at ${amount} but my math says it should be ${expected}. Account {account_id}, "
                "{seats} seats. Can someone walk through the calc with me?"
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={"old_plan": PLANS},
        ),
        Scenario(
            subject="Refund for cancelled seats not yet processed",
            body=(
                "Cancelled {seats} seats on {date}. The downgrade is reflected in the admin "
                "panel, but the {month} invoice still shows the full count and we were charged "
                "${amount}. Account: {account_id}, {plan} plan. Please refund the difference."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="{month} invoice missing from billing portal",
            body=(
                "The {month} invoice never appeared in the billing portal. Finance needs it "
                "for monthly close. Account {account_id}, {plan} plan. We were charged "
                "${amount} per the card statement so the bill clearly went out."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
        ),
        Scenario(
            subject="Tax line item incorrect for {country}",
            body=(
                "Tax on our last {country} invoice shows {tax_pct}% but the local VAT rate is "
                "different. Finance flagged it during reconciliation. Need a corrected invoice "
                "for {month}. Account {account_id}, {plan}, ${amount} total."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={
                "country": ["UK", "DE", "FR", "AU", "CA", "JP"],
                "tax_pct": ["7.5", "10", "15", "19", "20"],
            },
        ),
        Scenario(
            subject="Auto-renewal occurred despite cancellation request",
            body=(
                "Auto-renewal fired on {date} for ${amount} despite a cancellation request "
                "submitted on {prev_date} (confirmation email in my inbox). Please refund and "
                "confirm the {plan} subscription on {account_id} is actually cancelled."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"prev_date": ["March 20", "April 1", "March 14", "February 28"]},
        ),
        Scenario(
            subject="Failed payment but card is valid",
            body=(
                "Got a 'payment failed' email on {date} for our {plan} renewal. Card is valid, "
                "has plenty of available credit, and the bank shows no decline attempt. {seats} "
                "seats, account {account_id}, ${amount}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Need to update billing address on {month} invoice",
            body=(
                "We moved offices and the address on the {month} invoice is wrong. Updated it "
                "in the billing portal but the issued invoice still has the old one. Need a "
                "reissue for {plan} plan, account {account_id}, ${amount}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.NEUTRAL,
        ),
        Scenario(
            subject="Discount code not applied to renewal",
            body=(
                "The {discount}% off code from our renewal email didn't apply — charged the "
                "full ${amount} on {date} instead of the discounted rate. Account {account_id}, "
                "{plan}, {seats} seats."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"discount": ["10", "15", "20", "25"]},
        ),
        Scenario(
            subject="Need to switch from monthly to annual billing",
            body=(
                "We'd like to switch from monthly to annual on the {plan} plan to lock in the "
                "discount. Currently {seats} seats on account {account_id}. Can you confirm "
                "the proration and effective date?"
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.POSITIVE,
        ),
        Scenario(
            subject="ACH payment method not accepted at checkout",
            body=(
                "Trying to pay our {month} invoice (${amount}) via ACH but the payment method "
                "selector only shows credit cards. {plan} plan, account {account_id}, US-based. "
                "Sales told us ACH was available."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
        ),
    ],
)

# ---------------- INTEGRATION ----------------
INTEGRATION = CategorySpec(
    category=Category.INTEGRATION,
    shared_placeholders={
        "plan": PLANS,
        "account_id": ACCOUNT_IDS,
        "integration": [
            "Salesforce",
            "HubSpot",
            "Slack",
            "Zapier",
            "Zendesk",
            "Jira",
            "GitHub",
            "Okta",
            "Segment",
        ],
    },
    scenarios=[
        Scenario(
            subject="Webhook not firing for {event} events",
            body=(
                "Webhook subscriptions for {event} aren't firing. Verified the endpoint is "
                "reachable (returns 200 to curl). Last successful delivery was {hours_ago} hours "
                "ago. {plan} plan, account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "event": [
                    "ticket.created",
                    "ticket.updated",
                    "user.created",
                    "subscription.cancelled",
                    "payment.failed",
                ],
                "hours_ago": ["6", "12", "18", "24", "36"],
            },
        ),
        Scenario(
            subject="API key returns 403 on {endpoint} despite admin scope",
            body=(
                "Our admin-scoped API key returns 403 on {endpoint}. The same key works on "
                "{other_endpoint}. Generated a fresh admin key — same result. {plan} plan, "
                "account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEUTRAL,
            placeholders={
                "endpoint": ["/v1/tickets", "/v1/users", "/v1/macros", "/v1/audit_log"],
                "other_endpoint": ["/v1/me", "/v1/whoami", "/v1/health"],
            },
        ),
        Scenario(
            subject="{integration} connector stuck on 'connecting…'",
            body=(
                "Setting up the {integration} integration on a {plan} plan and the connection "
                "status stays at 'connecting' indefinitely. Followed the docs end to end. Logs "
                "show: '{log_snippet}'. Account: {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "log_snippet": [
                    "401 unauthorized",
                    "connection refused",
                    "rate_limit_exceeded",
                    "invalid_grant",
                    "OAuth state mismatch",
                ],
            },
        ),
        Scenario(
            subject="Slack integration posts to wrong channel",
            body=(
                "Configured the Slack integration to post to #support-alerts but messages are "
                "landing in #general. Re-authorized twice. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Zapier zap fails with 'invalid payload' on {event}",
            body=(
                "Our Zapier zap watching {event} fails with 'invalid payload' on every trigger. "
                "Payload from your side validates against your published schema. {plan} plan, "
                "account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "event": [
                    "ticket.created",
                    "ticket.updated",
                    "user.created",
                    "deal.closed_won",
                ],
            },
        ),
        Scenario(
            subject="Custom OAuth app stuck at consent screen",
            body=(
                "Building a custom OAuth app against your API. Clicking 'Allow' on the consent "
                "screen redirects back to consent rather than completing the flow. Same on "
                "{browser} and {alt_browser}. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"browser": BROWSERS, "alt_browser": BROWSERS},
        ),
        Scenario(
            subject="Rate limited at {rate} req/min on {plan} — docs say {expected_rate}",
            body=(
                "We're hitting 429s at {rate} req/min on {plan}. Docs say the limit is "
                "{expected_rate}/min. This is blocking our nightly sync. Account: {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.FRUSTRATED,
            placeholders={
                "rate": ["60", "100", "120"],
                "expected_rate": ["300", "600", "1000"],
            },
        ),
        Scenario(
            subject="Outbound webhook delivery times out at {timeout}s",
            body=(
                "Our webhook receiver responds in {response_ms}ms reliably but your delivery "
                "system reports timeouts at {timeout}s. Receiver logs show the request never "
                "arriving on retries. {plan}, account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEUTRAL,
            placeholders={
                "timeout": ["10", "15", "30"],
                "response_ms": ["80", "120", "200", "350"],
            },
        ),
        Scenario(
            subject="{integration} sync drops the '{field}' field silently",
            body=(
                "Custom field mapping in {integration} drops the '{field}' field on every sync. "
                "Field exists on both sides with matching types. No errors in the sync log. "
                "{plan} plan, account {account_id}."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "field": ["account_owner", "renewal_date", "external_id", "custom_segment"],
            },
        ),
        Scenario(
            subject="Help mapping custom fields between {integration} and your API",
            body=(
                "Our team is wiring up {integration} → your API and we're stuck on mapping "
                "custom fields with non-standard types ({field_type}). Docs cover string and "
                "number but not this case. {plan}, account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.NEUTRAL,
            placeholders={
                "field_type": ["multi-select", "lookup", "rollup", "formula"],
            },
        ),
        Scenario(
            subject="Webhook signature verification failing intermittently",
            body=(
                "About 1 in {ratio} webhook deliveries fail signature verification on our side. "
                "Using HMAC-SHA256 per docs. Same secret across all retries. {plan}, account "
                "{account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={"ratio": ["20", "50", "100"]},
        ),
        Scenario(
            subject="OAuth refresh token expires before documented TTL",
            body=(
                "Refresh tokens for our {integration} integration expire after {actual_days} "
                "days, but the docs say {documented_days}. We have to re-auth users repeatedly. "
                "{plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "actual_days": ["7", "14", "30"],
                "documented_days": ["60", "90", "365"],
            },
        ),
    ],
)

# ---------------- FEATURE REQUEST ----------------
FEATURE_REQUEST = CategorySpec(
    category=Category.FEATURE_REQUEST,
    shared_placeholders={
        "plan": PLANS,
        "account_id": ACCOUNT_IDS,
        "competitor": ["Intercom", "Front", "Help Scout", "Zendesk"],
    },
    scenarios=[
        Scenario(
            subject="Bulk export to CSV from the {view} view",
            body=(
                "We need bulk CSV export from the {view} view. Right now we have to export "
                "individual records one at a time, which doesn't scale past {scale}. {plan} "
                "plan, account {account_id}. Happy to share our use case in detail."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={
                "view": ["dashboard", "tickets", "analytics", "audit log", "team management"],
                "scale": ["~50 records", "a few hundred", "a few thousand", "our actual volume"],
            },
        ),
        Scenario(
            subject="Add a '{role}' role that can view but not edit",
            body=(
                "Could you add a '{role}' role that can view dashboards but not edit anything? "
                "We have stakeholders who need read-only access but the only option today is full "
                "member. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={"role": ["viewer", "auditor", "stakeholder", "read-only"]},
        ),
        Scenario(
            subject="Dark mode for the admin panel",
            body=(
                "Wishlist: dark mode for the admin panel. Our agents work long shifts and the "
                "current bright theme is rough on the eyes. Not blocking — would just be a nice "
                "polish. {plan}, account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.POSITIVE,
        ),
        Scenario(
            subject="Webhook retries with exponential backoff",
            body=(
                "Feature request: configurable retry policy on outbound webhooks (exponential "
                "backoff, max attempts). Right now a brief receiver outage means we lose the "
                "delivery entirely. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
        ),
        Scenario(
            subject="Filter saved views by team membership",
            body=(
                "Would love to filter saved views by team. We have {team_count} teams and the "
                "view picker is unwieldy when each team's views are mixed in. {plan} plan, "
                "account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.NEUTRAL,
            placeholders={"team_count": ["5", "12", "25", "40"]},
        ),
        Scenario(
            subject="Slack notifications for {event}",
            body=(
                "Could you add native Slack notifications for {event}? We've built a Zapier "
                "workaround but it's flaky and adds latency. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={
                "event": [
                    "high-priority ticket created",
                    "SLA breach imminent",
                    "ticket assigned to me",
                    "ticket reopened",
                ],
            },
        ),
        Scenario(
            subject="Custom date ranges in the analytics view",
            body=(
                "The analytics view only supports preset ranges (7d / 30d / 90d). We do "
                "monthly business reviews and need custom ranges to align with our fiscal "
                "calendar. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
        ),
        Scenario(
            subject="Audit log export endpoint for SOC 2 compliance",
            body=(
                "Our compliance team is asking for an audit log export ahead of our SOC 2 "
                "audit in {timeline}. Currently it's UI-only. Without it we'll need to scrape, "
                "which is fragile. {plan}, account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"timeline": ["Q3", "November", "next quarter", "before EOY"]},
        ),
        Scenario(
            subject="Bulk reassign {entity} across teams",
            body=(
                "Need a bulk reassign for {entity} across teams. We're reorganizing and have "
                "to move {volume} items by hand. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "entity": ["tickets", "macros", "users", "tags"],
                "volume": ["a few hundred", "a few thousand", "tens of thousands"],
            },
        ),
        Scenario(
            subject="API endpoint for {entity} that today is UI-only",
            body=(
                "We're evaluating {competitor} primarily because they expose {entity} via API "
                "and you don't. We'd much rather stay — we like the rest of your product. "
                "{plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEUTRAL,
            placeholders={"entity": ["macros", "saved views", "team membership", "tags"]},
        ),
        Scenario(
            subject="Tag-based access control",
            body=(
                "Wishlist: ACLs based on tags. We have sensitive accounts that should only be "
                "visible to a subset of agents. Today we're using a clunky workaround with "
                "private views. {plan}, account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.NEUTRAL,
        ),
        Scenario(
            subject="Multi-workspace switcher in the top nav",
            body=(
                "We have separate workspaces for our two product lines. Switching means "
                "logging out and back in. A workspace switcher (like Slack's) would save us "
                "{hours}/week. {plan}, account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.POSITIVE,
            placeholders={"hours": ["3 hours", "5 hours", "8 hours"]},
        ),
    ],
)

# ---------------- BUG REPORT ----------------
BUG_REPORT = CategorySpec(
    category=Category.BUG_REPORT,
    shared_placeholders={
        "plan": PLANS,
        "account_id": ACCOUNT_IDS,
        "browser": BROWSERS,
        "os": OSES,
    },
    scenarios=[
        Scenario(
            subject="Dashboard totals double-count merged tickets",
            body=(
                "Repro: 1) open the dashboard, 2) apply any tag filter, 3) compare the totals "
                "header to the actual count of cards. Totals are exactly 2× the count. We "
                "checked — the doubled rows are tickets that were merged. {browser} on {os}, "
                "{plan}, account {account_id}."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Search returns empty results for tags containing a hyphen",
            body=(
                "Repro: 1) search for any tag with a hyphen (e.g. 'vip-customer'), 2) observe "
                "empty results. Tag exists. Same query without hyphen works. {browser} on {os}, "
                "{plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="CSV export missing the '{column}' column",
            body=(
                "The CSV export from the tickets view is missing the '{column}' column despite "
                "it being visible in the UI. Repro on {browser} and {alt_browser}. {plan}, "
                "account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "column": [
                    "created_at",
                    "assignee_email",
                    "tag_list",
                    "external_id",
                    "first_response_at",
                ],
                "alt_browser": BROWSERS,
            },
        ),
        Scenario(
            subject="Mobile app crashes on the {screen} screen",
            body=(
                "iOS app crashes the moment I open the {screen} screen. Reproduces every time. "
                "App version {app_version}, iOS 17.2. Crash happened immediately after the "
                "{date} update. {plan}, account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.FRUSTRATED,
            placeholders={
                "screen": ["settings", "billing", "team", "notifications", "macros"],
                "app_version": ["4.2.1", "4.2.2", "4.3.0"],
                "date": ["April 18", "April 22", "April 24"],
            },
        ),
        Scenario(
            subject="CSV export timestamps off by user's TZ offset",
            body=(
                "Timestamps in the CSV export are 8 hours off from what the UI shows. Looks "
                "like the export is in UTC but the column is named the same as the UI's "
                "localized one. {plan} plan, {browser} on {os}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Drag-and-drop reorder on settings page doesn't persist",
            body=(
                "Reorder rows on the macros settings page via drag-and-drop, see the new order "
                "snap into place, reload the page — old order is back. No errors in console. "
                "{browser} on {os}. {plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Chart legend overlaps data on viewports under {width}px",
            body=(
                "On laptop screens (< {width}px wide) the analytics chart legend overlaps the "
                "right ~20% of the data. Resizing wider fixes it. {browser} on {os}, {plan}, "
                "account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"width": ["1280", "1366", "1440"]},
        ),
        Scenario(
            subject="Bulk reassign 'completes' but reassignments revert on reload",
            body=(
                "Bulk-select {n} tickets, reassign them, get the success toast, reload — "
                "original assignees are back. No errors. Looks like the write isn't persisting. "
                "{browser} on {os}. {plan}, account {account_id}."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"n": ["50", "100", "500", "1,000"]},
        ),
        Scenario(
            subject="{integration} sync duplicates records on retry",
            body=(
                "When the {integration} sync retries after a transient failure, it inserts a "
                "duplicate of every already-synced record instead of skipping. Caught it at "
                "{n} duplicates this morning. {plan}, account {account_id}."
            ),
            priority=Priority.URGENT,
            sentiment=Sentiment.NEGATIVE,
            placeholders={
                "integration": ["Salesforce", "HubSpot", "Zapier"],
                "n": ["50", "100", "500", "1,000"],
            },
        ),
        Scenario(
            subject="Notification badge never clears after reading",
            body=(
                "The unread notification badge stays on '12' regardless of how many I read. "
                "Logging out and back in clears it. Started after the {date} release. "
                "{browser} on {os}, {plan}, account {account_id}."
            ),
            priority=Priority.LOW,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"date": ["April 18", "April 22", "April 24"]},
        ),
        Scenario(
            subject="Audit log shows wrong actor on bulk operations",
            body=(
                "Audit log entries for bulk operations show the actor as 'system' instead of "
                "the agent who performed them. Single-record operations are correct. "
                "Compliance flagged this. {plan}, account {account_id}."
            ),
            priority=Priority.HIGH,
            sentiment=Sentiment.NEGATIVE,
        ),
        Scenario(
            subject="Saved view filters don't persist after browser restart",
            body=(
                "Save a view with several filters applied, close the browser, come back — the "
                "view loads with the filters cleared. Repro on {browser} and {alt_browser}. "
                "{plan}, account {account_id}."
            ),
            priority=Priority.NORMAL,
            sentiment=Sentiment.NEGATIVE,
            placeholders={"alt_browser": BROWSERS},
        ),
    ],
)


CATEGORIES: list[CategorySpec] = [LOGIN, BILLING, INTEGRATION, FEATURE_REQUEST, BUG_REPORT]


# Ground-truth mapping: scenario subject template -> list of relevant KB article IDs.
# The retrieval eval uses this to compute recall@k. Scenarios with no clear KB match
# get an empty list and are skipped from the retrieval eval.
SCENARIO_KB_MAP: dict[str, list[str]] = {
    # LOGIN
    "Can't log in — '{error}' even after password reset": ["KB-LOGIN-03", "KB-LOGIN-05"],
    "SSO redirect loop after {idp} update": ["KB-LOGIN-01"],
    "Locked out after enabling 2FA — recovery codes don't work": ["KB-LOGIN-02"],
    "MFA codes never arrive on my {device}": ["KB-LOGIN-02"],
    "Password reset email never received (checked spam)": ["KB-LOGIN-03"],
    "Session expires every {minutes} minutes — was hourly before": ["KB-LOGIN-04"],
    "Login page returns 500 on {browser}": ["KB-LOGIN-05"],
    "'Account suspended' message but billing is current": ["KB-LOGIN-05"],
    "SAML assertion rejected with no error detail": ["KB-LOGIN-01"],
    "Magic link login keeps cycling back to sign-in": ["KB-LOGIN-04"],
    "New users can't accept invite — link expired immediately": ["KB-LOGIN-04"],
    # BILLING
    "Charged twice for {plan} plan in {month}": ["KB-BILL-01"],
    "Annual renewal billed at wrong rate — expected ${expected}, charged ${amount}": [
        "KB-BILL-01",
        "KB-BILL-06",
    ],
    "Pro-rated upgrade charge looks wrong": ["KB-BILL-02"],
    "Refund for cancelled seats not yet processed": ["KB-BILL-03"],
    "{month} invoice missing from billing portal": ["KB-BILL-04"],
    "Tax line item incorrect for {country}": ["KB-BILL-04"],
    "Auto-renewal occurred despite cancellation request": ["KB-BILL-03"],
    "Failed payment but card is valid": ["KB-BILL-05"],
    "Need to update billing address on {month} invoice": ["KB-BILL-04"],
    "Discount code not applied to renewal": ["KB-BILL-06"],
    "Need to switch from monthly to annual billing": ["KB-BILL-02"],
    "ACH payment method not accepted at checkout": ["KB-BILL-05"],
    # INTEGRATION
    "Webhook not firing for {event} events": ["KB-INT-01"],
    "API key returns 403 on {endpoint} despite admin scope": ["KB-INT-02"],
    "{integration} connector stuck on 'connecting…'": ["KB-INT-05"],
    "Slack integration posts to wrong channel": ["KB-INT-04"],
    "Zapier zap fails with 'invalid payload' on {event}": ["KB-INT-01", "KB-INT-05"],
    "Custom OAuth app stuck at consent screen": ["KB-INT-02"],
    "Rate limited at {rate} req/min on {plan} — docs say {expected_rate}": ["KB-INT-03"],
    "Outbound webhook delivery times out at {timeout}s": ["KB-INT-01"],
    "{integration} sync drops the '{field}' field silently": ["KB-INT-06"],
    "Help mapping custom fields between {integration} and your API": ["KB-INT-06"],
    "Webhook signature verification failing intermittently": ["KB-INT-01"],
    "OAuth refresh token expires before documented TTL": ["KB-INT-02"],
    # FEATURE_REQUEST
    "Bulk export to CSV from the {view} view": ["KB-PROD-01"],
    "Add a '{role}' role that can view but not edit": ["KB-PROD-02"],
    "Dark mode for the admin panel": [],  # no clear KB match
    "Webhook retries with exponential backoff": ["KB-INT-01"],
    "Filter saved views by team membership": ["KB-PROD-03"],
    "Slack notifications for {event}": ["KB-INT-04"],
    "Custom date ranges in the analytics view": ["KB-PROD-04"],
    "Audit log export endpoint for SOC 2 compliance": ["KB-PROD-05"],
    "Bulk reassign {entity} across teams": ["KB-PROD-01"],
    "API endpoint for {entity} that today is UI-only": [],  # generic, no clear match
    "Tag-based access control": ["KB-PROD-02"],
    "Multi-workspace switcher in the top nav": [],  # no clear KB match
    # BUG_REPORT
    "Dashboard totals double-count merged tickets": ["KB-BUG-01", "KB-PROD-04"],
    "Search returns empty results for tags containing a hyphen": ["KB-BUG-01", "KB-PROD-03"],
    "CSV export missing the '{column}' column": ["KB-BUG-02"],
    "Mobile app crashes on the {screen} screen": ["KB-BUG-03"],
    "CSV export timestamps off by user's TZ offset": ["KB-BUG-02"],
    "Drag-and-drop reorder on settings page doesn't persist": ["KB-BUG-03"],
    "Chart legend overlaps data on viewports under {width}px": [],  # cosmetic, no KB match
    "Bulk reassign 'completes' but reassignments revert on reload": ["KB-PROD-01"],
    "{integration} sync duplicates records on retry": ["KB-BUG-04"],
    "Notification badge never clears after reading": [],  # no KB match
    "Audit log shows wrong actor on bulk operations": ["KB-PROD-05"],
    "Saved view filters don't persist after browser restart": ["KB-PROD-03"],
}


def _resolve_bindings(
    templates: list[str], placeholders: dict[str, Sequence[str]], rng: random.Random
) -> dict[str, str]:
    """Pick one value per referenced placeholder key, shared across all templates in the group.

    Resolving once per ticket (rather than per template) keeps a ticket internally consistent —
    e.g. ``{endpoint}`` in the subject matches ``{endpoint}`` in the body.

    Unknown keys raise KeyError — that signals a template authoring bug.
    """
    bindings: dict[str, str] = {}
    for tmpl in templates:
        i = 0
        while i < len(tmpl):
            start = tmpl.find("{", i)
            if start < 0:
                break
            end = tmpl.find("}", start)
            if end < 0:
                break
            key = tmpl[start + 1 : end]
            if key not in placeholders:
                raise KeyError(f"Template references undefined placeholder: {{{key}}}")
            if key not in bindings:
                bindings[key] = rng.choice(list(placeholders[key]))
            i = end + 1
    return bindings


def _apply(template: str, bindings: dict[str, str]) -> str:
    out = template
    while True:
        start = out.find("{")
        if start < 0:
            return out
        end = out.find("}", start)
        if end < 0:
            return out
        key = out[start + 1 : end]
        out = out[:start] + bindings[key] + out[end + 1 :]


def _validate_kb_map() -> None:
    """Every scenario must appear in SCENARIO_KB_MAP — empty list is fine, missing key is not.

    This catches typos in scenario subjects that would otherwise silently produce
    untruthed tickets in the retrieval eval.
    """
    expected = {s.subject for spec in CATEGORIES for s in spec.scenarios}
    declared = set(SCENARIO_KB_MAP.keys())
    missing = expected - declared
    extra = declared - expected
    if missing:
        raise RuntimeError(
            f"SCENARIO_KB_MAP missing entries for scenario subjects: {sorted(missing)}"
        )
    if extra:
        raise RuntimeError(
            f"SCENARIO_KB_MAP has stale entries (no matching scenario): {sorted(extra)}"
        )


def generate(
    count_per_category: int = DEFAULT_COUNT_PER_CATEGORY, seed: int = DEFAULT_SEED
) -> list[Ticket]:
    """Generate ``count_per_category`` unique tickets per category, deterministically."""
    _validate_kb_map()
    rng = random.Random(seed)
    tickets: list[Ticket] = []

    for spec in CATEGORIES:
        seen: set[tuple[str, str]] = set()
        attempts = 0
        max_attempts = count_per_category * 100
        while len(seen) < count_per_category:
            attempts += 1
            if attempts > max_attempts:
                raise RuntimeError(
                    f"Could not generate {count_per_category} unique tickets for "
                    f"{spec.category.value} after {max_attempts} attempts — broaden templates."
                )
            scenario = rng.choice(spec.scenarios)
            merged = {**spec.shared_placeholders, **scenario.placeholders}
            bindings = _resolve_bindings([scenario.subject, scenario.body], merged, rng)
            subject = _apply(scenario.subject, bindings)
            body = _apply(scenario.body, bindings)
            key = (subject, body)
            if key in seen:
                continue
            seen.add(key)

            ticket_id = f"{spec.category.value}-{len(seen):03d}"
            tickets.append(
                Ticket(
                    id=ticket_id,
                    subject=subject,
                    body=body,
                    priority=scenario.priority,
                    category=spec.category,
                    sentiment=scenario.sentiment,
                    relevant_kb_ids=list(SCENARIO_KB_MAP.get(scenario.subject, [])),
                )
            )

    return tickets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSONL path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--count-per-category",
        type=int,
        default=DEFAULT_COUNT_PER_CATEGORY,
        help=f"Tickets per category (default: {DEFAULT_COUNT_PER_CATEGORY})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"RNG seed for reproducibility (default: {DEFAULT_SEED})",
    )
    args = parser.parse_args()

    tickets = generate(count_per_category=args.count_per_category, seed=args.seed)
    write_tickets(tickets, args.out)
    print(f"Wrote {len(tickets)} tickets to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
