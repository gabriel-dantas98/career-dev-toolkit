from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from careeros.dates import parse_period, quarters_for, sort_start
from careeros.models import DeliveryRecord
from careeros.taxonomy import TAG_PREFIXES, classify_context
from careeros.urls import validate_google_exec_url

BRAG_DOCUMENT_GID = 425749964
SHEETS_HOMEPAGE_GID = 389581671
TIMELINE_CONTRACT_VERSION = "1.0.0"
MIN_PROMO_WORK_CARDS = 10
MAX_PROMO_WORK_CARDS = 12

_YEAR = re.compile(r"\b(\d{4})\b")
_OBSERVED_YEAR = re.compile(
    r"^(\d{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?:T|$)"
)


@dataclass(frozen=True)
class WorkCard:
    record_id: str
    title: str
    period: str | None
    delivery_types: tuple[str, ...]
    result: str | None
    evidence_links: tuple[str, ...]
    evidence_gaps: tuple[str, ...]


@dataclass(frozen=True)
class CommunitySummary:
    count: int
    evidence_links: tuple[str, ...]
    evidence_gaps: tuple[str, ...]


@dataclass(frozen=True)
class RecognitionSummary:
    count: int
    evidence_links: tuple[str, ...]
    evidence_gaps: tuple[str, ...]


@dataclass(frozen=True)
class UnresolvedWorkSummary:
    count: int
    evidence_links: tuple[str, ...]
    evidence_gaps: tuple[str, ...]


@dataclass(frozen=True)
class PromotionPacket:
    status: str
    work_cards: tuple[WorkCard, ...]
    community_summary: CommunitySummary
    recognition_summary: RecognitionSummary
    unresolved_work_summary: UnresolvedWorkSummary
    missing_work_cards: int


@dataclass(frozen=True)
class TimelineCard:
    record_id: str
    title: str
    face: str
    badges: tuple[str, ...]
    quarter_badges: tuple[str, ...]
    sort_start: str
    evidence_links: tuple[str, ...]
    evidence_gaps: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "recordId": self.record_id,
            "title": self.title,
            "face": self.face,
            "badges": list(self.badges),
            "quarterBadges": list(self.quarter_badges),
            "sortStart": self.sort_start,
            "evidenceLinks": list(self.evidence_links),
            "evidenceGaps": list(self.evidence_gaps),
        }


@dataclass(frozen=True)
class TimelineUnresolvedRecord:
    record_id: str
    evidence_links: tuple[str, ...]
    evidence_gaps: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "recordId": self.record_id,
            "evidenceLinks": list(self.evidence_links),
            "evidenceGaps": list(self.evidence_gaps),
        }


@dataclass(frozen=True)
class TimelineContract:
    cards: tuple[TimelineCard, ...]
    unresolved_records: tuple[TimelineUnresolvedRecord, ...] = ()
    version: str = TIMELINE_CONTRACT_VERSION

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "cards": [card.as_dict() for card in self.cards],
            "unresolvedRecords": [
                record.as_dict() for record in self.unresolved_records
            ],
        }


@dataclass(frozen=True)
class _PeriodResolution:
    status: str
    sort_start: str
    quarter_badges: tuple[str, ...]
    evidence_gaps: tuple[str, ...]


def build_homepage(
    web_app_url: str,
    *,
    brag_document_gid: int = BRAG_DOCUMENT_GID,
) -> dict[str, object]:
    validate_google_exec_url(web_app_url)
    if (
        isinstance(brag_document_gid, bool)
        or not isinstance(brag_document_gid, int)
        or brag_document_gid < 0
    ):
        raise ValueError("brag_document_gid must be a non-negative integer")
    if brag_document_gid == SHEETS_HOMEPAGE_GID:
        raise ValueError("Homepage source must use the brag-document gid")
    return {
        "webAppUrl": web_app_url,
        "source": {
            "kind": "brag-document",
            "gid": brag_document_gid,
        },
    }


def build_promo_packet(
    records: Sequence[DeliveryRecord],
    community_records: Sequence[DeliveryRecord] = (),
    *,
    reference_year: int | None = None,
) -> PromotionPacket:
    # Retained for call compatibility. Output periods never use a global fallback.
    del reference_year
    all_records = tuple(records)
    explicit_community = tuple(community_records)

    work: list[DeliveryRecord] = []
    community: list[DeliveryRecord] = list(explicit_community)
    recognition: list[DeliveryRecord] = []
    explicit_ids = {record.id for record in explicit_community}
    for record in all_records:
        if record.id in explicit_ids:
            continue
        context = classify_context(record)
        if context == "community":
            community.append(record)
        elif context == "kudos":
            recognition.append(record)
        else:
            work.append(record)

    eligible: list[tuple[DeliveryRecord, _PeriodResolution]] = []
    unresolved: list[tuple[DeliveryRecord, _PeriodResolution]] = []
    for record in work:
        resolution = _resolve_record_period(record)
        if resolution.status == "unresolved":
            unresolved.append((record, resolution))
        elif _evidence_links(record):
            eligible.append((record, resolution))

    eligible.sort(key=_promo_sort_key)
    selected = eligible[:MAX_PROMO_WORK_CARDS]
    cards = tuple(_work_card(record) for record, _resolution in selected)
    missing = max(0, MIN_PROMO_WORK_CARDS - len(cards))
    status = "ready" if missing == 0 else "insufficient_evidence"

    return PromotionPacket(
        status=status,
        work_cards=cards,
        community_summary=CommunitySummary(**_summary_values(community)),
        recognition_summary=RecognitionSummary(**_summary_values(recognition)),
        unresolved_work_summary=UnresolvedWorkSummary(
            count=len(unresolved),
            evidence_links=_combined_evidence_links(
                [record for record, _resolution in unresolved]
            ),
            evidence_gaps=tuple(
                gap
                for record, resolution in sorted(
                    unresolved,
                    key=lambda item: item[0].id,
                )
                for gap in (*record.evidence_gaps, *resolution.evidence_gaps)
            ),
        ),
        missing_work_cards=missing,
    )


