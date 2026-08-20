from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from typing import Any

from careeros.connectors.base import (
    CollectRequest,
    ConnectorRequestInvalid,
    Observation,
    PrivacyBlocked,
)
from careeros.connectors.thread import ThreadConnector
from careeros.consent import ConsentDenied
from careeros.deploy import DeploymentBlocked, DeployService
from careeros.harvest import HarvestRequest, HarvestService, memory_store
from careeros.jobs import InvalidJobId, JobResult, UnknownJob
from careeros.models import (
    CommandResult,
    DeliveryRecord,
    EvidenceRef,
    RecordMetadata,
    ValidationIssue,
)
from careeros.outputs import PromotionPacket, build_promo_packet
from careeros.privacy import PrivacyFinding, scan_sensitive
from careeros.sync import ReadbackMismatch, SyncGateway, SyncService
from careeros.validation import validate_records

STAR_FIELDS = ("situation", "task", "action", "result")


def privacy_result(command: str, value: object) -> CommandResult | None:
    findings = _scan_value(value)
    if not findings:
        return None
    return CommandResult(
        ok=False,
        command=command,
        data={"findings": [_finding_data(finding) for finding in findings]},
        errors=(
            {
                "code": "privacy.blocked",
                "message": "Input was blocked by the privacy preflight",
            },
        ),
    )


def handle_capture_delivery(payload: Mapping[str, object]) -> CommandResult:
    command = "capture-delivery"
    try:
        excerpt, thread_id = _capture_input(payload)
    except ValueError:
        return _input_error(command, "A bounded excerpt or thread is required")

    blocked = privacy_result(command, excerpt)
    if blocked is not None:
        return blocked

    try:
        observations = ThreadConnector().collect(
            CollectRequest(
                source="thread",
                excerpt=excerpt,
                thread_id=thread_id,
            )
        )
    except (ConnectorRequestInvalid, PrivacyBlocked):
        return _input_error(command, "The thread excerpt is invalid or privacy blocked")

    result = HarvestService(memory_store()).run(
        HarvestRequest(
            observations=tuple(observation.as_dict() for observation in observations),
            persist=False,
        )
    )
    drafts = [_draft_data(record) for record in result.records]
    issues = _issue_data(result.issues)
    has_errors = _has_error_issues(result.issues)
    errors = (
        (
            {
                "code": "validation.failed",
                "message": "Capture validation failed",
            },
        )
        if has_errors
        else ()
    )
    return CommandResult(
        ok=not has_errors,
        command=command,
        data={"drafts": drafts, "issues": issues, "persisted": False},
        errors=errors,
    )


def handle_harvest_retrospective(
    payload: Mapping[str, object],
    *,
    store: object,
    github_connector: object | None = None,
    google_connector: object | None = None,
) -> CommandResult:
    command = "harvest-retrospective"
    blocked = privacy_result(command, payload)
    if blocked is not None:
        return blocked

    try:
        observations = _collect_harvest_observations(
            payload,
            github_connector=github_connector,
            google_connector=google_connector,
        )
    except ConsentDenied:
        return _error(
            command,
            "harvest.consent_denied",
            "Connector consent is missing or revoked",
        )
    except (ConnectorRequestInvalid, PrivacyBlocked, ValueError, TypeError):
        return _input_error(command, "Harvest input is invalid or blocked")
    except Exception:
        return _error(
            command,
            "harvest.connector_failed",
            "A configured connector failed",
        )

    if not observations:
        return _input_error(command, "At least one bounded observation is required")

    result = HarvestService(store).run(
        HarvestRequest(
            observations=tuple(observation.as_dict() for observation in observations),
        )
    )
    issue_ids = sorted({issue.rule_id for issue in result.issues})
    provenance = sorted(
        {
            connector
            for record in result.records
            for connector in (
                *record.metadata.provenance,
                record.source_connector,
            )
            if connector
        }
    )
    data: dict[str, object] = {
        "persisted": result.persisted,
        "issues": issue_ids,
        "record_ids": [record.id for record in result.records],
        "provenance": provenance,
    }
    if result.persistence_error is not None:
        return _error(
            command,
            "harvest.persistence.failed",
            "Validated records could not be persisted",
            data=data,
        )
    if _has_error_issues(result.issues):
        return _error(
            command,
            "validation.failed",
            "Harvest validation failed",
            data=data,
        )
    return CommandResult(ok=True, command=command, data=data)


