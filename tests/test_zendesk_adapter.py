"""Tests for the Zendesk adapter at scripts/triage_zendesk_export.py.

These tests do NOT exercise the live /triage endpoint — they cover the
schema mapping (Zendesk shape → TriageRequest shape) and the file loader.
End-to-end exercise of the API happens in test_main.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.triage_zendesk_export import zendesk_to_triage_request

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "synthetic"
    / "zendesk_export_sample.json"
)


def test_sample_fixture_loads_and_has_tickets() -> None:
    """The committed sample export parses and contains at least one ticket."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "tickets" in payload
    assert isinstance(payload["tickets"], list)
    assert len(payload["tickets"]) > 0


def test_zendesk_to_triage_request_maps_required_fields() -> None:
    """Zendesk's `description` maps to `body`; `subject` maps directly."""
    zd_ticket = {
        "id": 12345,
        "subject": "SSO redirect loop",
        "description": "Half our team gets bounced back to Okta after login.",
        "status": "open",
        "priority": "high",
        "tags": ["sso", "okta"],
    }
    result = zendesk_to_triage_request(zd_ticket)
    assert result == {
        "subject": "SSO redirect loop",
        "body": "Half our team gets bounced back to Okta after login.",
    }


def test_zendesk_to_triage_request_drops_extra_fields() -> None:
    """Zendesk-only fields (id, status, tags, etc.) don't leak into the
    request — the /triage endpoint only accepts subject + body."""
    zd_ticket = {
        "id": 9001,
        "subject": "billing question",
        "description": "got charged twice",
        "status": "open",
        "tags": ["billing"],
        "custom_fields": [{"id": 1, "value": "pro_plan"}],
    }
    result = zendesk_to_triage_request(zd_ticket)
    assert set(result.keys()) == {"subject", "body"}


def test_zendesk_to_triage_request_missing_subject_raises() -> None:
    """A malformed Zendesk ticket without `subject` is a hard error — the
    adapter does not paper over schema mismatches."""
    zd_ticket = {"id": 1, "description": "body only, no subject"}
    with pytest.raises(KeyError):
        zendesk_to_triage_request(zd_ticket)


def test_sample_fixture_each_ticket_maps_cleanly() -> None:
    """Every ticket in the committed sample maps to a valid TriageRequest."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for ticket in payload["tickets"]:
        result = zendesk_to_triage_request(ticket)
        assert isinstance(result["subject"], str) and result["subject"].strip()
        assert isinstance(result["body"], str) and result["body"].strip()
