from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

MAX_THREAD_EXCERPT = 8_000
MAX_GITHUB_RESULTS = 100
MAX_GOOGLE_RESULTS = 50
MAX_SHEET_READ_CELLS = 500
MAX_SHEET_ROWS = 1_000_000
MAX_SHEET_COLUMNS = 18_278

_FINITE_A1_RANGE = re.compile(
    r"^([A-Za-z]{1,3})([1-9][0-9]{0,6})(?::([A-Za-z]{1,3})([1-9][0-9]{0,6}))?$"
)

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
    record_type: str = "delivery"
    name: str | None = None
    month: str | None = None

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
            "record_type": self.record_type,
            "name": self.name,
            "month": self.month,
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
    sheet_name: str | None = None
    range: str | None = None


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


def bound_excerpt(text: str) -> str:
    return text[:MAX_THREAD_EXCERPT]


def validate_sheet_range(value: str) -> str:
    match = _FINITE_A1_RANGE.fullmatch(value.strip())
    if match is None:
        raise ConnectorRequestInvalid("sheets.read range must be a finite A1 rectangle")

    start_column = _column_number(match.group(1))
    start_row = int(match.group(2))
    end_column = _column_number(match.group(3) or match.group(1))
    end_row = int(match.group(4) or match.group(2))
    cell_count = (end_column - start_column + 1) * (end_row - start_row + 1)
    if (
        start_column > end_column
        or start_row > end_row
        or end_column > MAX_SHEET_COLUMNS
        or end_row > MAX_SHEET_ROWS
        or cell_count > MAX_SHEET_READ_CELLS
    ):
        raise ConnectorRequestInvalid("sheets.read range exceeds the fixed cell bounds")

    return (
        f"{_column_label(start_column)}{start_row}:"
        f"{_column_label(end_column)}{end_row}"
    )


def _parse_iso8601(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def _column_number(label: str) -> int:
    result = 0
    for character in label.upper():
        result = result * 26 + ord(character) - 64
    return result


def _column_label(number: int) -> str:
    value = number
    label = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label
    return label


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
        record_type=str(data.get("record_type", "delivery")),
        name=str(data["name"]) if data.get("name") is not None else None,
        month=str(data["month"]) if data.get("month") is not None else None,
    )