def handle_validate_bragsheet_integrity(
    records: Sequence[DeliveryRecord | Mapping[str, object]],
) -> CommandResult:
    command = "validate-bragsheet-integrity"
    blocked = privacy_result(command, records)
    if blocked is not None:
        return blocked
    normalized_records = tuple(
        record
        if isinstance(record, DeliveryRecord) or record.get("record_type") == "kudos"
        else record_from_mapping(record)
        for record in records
    )
    issues = validate_records(normalized_records, {})
    has_errors = _has_error_issues(issues)
    return CommandResult(
        ok=not has_errors,
        command=command,
        data={"issues": _issue_data(issues), "record_count": len(records)},
        errors=(
            (
                {
                    "code": "validation.failed",
                    "message": "Record integrity validation failed",
                },
            )
            if has_errors
            else ()
        ),
    )


def handle_write_bragsheet_safe(
    records: Sequence[DeliveryRecord],
    *,
    destination_id: str,
    sheet_name: str,
    start_row: int,
    sync: SyncService,
    gateway: SyncGateway,
    command: str = "write-bragsheet-safe",
) -> CommandResult:
    blocked = privacy_result(command, records)
    if blocked is not None:
        return blocked

    issues = validate_records(records, {})
    if _has_error_issues(issues):
        return CommandResult(
            ok=False,
            command=command,
            data={
                "status": "blocked",
                "issues": _issue_data(issues),
            },
            errors=(
                {
                    "code": "validation.failed",
                    "message": "Record integrity validation failed",
                },
            ),
        )

    try:
        projection = sync.preview(
            records,
            destination_id=destination_id,
            sheet_name=sheet_name,
            start_row=start_row,
        )
    except (TypeError, ValueError):
        return _input_error(command, "Brag-sheet projection configuration is invalid")

    preview = {
        "destination_id": projection.destination_id,
        "sheet_name": projection.sheet_name,
        "start_row": projection.start_row,
        "row_count": projection.row_count,
        "column_count": projection.column_count,
    }
    try:
        run = sync.write_and_verify(projection, gateway)
    except ConsentDenied:
        return _error(
            command,
            "sync.consent_denied",
            "Destination consent is missing or revoked",
            data={"status": "blocked", "preview": preview},
        )
    except ReadbackMismatch:
        return _reconciliation_result(command, preview)
    except Exception:
        if sync.last_run is not None and sync.last_run.status == "reconciliation_required":
            return _reconciliation_result(command, preview)
        return _error(
            command,
            "sync.failed",
            "Brag-sheet synchronization failed before verification",
            data={"status": "blocked", "preview": preview},
        )

    return CommandResult(
        ok=run.status == "synced",
        command=command,
        data={"status": run.status, "preview": preview},
        errors=(
            ()
            if run.status == "synced"
            else (
                {
                    "code": "sync.unverified",
                    "message": "Brag-sheet synchronization was not verified",
                },
            )
        ),
    )


def handle_deploy_careeros_timeline(service: DeployService) -> CommandResult:
    command = "deploy-careeros-timeline"
    try:
        result = service.deploy()
    except DeploymentBlocked:
        return _error(
            command,
            "deploy.blocked",
            "Deployment health or /exec verification failed",
        )
    except Exception:
        return _error(
            command,
            "deploy.failed",
            "Deployment failed without a verified /exec URL",
        )
    return CommandResult(
        ok=True,
        command=command,
        data={
            "webAppUrl": result.web_app_url,
            "homepage": result.homepage,
        },
    )


