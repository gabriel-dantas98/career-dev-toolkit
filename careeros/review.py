from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from careeros.models import DeliveryRecord

_TOKEN = re.compile(r"[a-z0-9]+")
_CLAIM_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "before",
        "com",
        "das",
        "dos",
        "for",
        "from",
        "para",
        "that",
        "the",
        "this",
        "uma",
        "with",
    }
)


@dataclass(frozen=True)
class ReviewFinding:
    rule_id: str
    record_id: str
    field: str
    message: str


@dataclass(frozen=True)
class LeaderReview:
    findings: tuple[ReviewFinding, ...]


def leader_review(records: Sequence[DeliveryRecord]) -> LeaderReview:
    findings: list[ReviewFinding] = []
    for record in records:
        evidence_links = tuple(
            evidence.locator.strip()
            for evidence in record.evidence
            if evidence.locator.strip()
        )
        if not evidence_links:
            findings.append(
                ReviewFinding(
                    rule_id="leader_review.evidence.missing",
                    record_id=record.id,
                    field="evidence",
                    message="Record has no supporting evidence link.",
                )
            )
        if (
            "impact" in {tag.lower() for tag in record.tags}
            and record.result
            and evidence_links
        ):
            if not _impact_claim_supported(record):
                findings.append(
                    ReviewFinding(
                        rule_id="leader_review.impact.unsupported",
                        record_id=record.id,
                        field="result",
                        message="Impact text is not supported by a linked source.",
                    )
                )
        for gap in record.evidence_gaps:
            findings.append(
                ReviewFinding(
                    rule_id="leader_review.evidence_gap",
                    record_id=record.id,
                    field="evidence_gaps",
                    message=gap,
                )
            )

    ordered = tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.record_id,
                finding.rule_id,
                finding.field,
                finding.message,
            ),
        )
    )
    return LeaderReview(findings=ordered)


def _impact_claim_supported(record: DeliveryRecord) -> bool:
    claim_tokens = _meaningful_tokens(record.result or "")
    if not claim_tokens:
        return False
    for evidence in record.evidence:
        if not evidence.locator.strip() or not evidence.excerpt.strip():
            continue
        if claim_tokens.intersection(_meaningful_tokens(evidence.excerpt)):
            return True
    return False


def _meaningful_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value.lower()).encode(
        "ascii",
        "ignore",
    ).decode("ascii")
    return {
        token
        for token in _TOKEN.findall(normalized)
        if len(token) >= 4 and token not in _CLAIM_STOPWORDS
    }
