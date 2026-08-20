import json

import pytest

from careeros.privacy import scan_sensitive

SENSITIVE_SAMPLES = [
    ("github-token", "ghp_TEST_ONLY_NOT_A_SECRET"),
    ("api-key", "sk-TEST_ONLY_NOT_A_SECRET"),
    ("authorization-header", "Authorization: Bearer TEST_ONLY_TOKEN"),
    (
        "private-key",
        "-----BEGIN PRIVATE KEY-----\nTEST_ONLY\n-----END PRIVATE KEY-----",
    ),
    ("email", "engineer@example.test"),
]


@pytest.mark.parametrize(("category", "value"), SENSITIVE_SAMPLES)
def test_scan_sensitive_identifies_category_without_echoing_value(category: str, value: str) -> None:
    findings = scan_sensitive(f"before {value} after")

    assert len(findings) == 1
    assert findings[0].category == category
    assert json.dumps(
        [{"category": finding.category, "start": finding.start, "end": finding.end} for finding in findings]
    ).find(value) == -1


def test_scan_sensitive_returns_sorted_findings() -> None:
    text = "ghp_TEST_ONLY_NOT_A_SECRET and sk-TEST_ONLY_NOT_A_SECRET"
    findings = scan_sensitive(text)

    assert len(findings) == 2
    assert findings[0].start <= findings[1].start