def handle_build_promo_packet(records: Sequence[DeliveryRecord]) -> CommandResult:
    command = "build-promo-packet"
    blocked = privacy_result(command, records)
    if blocked is not None:
        return blocked
    issues = validate_records(records, {})
    if _has_error_issues(issues):
        return CommandResult(
            ok=False,
            command=command,
            data={
                "status": "blocked",
                "issues": _issue_data(issues),
                "work_card_count": 0,
                "missing_work_cards": 10,
            },
            errors=(
                {
                    "code": "validation.failed",
                    "message": "Record integrity validation failed",
                },
            ),
        )
    packet = build_promo_packet(records)
    return CommandResult(
        ok=True,
        command=command,
        data=_packet_data(packet),
    )


def handle_sync_careeros_background(
    job_id: str,
    *,
    run_job: Callable[[str], JobResult],
) -> CommandResult:
    command = "sync-careeros"
    try:
        result = run_job(job_id)
    except ConsentDenied:
        return _error(
            command,
            "sync.consent_denied",
            "Background consent is missing or revoked",
        )
    except (InvalidJobId, UnknownJob):
        return _error(command, "sync.job_invalid", "Background job is not configured")
    except Exception:
        return _error(command, "sync.job_failed", "Background synchronization failed")
    return CommandResult(
        ok=True,
        command=command,
        data={
            "jobId": result.job_id,
            "status": result.status,
            "idempotencyKey": result.idempotency_key,
        },
    )


def records_from_payload(payload: Mapping[str, object]) -> tuple[DeliveryRecord, ...] | None:
    raw_records = payload.get("records")
    if raw_records is None:
        return None
    if not isinstance(raw_records, list):
        raise ValueError("records must be a list")
    return tuple(record_from_mapping(record) for record in raw_records)


def record_from_mapping(value: object) -> DeliveryRecord:
    if not isinstance(value, Mapping):
        raise ValueError("record must be an object")
    evidence_value = value.get("evidence", ())
    if not isinstance(evidence_value, (list, tuple)):
        raise ValueError("record evidence must be a list")
    evidence = tuple(_evidence_from_mapping(item) for item in evidence_value)
    metadata_value = value.get("metadata", {})
    if not isinstance(metadata_value, Mapping):
        raise ValueError("record metadata must be an object")
    record_id = _required_text(value, "id")
    title = _required_text(value, "title")
    return DeliveryRecord(
        id=record_id,
        schema_version=int(value.get("schema_version", 1)),
        source_connector=str(value.get("source_connector", "stdin")),
        source_locator=str(value.get("source_locator", record_id)),
        title=title,
        period=_optional_text(value.get("period")),
        tags=_string_tuple(value.get("tags", ())),
        context=_optional_text(value.get("context")),
        confidence=_optional_text(value.get("confidence")),
        situation=_optional_text(value.get("situation")),
        task=_optional_text(value.get("task")),
        action=_optional_text(value.get("action")),
        result=_optional_text(value.get("result")),
        evidence=evidence,
        evidence_gaps=_string_tuple(value.get("evidence_gaps", ())),
        content_fingerprint=str(
            value.get("content_fingerprint") or _mapping_fingerprint(value)
        ),
        observed_at=str(value.get("observed_at", "")),
        metadata=RecordMetadata(
            jira_key=_optional_text(metadata_value.get("jira_key", value.get("jira_key"))),
            pr_status=_optional_text(
                metadata_value.get("pr_status", value.get("pr_status"))
            ),
            narrative_status=_optional_text(
                metadata_value.get(
                    "narrative_status",
                    value.get("narrative_status"),
                )
            ),
            epic_parent=_optional_text(
                metadata_value.get("epic_parent", value.get("epic_parent"))
            ),
            provenance=_string_tuple(metadata_value.get("provenance", ())),
            merged_source_ids=_string_tuple(
                metadata_value.get("merged_source_ids", ())
            ),
            evidence_locators=_string_tuple(
                metadata_value.get("evidence_locators", ())
            ),
        ),
    )


