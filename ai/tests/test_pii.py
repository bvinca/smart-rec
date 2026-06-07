# pii redactor tests (runs before llm calls)

from __future__ import annotations

from ai.ai_utils.pii import redact_pii


def test_email_phone_url_address_redacted():
    text = (
        "Contact: jane.doe@example.com or +44 20 7946 0958. "
        "Portfolio: https://janedoe.dev. Lives at 221B Baker Street, London NW1 6XE."
    )
    redacted = redact_pii(text)
    assert "[EMAIL]" in redacted
    assert "[PHONE]" in redacted
    assert "[URL]" in redacted
    assert "[ADDRESS]" in redacted
    assert "[POSTCODE]" in redacted


def test_candidate_name_replaced():
    text = "Jane Doe is a senior engineer. Jane Doe led the platform team."
    redacted = redact_pii(text, candidate_names=["Jane Doe"])
    assert "Jane Doe" not in redacted
    assert "[NAME]" in redacted


def test_short_string_does_not_crash():
    assert redact_pii("") == ""
    assert redact_pii(None) is None  # type: ignore[arg-type]
