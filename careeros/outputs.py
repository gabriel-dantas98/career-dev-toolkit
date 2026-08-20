from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from careeros.dates import parse_period, quarters_for, sort_start
from careeros.models import DeliveryRecord
from careeros.taxonomy import TAG_PREFIXES, classify_context

BRAG_DOCUMENT_GID = 425749964
SHEETS_HOMEPAGE_GID = 389581671
TIMELINE_CONTRACT_VERSION = "1.0.0"
MIN_PROMO_WORK_CARDS = 10
MAX_PROMO_WORK_CARDS = 12

_YEAR = re.compile(r"\b(\d{4})\b")


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
class PromotionPacket:
    status: str
    work_cards: tuple[WorkCard, ...]
    community_summary: CommunitySummary
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
class TimelineContract:
    cards: tuple[TimelineCard, ...]
    version: str = TIMELINE_CONTRACT_VERSION

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "cards": [card.as_dict() for card in self.cards],
        }


def build_homepage(
    web_app_url: str,
    *,
    brag_document_gid: int = BRAG_DOCUMENT_GID,
) -> dict[str, object]:
    _require_google_exec_url(web_app_url)
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
    all_records = tuple(records)
    explicit_community = tuple(community_records)
    year = _resolve_reference_year((*all_records, *explicit_community), reference_year)

    work: list[DeliveryRecord] = []
    community: list[DeliveryRecord] = list(explicit_community)
    explicit_ids = {record.id for record in explicit_community}
    for record in all_records:
        if record.id in explicit_ids:
            continue
        if classify_context(record) == "community":
            community.append(record)
        else:
            work.append(record)

    eligible = [record for record in work if _evidence_links(record)]
    eligible.sort(key=lambda record: _promo_sort_key(record, year))
    selected = eligible[:MAX_PROMO_WORK_CARDS]
    cards = tuple(_work_card(record) for record in selected)
    missing = max(0, MIN_PROMO_WORK_CARDS - len(cards))
    status = "ready" if missing == 0 else "insufficient_evidence"

    return PromotionPacket(
        status=status,
        work_cards=cards,
        community_summary=CommunitySummary(
            count=len(community),
            evidence_links=_combined_evidence_links(community),
            evidence_gaps=tuple(
                gap
                for record in sorted(community, key=lambda item: item.id)
                for gap in record.evidence_gaps
            ),
        ),
        missing_work_cards=missing,
    )


def build_timeline(
    records: Sequence[DeliveryRecord],
    *,
    reference_year: int | None = None,
) -> TimelineContract:
    normalized = tuple(records)
    year = _resolve_reference_year(normalized, reference_year)
    cards = tuple(_timeline_card(record, year) for record in normalized)
    ordered = tuple(
        sorted(
            cards,
            key=lambda card: (card.sort_start, card.record_id),
            reverse=True,
        )
    )
    return TimelineContract(cards=ordered)


def _timeline_card(record: DeliveryRecord, reference_year: int) -> TimelineCard:
    delivery_types = _delivery_types(record)
    evidence_links = _evidence_links(record)
    period_start = ""
    quarter_badges: tuple[str, ...] = ()
    if record.period and record.period.strip():
        try:
            parsed = parse_period(record.period, reference_year=reference_year)
        except ValueError:
            pass
        else:
            period_start = sort_start(parsed)
            quarter_badges = quarters_for(parsed)

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
        quarter_badges=quarter_badges,
        sort_start=period_start,
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


def _promo_sort_key(record: DeliveryRecord, reference_year: int) -> tuple[int, str, str]:
    delivery_types = _delivery_types(record)
    impact_priority = 0 if "impact" in delivery_types else 1
    start = ""
    if record.period and record.period.strip():
        try:
            start = sort_start(parse_period(record.period, reference_year=reference_year))
        except ValueError:
            pass
    inverted_start = "".join(chr(255 - ord(character)) for character in start)
    return impact_priority, inverted_start, record.id


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


def _resolve_reference_year(
    records: Sequence[DeliveryRecord],
    configured: int | None,
) -> int:
    if configured is not None:
        if isinstance(configured, bool) or configured < 1:
            raise ValueError("reference_year must be a positive integer")
        return configured

    years: list[int] = []
    for record in records:
        for candidate in (record.period or "", record.observed_at):
            years.extend(int(match) for match in _YEAR.findall(candidate))
    if not years:
        raise ValueError("reference_year is required when records contain no year")
    return max(years)


def _require_google_exec_url(value: str) -> None:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "script.google.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith("/exec")
    ):
        raise ValueError("web_app_url must be an exact Google Apps Script /exec URL")


def timeline_mapping(value: TimelineContract | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, TimelineContract):
        return value.as_dict()
    return {str(key): item for key, item in value.items()}