def _capture_input(payload: Mapping[str, object]) -> tuple[str, str]:
    excerpt = payload.get("excerpt")
    thread = payload.get("thread")
    thread_id_value = payload.get("thread_id")
    if isinstance(excerpt, str):
        text = excerpt
    elif isinstance(thread, str):
        text = thread
    elif isinstance(thread, Mapping):
        content = thread.get("excerpt", thread.get("content"))
        if not isinstance(content, str):
            raise ValueError("thread content is missing")
        text = content
        thread_id_value = thread.get("id", thread_id_value)
    else:
        raise ValueError("capture input is missing")
    if not text.strip():
        raise ValueError("capture input is empty")
    if isinstance(thread_id_value, str) and thread_id_value.strip():
        thread_id = thread_id_value.strip()
    else:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        thread_id = f"excerpt-{digest}"
    return text, thread_id


def _collect_harvest_observations(
    payload: Mapping[str, object],
    *,
    github_connector: object | None,
    google_connector: object | None,
) -> tuple[Observation, ...]:
    collected: list[Observation] = []
    raw_observations = payload.get("observations", ())
    if not isinstance(raw_observations, (list, tuple)):
        raise ValueError("observations must be a list")
    for raw in raw_observations:
        collected.append(_observation_from_json(raw))

    if "excerpt" in payload or "thread" in payload:
        excerpt, thread_id = _capture_input(payload)
        collected.extend(
            ThreadConnector().collect(
                CollectRequest(
                    source="thread",
                    excerpt=excerpt,
                    thread_id=thread_id,
                )
            )
        )

    github = payload.get("github")
    if github is not None:
        if github_connector is None or not isinstance(github, Mapping):
            raise ValueError("GitHub connector is not configured")
        collect = getattr(github_connector, "collect")
        collected.extend(
            collect(
                CollectRequest(
                    source="github",
                    endpoint=_optional_text(github.get("endpoint")),
                    fields=_optional_text(github.get("fields")),
                    max_results=_optional_int(github.get("max_results")),
                )
            )
        )

    google = payload.get("google")
    if google is not None:
        if google_connector is None:
            raise ValueError("Google connector is not configured")
        requests = google if isinstance(google, list) else [google]
        collect = getattr(google_connector, "collect")
        for request in requests:
            if not isinstance(request, Mapping):
                raise ValueError("Google request must be an object")
            time_window = request.get("time_window")
            collected.extend(
                collect(
                    CollectRequest(
                        source="google",
                        action=_optional_text(request.get("action")),
                        query=_optional_text(request.get("query")),
                        time_window=_time_window(time_window),
                        max_results=_optional_int(request.get("max_results")),
                        resource_id=_optional_text(request.get("resource_id")),
                        sheet_name=_optional_text(request.get("sheet_name")),
                        range=_optional_text(request.get("range")),
                    )
                )
            )
    return tuple(collected)


def _observation_from_json(value: object) -> Observation:
    if not isinstance(value, Mapping):
        raise ValueError("observation must be an object")
    return Observation(
        source_id=_required_text(value, "source_id"),
        source_connector=_required_text(value, "source_connector"),
        source_locator=_required_text(value, "source_locator"),
        title=_required_text(value, "title"),
        tags=_string_tuple(value.get("tags", ())),
        period=_optional_text(value.get("period")),
        observed_at=_required_text(value, "observed_at"),
        excerpt=str(value.get("excerpt", "")),
        jira_key=_optional_text(value.get("jira_key")),
        pr_locator=_optional_text(value.get("pr_locator")),
        evidence_locator=_optional_text(value.get("evidence_locator")),
        provenance=_string_tuple(value.get("provenance", ())),
        result=_optional_text(value.get("result")),
        pr_status=_optional_text(value.get("pr_status")),
        narrative_status=_optional_text(value.get("narrative_status")),
        confidence=_optional_text(value.get("confidence")),
    )


