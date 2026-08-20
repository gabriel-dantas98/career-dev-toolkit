from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from careeros.connectors.timestamps import utc_now_iso
from careeros.dedup import deduplicate
from careeros.models import DeliveryRecord, EvidenceRef, RecordMetadata, ValidationIssue
from careeros.taxonomy import apply_confidence_cap, classify_context, normalize_delivery_prefix
from careeros.validation import validate_records

Validator = Callable[
    [Sequence[DeliveryRecord | Mapping[str, object]], Mapping[str, object]],
    list[ValidationIssue],
]


@dataclass(frozen=True)
class HarvestRequest:
    observations: tuple[Mapping[str, object], ...]
    persist: bool = True


@dataclass(frozen=True)
class HarvestResult:
    records: tuple[DeliveryRecord, ...]
    issues: tuple[ValidationIssue, ...]
    persisted: bool
    persistence_error: Mapping[str, object] | None = None


class HarvestPersistenceError(Exception):
    """Raised when validated harvest records cannot be persisted."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class MemoryStore:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}

    def count_records(self) -> int:
        return len(self._records)

    def get_record(self, record_id: str) -> dict[str, object] | None:
        return self._records.get(record_id)

    def persist_records(self, records: tuple[DeliveryRecord, ...]) -> None:
        pending: dict[str, dict[str, object]] = {}
        for record in records:
            pending[record.id] = {
                "id": record.id,
                "title": record.title,
                "evidence": [
                    {
                        "locator": evidence.locator,
                        "excerpt": evidence.excerpt,
                        "observed_at": evidence.observed_at,
                        "connector": evidence.connector,
                    }
                    for evidence in record.evidence
                ],
            }
        self._records.update(pending)


def memory_store() -> MemoryStore:
    return MemoryStore()


class HarvestService:
    def __init__(
        self,
        store: object,
        *,
        extra_validators: Sequence[Validator] | None = None,
    ) -> None:
        self._store = store
        self._validators: list[Validator] = [validate_records]
        if extra_validators:
            self._validators.extend(extra_validators)

    def run(self, request: HarvestRequest) -> HarvestResult:
        raw_observations = [dict(observation) for observation in request.observations]
        merged_observations = deduplicate(raw_observations)
        records = [
            self._to_delivery_record(merged, raw_observations, normalize_title=False)
            for merged in merged_observations
        ]

        issues: list[ValidationIssue] = []
        for validator in self._validators:
            issues.extend(validator(records, {}))

        has_errors = any(issue.severity == "error" for issue in issues)
        persisted = False
        final_records = records
        if request.persist and not has_errors and records:
            final_records = [
                self._normalize_record(record) for record in records
            ]
            try:
                persist = getattr(self._store, "persist_records")
                persist(tuple(final_records))
                persisted = True
            except Exception as exc:
                return HarvestResult(
                    records=tuple(final_records),
                    issues=tuple(issues),
                    persisted=False,
                    persistence_error={
                        "code": "harvest.persistence.failed",
                        "message": type(exc).__name__,
                    },
                )

        return HarvestResult(
            records=tuple(final_records),
            issues=tuple(issues),
            persisted=persisted,
        )

    def _normalize_record(self, record: DeliveryRecord) -> DeliveryRecord:
        normalized_title = normalize_delivery_prefix(record.title, tags=record.tags)
        if normalized_title == record.title:
            return record
        return DeliveryRecord(
            id=record.id,
            schema_version=record.schema_version,
            source_connector=record.source_connector,
            source_locator=record.source_locator,
            title=normalized_title,
            period=record.period,
            tags=record.tags,
            context=record.context,
            confidence=record.confidence,
            situation=record.situation,
            task=record.task,
            action=record.action,
            result=record.result,
            evidence=record.evidence,
            evidence_gaps=record.evidence_gaps,
            content_fingerprint=record.content_fingerprint,
            observed_at=record.observed_at,
            metadata=record.metadata,
        )

    def _to_delivery_record(
        self,
        merged: Mapping[str, object],
        raw_observations: Sequence[Mapping[str, object]],
        *,
        normalize_title: bool = True,
    ) -> DeliveryRecord:
        source_id = str(merged.get("source_id", ""))
        record_id = f"rec:{source_id}" if source_id else "rec:unknown"
        title = str(merged.get("title", "Untitled"))
        tags = merged.get("tags", ())
        normalized_tags = tuple(str(tag) for tag in tags) if isinstance(tags, tuple) else ()
        if normalize_title:
            title = normalize_delivery_prefix(title, tags=normalized_tags)
        evidence = self._build_evidence(merged, raw_observations)
        provenance = merged.get("provenance", ())
        merged_source_ids = merged.get("merged_source_ids", ())
        evidence_locators = tuple(
            ref.locator.strip() for ref in evidence if ref.locator.strip()
        )
        metadata = RecordMetadata(
            jira_key=(
                str(merged["jira_key"]) if merged.get("jira_key") is not None else None
            ),
            pr_status=(
                str(merged["pr_status"]) if merged.get("pr_status") is not None else None
            ),
            narrative_status=(
                str(merged["narrative_status"])
                if merged.get("narrative_status") is not None
                else None
            ),
            epic_parent=(
                str(merged["epic_parent"]) if merged.get("epic_parent") is not None else None
            ),
            provenance=(
                tuple(str(item) for item in provenance)
                if isinstance(provenance, tuple)
                else ()
            ),
            merged_source_ids=(
                tuple(str(item) for item in merged_source_ids)
                if isinstance(merged_source_ids, tuple)
                else ()
            ),
            evidence_locators=evidence_locators,
        )

        confidence = merged.get("confidence")
        if confidence is not None:
            confidence_value = str(confidence)
        else:
            confidence_value = "partial"

        record = DeliveryRecord(
            id=record_id,
            schema_version=1,
            source_connector=str(merged.get("source_connector", "harvest")),
            source_locator=str(merged.get("source_locator", record_id)),
            title=title,
            period=str(merged["period"]) if merged.get("period") is not None else None,
            tags=normalized_tags,
            context=None,
            confidence=confidence_value,
            situation=None,
            task=None,
            action=None,
            result=str(merged["result"]) if merged.get("result") is not None else None,
            evidence=evidence,
            evidence_gaps=(),
            content_fingerprint=_content_fingerprint(merged),
            observed_at=str(merged.get("observed_at", utc_now_iso())),
            metadata=metadata,
        )
        capped = apply_confidence_cap(record)
        if capped != record.confidence:
            return DeliveryRecord(
                id=record.id,
                schema_version=record.schema_version,
                source_connector=record.source_connector,
                source_locator=record.source_locator,
                title=record.title,
                period=record.period,
                tags=record.tags,
                context=record.context,
                confidence=capped,
                situation=record.situation,
                task=record.task,
                action=record.action,
                result=record.result,
                evidence=record.evidence,
                evidence_gaps=record.evidence_gaps,
                content_fingerprint=record.content_fingerprint,
                observed_at=record.observed_at,
                metadata=record.metadata,
            )
        classified = classify_context(record)
        return DeliveryRecord(
            id=record.id,
            schema_version=record.schema_version,
            source_connector=record.source_connector,
            source_locator=record.source_locator,
            title=record.title,
            period=record.period,
            tags=record.tags,
            context=classified,
            confidence=record.confidence,
            situation=record.situation,
            task=record.task,
            action=record.action,
            result=record.result,
            evidence=record.evidence,
            evidence_gaps=record.evidence_gaps,
            content_fingerprint=record.content_fingerprint,
            observed_at=record.observed_at,
            metadata=record.metadata,
        )

    def _build_evidence(
        self,
        merged: Mapping[str, object],
        raw_observations: Sequence[Mapping[str, object]],
    ) -> tuple[EvidenceRef, ...]:
        provenance = merged.get("provenance", ())
        connectors = (
            tuple(str(item) for item in provenance)
            if isinstance(provenance, tuple)
            else ()
        )
        refs: list[EvidenceRef] = []
        for connector in connectors:
            for observation in raw_observations:
                obs_provenance = observation.get("provenance", ())
                obs_connector = observation.get("source_connector")
                if connector == obs_connector or (
                    isinstance(obs_provenance, tuple) and connector in obs_provenance
                ):
                    refs.append(
                        EvidenceRef(
                            locator=str(observation.get("source_locator", "")),
                            excerpt=str(observation.get("excerpt", "")),
                            observed_at=str(
                                observation.get("observed_at", utc_now_iso())
                            ),
                            connector=connector,
                        )
                    )
                    break
        return tuple(refs)


def _content_fingerprint(merged: Mapping[str, object]) -> str:
    payload = {
        "source_id": merged.get("source_id"),
        "title": merged.get("title"),
        "jira_key": merged.get("jira_key"),
        "pr_locator": merged.get("pr_locator"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest[:16]

