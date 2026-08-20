from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

MAX_THREAD_EXCERPT = 8_000
MAX_GITHUB_RESULTS = 100
MAX_GOOGLE_RESULTS = 50

GOOGLE_SEARCH_ACTIONS = frozenset(
    {
        "calendar.search",
        "gmail.search",
        "drive.search",
    }
)


class ConnectorRequestInvalid(ValueError):
    """Raised when a connector request violates bounded-collection rules."""


class PrivacyBlocked(Exception):
    """Raised when privacy preflight blocks connector ingestion."""


@dataclass(frozen=True)
class Observation:
    source_id: str
    source_connector: str
    source_locator: str
    title: str
    tags: tuple[str, ...]
    period: str | None
    observed_at: str
    excerpt: str
    jira_key: str | None = None
    pr_locator: str | None = None
    evidence_locator: str | None = None
    provenance: tuple[str, ...] = ()
    result: str | None = None
    pr_status: str | None = None
    narrative_status: str | None = None
    confidence: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "source_connector": self.source_connector,
            "source_locator": self.source_locator,
            "title": self.title,
            "tags": self.tags,
            "period": self.period,
            "observed_at": self.observed_at,
            "excerpt": self.excerpt,
            "jira_key": self.jira_key,
            "pr_locator": self.pr_locator,
            "evidence_locator": self.evidence_locator,
            "provenance": self.provenance,
            "result": self.result,
            "pr_status": self.pr_status,
            "narrative_status": self.narrative_status,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class CollectRequest:
    source: str
    excerpt: str | None = None
    thread_id: str | None = None
    endpoint: str | None = None
    fields: str | None = None
    max_results: int | None = None
    action: str | None = None
    query: str | None = None
    time_window: tuple[str, str] | None = None
    resource_id: str | None = None


class Connector(Protocol):
    def collect(self, request: CollectRequest) -> tuple[Observation, ...]: ...


def validate_time_window(time_window: tuple[str, str]) -> None:
    start_raw, end_raw = time_window
    if not start_raw.strip() or not end_raw.strip():
        raise ConnectorRequestInvalid("time window requires finite ISO-8601 start and end")

    try:
        start = _parse_iso8601(start_raw.strip())
        end = _parse_iso8601(end_raw.strip())
    except ValueError as exc:
        raise ConnectorRequestInvalid("time window requires finite ISO-8601 start and end") from exc

    if start >= end:
        raise ConnectorRequestInvalid("time window start must be before end")


def _parse_iso8601(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def observation_from_mapping(data: Mapping[str, object]) -> Observation:
    tags = data.get("tags", ())
    provenance = data.get("provenance", ())
    return Observation(
        source_id=str(data["source_id"]),
        source_connector=str(data["source_connector"]),
        source_locator=str(data["source_locator"]),
        title=str(data["title"]),
        tags=tuple(str(tag) for tag in tags) if isinstance(tags, tuple) else (),
        period=str(data["period"]) if data.get("period") is not None else None,
        observed_at=str(data["observed_at"]),
        excerpt=str(data["excerpt"]),
        jira_key=str(data["jira_key"]) if data.get("jira_key") is not None else None,
        pr_locator=str(data["pr_locator"]) if data.get("pr_locator") is not None else None,
        evidence_locator=(
            str(data["evidence_locator"]) if data.get("evidence_locator") is not None else None
        ),
        provenance=(
            tuple(str(item) for item in provenance)
            if isinstance(provenance, tuple)
            else ()
        ),
        result=str(data["result"]) if data.get("result") is not None else None,
        pr_status=str(data["pr_status"]) if data.get("pr_status") is not None else None,
        narrative_status=(
            str(data["narrative_status"]) if data.get("narrative_status") is not None else None
        ),
        confidence=str(data["confidence"]) if data.get("confidence") is not None else None,
    )