def _draft_data(record: DeliveryRecord) -> dict[str, object]:
    gaps = list(record.evidence_gaps)
    star_values: dict[str, str] = {}
    for field in STAR_FIELDS:
        value = getattr(record, field)
        if isinstance(value, str) and value.strip():
            star_values[field] = value
            continue
        gap = f"Evidence gap: {field.capitalize()} not present in source excerpt."
        star_values[field] = gap
        if gap not in gaps:
            gaps.append(gap)
    return {
        "record_id": record.id,
        "period": record.period,
        "title": record.title,
        "tags": list(record.tags),
        "context": record.context,
        "confidence": record.confidence,
        **star_values,
        "evidence": [
            {
                "locator": evidence.locator,
                "observed_at": evidence.observed_at,
                "connector": evidence.connector,
            }
            for evidence in record.evidence
        ],
        "evidence_gaps": gaps,
    }


def _packet_data(packet: PromotionPacket) -> dict[str, object]:
    return {
        "status": packet.status,
        "work_card_count": len(packet.work_cards),
        "work_cards": [asdict(card) for card in packet.work_cards],
        "community_summary": asdict(packet.community_summary),
        "recognition_summary": asdict(packet.recognition_summary),
        "unresolved_work_summary": asdict(packet.unresolved_work_summary),
        "missing_work_cards": packet.missing_work_cards,
    }


def _issue_data(issues: Sequence[ValidationIssue]) -> list[dict[str, object]]:
    return [
        {
            "rule_id": issue.rule_id,
            "severity": issue.severity,
            "field": issue.field,
        }
        for issue in issues
    ]


def _has_error_issues(issues: Sequence[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _scan_value(value: object) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for text in _strings_in(value):
        findings.extend(scan_sensitive(text))
    return findings


def _strings_in(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, DeliveryRecord):
        return _strings_in(asdict(value))
    if isinstance(value, Mapping):
        return [
            text
            for key, item in value.items()
            for text in (*_strings_in(key), *_strings_in(item))
        ]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _strings_in(item)]
    return []


def _finding_data(finding: PrivacyFinding) -> dict[str, object]:
    return {
        "category": finding.category,
        "start": finding.start,
        "end": finding.end,
    }


def _reconciliation_result(
    command: str,
    preview: Mapping[str, object],
) -> CommandResult:
    return _error(
        command,
        "sync.reconciliation_required",
        "Brag-sheet read-back did not match the intended projection",
        data={"status": "reconciliation_required", "preview": dict(preview)},
    )


def _input_error(command: str, message: str) -> CommandResult:
    return _error(command, "input.invalid", message)


def _error(
    command: str,
    code: str,
    message: str,
    *,
    data: Mapping[str, object] | None = None,
) -> CommandResult:
    return CommandResult(
        ok=False,
        command=command,
        data=dict(data or {}),
        errors=({"code": code, "message": message},),
    )


def _required_text(value: Mapping[str, object], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"{field} is required")
    return result.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("expected text")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected integer")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("expected a list")
    return tuple(str(item) for item in value)


def _time_window(value: object) -> tuple[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("time_window must contain start and end")
    return str(value[0]), str(value[1])


def _evidence_from_mapping(value: object) -> EvidenceRef:
    if not isinstance(value, Mapping):
        raise ValueError("evidence must be an object")
    return EvidenceRef(
        locator=str(value.get("locator", "")),
        excerpt=str(value.get("excerpt", "")),
        observed_at=str(value.get("observed_at", "")),
        connector=str(value.get("connector", "")),
    )


def _mapping_fingerprint(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        dict(value),
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
