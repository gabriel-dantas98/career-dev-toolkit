import re
from dataclasses import dataclass

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        ),
    ),
    (
        "authorization-header",
        re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    ),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{12,}\b")),
    ("api-key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class PrivacyFinding:
    category: str
    start: int
    end: int


def scan_sensitive(text: str) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []

    for category, pattern in PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                PrivacyFinding(
                    category=category,
                    start=match.start(),
                    end=match.end(),
                )
            )

    return sorted(findings, key=lambda finding: finding.start)
