from __future__ import annotations

from collections.abc import Mapping, Sequence

from careeros.models import DeliveryRecord, EvidenceRef, RecordMetadata, ValidationIssue
from careeros.taxonomy import apply_confidence_cap, prefix_for_tag


def _issue(
    rule_id: str,
    *,
    severity: str,
    message: str,
    field: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        rule_id=rule_id,
        severity=severity,
        message=message,
        field=field,
    )


def _normalize_evidence_items(value: object) -> tuple[EvidenceRef, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    refs: list[EvidenceRef] = []
    for item in value:
        if isinstance(item, EvidenceRef):
            refs.append(item)
    return tuple(refs)


def _record_view(record: Mapping[str, object] | DeliveryRecord) -> Mapping[str, object]:
    if isinstance(record, DeliveryRecord):
        metadata = record.metadata
        return {
            "record_type": record.record_type,
            "id": record.id,
            "title": record.title,
            "tags": record.tags,
            "name": record.name,
            "month": record.month,
            "confidence": record.confidence,
            "result": record.result or "",
            "evidence": record.evidence,
            "jira_key": metadata.jira_key,
            "pr_status": metadata.pr_status,
            "narrative_status": metadata.narrative_status,
            "epic_parent": metadata.epic_parent,
        }
    return record


def _evidence_locators(
    record: Mapping[str, object],
    evidence: Mapping[str, object],
) -> set[str]:
    locators: set[str] = set()
    for item in _normalize_evidence_items(record.get("evidence", ())):
        if item.locator.strip():
            locators.add(item.locator.strip())

    record_id = str(record.get("id", ""))
    mapped = evidence.get(record_id)
    for item in _normalize_evidence_items(mapped):
        if item.locator.strip():
            locators.add(item.locator.strip())

    return locators


def _validate_kudos(record: Mapping[str, object]) -> list[ValidationIssue]:
    if record.get("record_type") != "kudos":
        return []
    issues: list[ValidationIssue] = []
    name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        issues.append(
            _issue(
                "kudos.name.required",
                severity="error",
                message="Kudos records require a recipient name.",
                field="name",
            )
        )
    month = record.get("month")
    if month is None or (isinstance(month, str) and not month.strip()):
        issues.append(
            _issue(
                "kudos.month.required",
                severity="error",
                message="Kudos records require a month.",
                field="month",
            )
        )
    return issues


def _title_prefix(title: str) -> str | None:
    if not title.startswith("["):
        return None
    closing = title.find("]")
    if closing == -1:
        return None
    return title[: closing + 1]


def _validate_delivery(
    record: Mapping[str, object],
    evidence: Mapping[str, object],
) -> list[ValidationIssue]:
    if record.get("record_type") != "delivery":
        return []
    issues: list[ValidationIssue] = []
    title = str(record.get("title", ""))
    tags = tuple(record.get("tags", ()))
    normalized_tags = tuple(tag.lower() for tag in tags if isinstance(tag, str))

    prefix = _title_prefix(title)
    if not prefix:
        issues.append(
            _issue(
                "taxonomy.prefix.required",
                severity="error",
                message="Delivery titles require a taxonomy prefix.",
                field="title",
            )
        )
    elif normalized_tags:
        expected_prefix = prefix_for_tag(normalized_tags[0])
        if prefix != expected_prefix:
            issues.append(
                _issue(
                    "title.tags.mismatch",
                    severity="error",
                    message="Delivery title prefix does not match primary tag.",
                    field="title",
                )
            )

    delivery_record = None
    if isinstance(record, DeliveryRecord):
        delivery_record = record
    elif record.get("record_type") == "delivery":
        metadata = RecordMetadata(
            jira_key=record.get("jira_key") if isinstance(record.get("jira_key"), str) else None,
            pr_status=record.get("pr_status") if isinstance(record.get("pr_status"), str) else None,
            narrative_status=(
                record.get("narrative_status")
                if isinstance(record.get("narrative_status"), str)
                else None
            ),
            epic_parent=record.get("epic_parent") if isinstance(record.get("epic_parent"), str) else None,
        )
        delivery_record = DeliveryRecord(
            id=str(record.get("id", "")),
            schema_version=1,
            source_connector="validation",
            source_locator=str(record.get("id", "")),
            title=title,
            period=None,
            tags=normalized_tags,
            context=None,
            confidence=str(record.get("confidence")) if record.get("confidence") is not None else None,
            situation=None,
            task=None,
            action=None,
            result=str(record.get("result", "")),
            evidence=_normalize_evidence_items(record.get("evidence", ())),
            evidence_gaps=(),
            content_fingerprint=str(record.get("id", "")),
            observed_at="1970-01-01T00:00:00Z",
            metadata=metadata,
        )

    if delivery_record is not None:
        capped = apply_confidence_cap(delivery_record)
        if delivery_record.confidence == "complete" and capped != "complete":
            issues.append(
                _issue(
                    "taxonomy.confidence.exceeds_cap",
                    severity="error",
                    message="Confidence exceeds evidence-supported cap.",
                    field="confidence",
                )
            )

    result = str(record.get("result", ""))
    locators = _evidence_locators(record, evidence)
    if "impact" in normalized_tags and result.strip() and not locators:
        issues.append(
            _issue(
                "impact.evidence.missing",
                severity="error",
                message="Impact claims require linked evidence.",
                field="evidence",
            )
        )

    record_locators = {
        item.locator.strip()
        for item in _normalize_evidence_items(record.get("evidence", ()))
        if item.locator.strip()
    }
    mapped_locators = {
        item.locator.strip()
        for item in _normalize_evidence_items(evidence.get(str(record.get("id", ""))))
        if item.locator.strip()
    }
    if record_locators and mapped_locators and not record_locators.intersection(mapped_locators):
        issues.append(
            _issue(
                "impact.evidence.inconsistent",
                severity="error",
                message="Record evidence locators do not match the evidence mapping.",
                field="evidence",
            )
        )

    pr_status = record.get("pr_status")
    narrative_status = record.get("narrative_status")
    if (
        isinstance(pr_status, str)
        and isinstance(narrative_status, str)
        and pr_status.strip().lower() != narrative_status.strip().lower()
    ):
        issues.append(
            _issue(
                "github.pr.narrative_mismatch",
                severity="error",
                message="GitHub PR status does not match narrative status.",
                field="pr_status",
            )
        )

    return issues


def _validate_cross_record(records: Sequence[Mapping[str, object]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    jira_keys: dict[str, str] = {}
    epic_parents: dict[str, str] = {}

    for record in records:
        if record.get("record_type") != "delivery":
            continue
        record_id = str(record.get("id", ""))
        jira_key = record.get("jira_key")
        if isinstance(jira_key, str) and jira_key.strip():
            normalized = jira_key.strip().upper()
            if normalized in jira_keys:
                issues.append(
                    _issue(
                        "jira.duplicate",
                        severity="error",
                        message="Duplicate Jira key across records.",
                        field="jira_key",
                    )
                )
            else:
                jira_keys[normalized] = record_id

        epic_parent = record.get("epic_parent")
        if isinstance(epic_parent, str) and epic_parent.strip():
            normalized_epic = epic_parent.strip().upper()
            if normalized_epic in epic_parents:
                issues.append(
                    _issue(
                        "epic.duplicate",
                        severity="error",
                        message="Duplicate epic-tree parent across records.",
                        field="epic_parent",
                    )
                )
            else:
                epic_parents[normalized_epic] = record_id

    return issues


def validate_records(
    records: Sequence[Mapping[str, object] | DeliveryRecord],
    evidence: Mapping[str, object],
) -> list[ValidationIssue]:
    normalized_records = [_record_view(record) for record in records]

    issues: list[ValidationIssue] = []
    for record in normalized_records:
        issues.extend(_validate_kudos(record))
        issues.extend(_validate_delivery(record, evidence))
    issues.extend(_validate_cross_record(normalized_records))
    return issues