def build_timeline(
    records: Sequence[DeliveryRecord],
    *,
    reference_year: int | None = None,
) -> TimelineContract:
    # Retained for call compatibility. Output periods never use a global fallback.
    del reference_year
    normalized = tuple(records)
    cards: list[TimelineCard] = []
    unresolved: list[TimelineUnresolvedRecord] = []
    for record in normalized:
        resolution = _resolve_record_period(record)
        if resolution.status == "unresolved":
            unresolved.append(
                TimelineUnresolvedRecord(
                    record_id=record.id,
                    evidence_links=_evidence_links(record),
                    evidence_gaps=(
                        *record.evidence_gaps,
                        *resolution.evidence_gaps,
                    ),
                )
            )
        else:
            cards.append(_timeline_card(record, resolution))

    # Stable two-pass ordering makes date descending and equal-date IDs ascending.
    cards.sort(key=lambda card: card.record_id)
    cards.sort(key=lambda card: card.sort_start, reverse=True)
    return TimelineContract(
        cards=tuple(cards),
        unresolved_records=tuple(
            sorted(unresolved, key=lambda record: record.record_id)
        ),
    )


def _timeline_card(
    record: DeliveryRecord,
    resolution: _PeriodResolution,
) -> TimelineCard:
    delivery_types = _delivery_types(record)
    evidence_links = _evidence_links(record)

    impact_is_supported = (
        "impact" in delivery_types
        and bool(evidence_links)
        and bool(record.result and record.result.strip())
    )
    if impact_is_supported:
        face = str(record.result).strip()
    elif record.action and record.action.strip():
        face = record.action.strip()
    else:
        face = record.title

    return TimelineCard(
        record_id=record.id,
        title=record.title,
        face=face,
        badges=delivery_types,
        quarter_badges=resolution.quarter_badges,
        sort_start=resolution.sort_start,
        evidence_links=evidence_links,
        evidence_gaps=tuple(record.evidence_gaps),
    )


def _work_card(record: DeliveryRecord) -> WorkCard:
    return WorkCard(
        record_id=record.id,
        title=record.title,
        period=record.period,
        delivery_types=_delivery_types(record),
        result=record.result,
        evidence_links=_evidence_links(record),
        evidence_gaps=tuple(record.evidence_gaps),
    )


def _promo_sort_key(
    item: tuple[DeliveryRecord, _PeriodResolution],
) -> tuple[int, int, int, str]:
    record, resolution = item
    delivery_types = _delivery_types(record)
    impact_priority = 0 if "impact" in delivery_types else 1
    is_undated = 1 if resolution.status == "undated" else 0
    date_number = (
        int(resolution.sort_start.replace("-", ""))
        if resolution.sort_start
        else 0
    )
    return is_undated, -date_number, impact_priority, record.id


def _delivery_types(record: DeliveryRecord) -> tuple[str, ...]:
    types: list[str] = []
    for tag in record.tags:
        normalized = tag.strip().lower()
        if normalized in TAG_PREFIXES and normalized not in types:
            types.append(normalized)
    context = classify_context(record)
    if context in TAG_PREFIXES and context not in types:
        types.append(context)
    if not types:
        types.append("delivery")
    return tuple(types)


def _evidence_links(record: DeliveryRecord) -> tuple[str, ...]:
    links: list[str] = []
    for evidence in record.evidence:
        locator = evidence.locator.strip()
        if locator and locator not in links:
            links.append(locator)
    return tuple(links)


def _combined_evidence_links(records: Sequence[DeliveryRecord]) -> tuple[str, ...]:
    links: list[str] = []
    for record in sorted(records, key=lambda item: item.id):
        for link in _evidence_links(record):
            if link not in links:
                links.append(link)
    return tuple(links)


def _summary_values(records: Sequence[DeliveryRecord]) -> dict[str, object]:
    return {
        "count": len(records),
        "evidence_links": _combined_evidence_links(records),
        "evidence_gaps": tuple(
            gap
            for record in sorted(records, key=lambda item: item.id)
            for gap in record.evidence_gaps
        ),
    }


def _resolve_record_period(record: DeliveryRecord) -> _PeriodResolution:
    raw_period = (record.period or "").strip()
    if not raw_period:
        return _PeriodResolution(
            status="undated",
            sort_start="",
            quarter_badges=(),
            evidence_gaps=(),
        )

    period_year = _YEAR.search(raw_period)
    if period_year is not None:
        reference_year = int(period_year.group(1))
    else:
        observed_year = _OBSERVED_YEAR.match(record.observed_at.strip())
        if observed_year is None:
            return _PeriodResolution(
                status="unresolved",
                sort_start="",
                quarter_badges=(),
                evidence_gaps=("period.year.required",),
            )
        reference_year = int(observed_year.group(1))

    try:
        period = parse_period(raw_period, reference_year=reference_year)
    except ValueError:
        return _PeriodResolution(
            status="unresolved",
            sort_start="",
            quarter_badges=(),
            evidence_gaps=("period.invalid",),
        )
    return _PeriodResolution(
        status="dated",
        sort_start=sort_start(period),
        quarter_badges=quarters_for(period),
        evidence_gaps=(),
    )


def timeline_mapping(value: TimelineContract | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, TimelineContract):
        return value.as_dict()
    return {str(key): item for key, item in value.items()}
