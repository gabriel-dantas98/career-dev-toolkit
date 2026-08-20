from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class EventDateCandidate:
    date: str
    evidence_link: str


@dataclass(frozen=True)
class EventDateResolution:
    status: str
    date: str | None
    source: str | None
    evidence_links: tuple[str, ...]
    queried_sources: tuple[str, ...]
    unavailable_sources: tuple[str, ...]


@dataclass(frozen=True)
class EnrichmentResult:
    status: str
    fields: Mapping[str, str | None]
    evidence_links: tuple[str, ...]
    unresolved_fields: tuple[str, ...]


def resolve_event_date(
    *,
    calendar_candidates: Sequence[EventDateCandidate],
    gmail_candidates: Sequence[EventDateCandidate],
) -> EventDateResolution:
    calendar_match = _first_resolved_candidate(calendar_candidates)
    if calendar_match is not None:
        return EventDateResolution(
            status="resolved",
            date=calendar_match.date,
            source="calendar",
            evidence_links=_candidate_links(calendar_match),
            queried_sources=("calendar",),
            unavailable_sources=(),
        )

    gmail_match = _first_resolved_candidate(gmail_candidates)
    if gmail_match is not None:
        return EventDateResolution(
            status="resolved",
            date=gmail_match.date,
            source="gmail",
            evidence_links=_candidate_links(gmail_match),
            queried_sources=("calendar", "gmail"),
            unavailable_sources=(),
        )

    return EventDateResolution(
        status="unresolved",
        date=None,
        source=None,
        evidence_links=(),
        queried_sources=("calendar", "gmail"),
        unavailable_sources=("luma",),
    )


def enrich_kudos(
    *,
    name: str | None,
    month: str | None,
    evidence_links: Sequence[str] = (),
) -> EnrichmentResult:
    return _enrichment_result(
        fields={"name": name, "month": month},
        required_fields=("name", "month"),
        evidence_links=evidence_links,
    )


def enrich_talk(
    *,
    title: str | None,
    event_date: str | None,
    evidence_links: Sequence[str] = (),
) -> EnrichmentResult:
    return _enrichment_result(
        fields={"title": title, "event_date": event_date},
        required_fields=("title", "event_date"),
        evidence_links=evidence_links,
    )


def enrich_credential(
    *,
    name: str | None,
    issuer: str | None,
    issued_on: str | None,
    evidence_links: Sequence[str] = (),
) -> EnrichmentResult:
    return _enrichment_result(
        fields={"name": name, "issuer": issuer, "issued_on": issued_on},
        required_fields=("name", "issuer", "issued_on"),
        evidence_links=evidence_links,
    )


def _enrichment_result(
    *,
    fields: Mapping[str, str | None],
    required_fields: Sequence[str],
    evidence_links: Sequence[str],
) -> EnrichmentResult:
    unresolved = tuple(
        field
        for field in required_fields
        if fields.get(field) is None or not str(fields[field]).strip()
    )
    return EnrichmentResult(
        status="resolved" if not unresolved else "unresolved",
        fields=MappingProxyType(dict(fields)),
        evidence_links=tuple(evidence_links),
        unresolved_fields=unresolved,
    )


def _first_resolved_candidate(
    candidates: Sequence[EventDateCandidate],
) -> EventDateCandidate | None:
    for candidate in candidates:
        if candidate.date.strip():
            return candidate
    return None


def _candidate_links(candidate: EventDateCandidate) -> tuple[str, ...]:
    if not candidate.evidence_link.strip():
        return ()
    return (candidate.evidence_link,)
