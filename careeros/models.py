from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    command: str
    data: Mapping[str, object]
    errors: tuple[Mapping[str, object], ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "command": self.command,
            "data": dict(self.data),
            "errors": [dict(error) for error in self.errors],
        }


@dataclass(frozen=True)
class EvidenceRef:
    locator: str
    excerpt: str
    observed_at: str
    connector: str = ""


@dataclass(frozen=True)
class ValidationIssue:
    rule_id: str
    severity: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class RecordMetadata:
    jira_key: str | None = None
    pr_status: str | None = None
    narrative_status: str | None = None
    epic_parent: str | None = None
    provenance: tuple[str, ...] = ()
    merged_source_ids: tuple[str, ...] = ()
    evidence_locators: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeliveryRecord:
    id: str
    schema_version: int
    source_connector: str
    source_locator: str
    title: str
    period: str | None
    tags: tuple[str, ...]
    context: str | None
    confidence: str | None
    situation: str | None
    task: str | None
    action: str | None
    result: str | None
    evidence: tuple[EvidenceRef, ...]
    evidence_gaps: tuple[str, ...]
    content_fingerprint: str
    observed_at: str
    metadata: RecordMetadata = field(default_factory=RecordMetadata)
