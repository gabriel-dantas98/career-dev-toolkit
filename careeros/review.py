from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from careeros.models import DeliveryRecord


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
        if "impact" in {tag.lower() for tag in record.tags} and record.result:
            if not evidence_links:
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
