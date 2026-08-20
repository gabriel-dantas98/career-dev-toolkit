from __future__ import annotations

import json

from careeros.models import DeliveryRecord, EvidenceRef, RecordMetadata


def serialize_metadata(metadata: RecordMetadata) -> str:
    payload = {
        "epic_parent": metadata.epic_parent,
        "evidence_locators": list(metadata.evidence_locators),
        "jira_key": metadata.jira_key,
        "merged_source_ids": list(metadata.merged_source_ids),
        "narrative_status": metadata.narrative_status,
        "pr_status": metadata.pr_status,
        "provenance": list(metadata.provenance),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def deserialize_metadata(raw: str | None) -> RecordMetadata:
    if not raw:
        return RecordMetadata()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return RecordMetadata()
    return RecordMetadata(
        jira_key=_optional_str(payload.get("jira_key")),
        pr_status=_optional_str(payload.get("pr_status")),
        narrative_status=_optional_str(payload.get("narrative_status")),
        epic_parent=_optional_str(payload.get("epic_parent")),
        provenance=_tuple_of_str(payload.get("provenance")),
        merged_source_ids=_tuple_of_str(payload.get("merged_source_ids")),
        evidence_locators=_tuple_of_str(payload.get("evidence_locators")),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _tuple_of_str(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def metadata_from_record(record: DeliveryRecord) -> RecordMetadata:
    locators = tuple(
        evidence.locator.strip()
        for evidence in record.evidence
        if evidence.locator.strip()
    )
    metadata = record.metadata
    if metadata.evidence_locators == locators:
        return metadata
    return RecordMetadata(
        jira_key=metadata.jira_key,
        pr_status=metadata.pr_status,
        narrative_status=metadata.narrative_status,
        epic_parent=metadata.epic_parent,
        provenance=metadata.provenance,
        merged_source_ids=metadata.merged_source_ids,
        evidence_locators=locators,
    )
