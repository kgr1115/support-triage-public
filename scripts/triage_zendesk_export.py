"""Triage a Zendesk-shaped ticket export.

Reads tickets from a Zendesk JSON export, POSTs each one to /triage, and
prints a one-line triage summary per ticket.

Reference adapter for forkers — shows how to map a real ticket-source
schema into the /triage endpoint's TriageRequest shape (subject + body).
Real Zendesk exports include many more fields (status, tags, requester_id,
custom_fields, etc.) — use them for filtering or post-processing as your
workflow needs.

Usage:
    # one terminal: start the dev server
    uv run python -m scripts.dev

    # another terminal: run the adapter against the sample export
    uv run python -m scripts.triage_zendesk_export fixtures/synthetic/zendesk_export_sample.json

    # or hit a non-default URL
    uv run python -m scripts.triage_zendesk_export your_export.json --api-url http://localhost:8001
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_API_URL = "http://localhost:8000"


def zendesk_to_triage_request(zd_ticket: dict[str, Any]) -> dict[str, str]:
    """Map a Zendesk ticket to the /triage endpoint's TriageRequest shape.

    Zendesk uses ``description`` for the ticket body; ``/triage`` uses ``body``.
    Subject maps directly. All other Zendesk fields are dropped — extend this
    function if your workflow needs them downstream.
    """
    return {
        "subject": zd_ticket["subject"],
        "body": zd_ticket["description"],
    }


def post_triage(payload: dict[str, str], api_url: str) -> dict[str, Any]:
    """POST to /triage and return the parsed JSON response."""
    request = urllib.request.Request(
        f"{api_url}/triage",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def triage_export(export_path: Path, api_url: str = DEFAULT_API_URL) -> int:
    """Read tickets from a Zendesk export JSON, triage each, print summary."""
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    tickets = payload.get("tickets", [])

    if not tickets:
        print(f"No tickets found in {export_path}", file=sys.stderr)
        return 1

    print(f"Triaging {len(tickets)} tickets via {api_url}/triage\n")

    errors = 0
    for zd_ticket in tickets:
        ticket_id = zd_ticket.get("id", "?")
        try:
            result = post_triage(zendesk_to_triage_request(zd_ticket), api_url)
        except urllib.error.URLError as exc:
            print(f"#{ticket_id}: ERROR — {exc}", file=sys.stderr)
            errors += 1
            continue
        except KeyError as exc:
            print(f"#{ticket_id}: ERROR — missing field {exc}", file=sys.stderr)
            errors += 1
            continue

        cls = result["classification"]
        top_kb = result["retrieved_kb"][0] if result["retrieved_kb"] else None

        print(f"#{ticket_id}: {zd_ticket.get('subject', '(no subject)')}")
        print(
            f"  classified: {cls['priority']} / {cls['category']} / {cls['sentiment']}"
        )
        if top_kb:
            print(
                f"  top KB:    {top_kb['id']} ({top_kb['title']}) score={top_kb['score']:.3f}"
            )
        print()

    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Triage a Zendesk-shaped ticket export against a running support-triage API."
    )
    parser.add_argument("export_path", type=Path, help="Path to Zendesk export JSON")
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Base URL of the running support-triage API (default: {DEFAULT_API_URL})",
    )
    args = parser.parse_args()

    if not args.export_path.exists():
        print(f"Export file not found: {args.export_path}", file=sys.stderr)
        return 1

    return triage_export(args.export_path, args.api_url)


if __name__ == "__main__":
    sys.exit(main())
