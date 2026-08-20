from dataclasses import replace

from careeros.models import DeliveryRecord, EvidenceRef
from careeros.outputs import (
    BRAG_DOCUMENT_GID,
    SHEETS_HOMEPAGE_GID,
    build_homepage,
    build_promo_packet,
    build_timeline,
)


def synthetic_record(index: int, **overrides: object) -> DeliveryRecord:
    base: dict[str, object] = {
        "id": f"delivery:synthetic-{index:02d}",
        "schema_version": 1,
        "source_connector": "thread",
        "source_locator": f"thread:synthetic-{index:02d}",
        "title": f"[Delivery] Synthetic work {index:02d}",
        "period": f"Q{(index % 4) + 1} 2026",
        "tags": ("delivery",),
        "context": "delivery",
        "confidence": "complete",
        "situation": "Synthetic situation.",
        "task": "Synthetic task.",
        "action": f"Implemented synthetic action {index:02d}.",
        "result": f"Supported synthetic impact {index:02d}.",
        "evidence": (
            EvidenceRef(
                locator=f"https://example.invalid/evidence/{index:02d}",
                excerpt="Synthetic evidence.",
                observed_at="2026-08-20T00:00:00+00:00",
                connector="thread",
            ),
        ),
        "evidence_gaps": (),
        "content_fingerprint": f"synthetic-fingerprint-{index:02d}",
        "observed_at": "2026-08-20T00:00:00+00:00",
    }
    base.update(overrides)
    return DeliveryRecord(**base)  # type: ignore[arg-type]


def test_homepage_defaults_to_brag_document_gid_not_sheets_homepage_gid() -> None:
    homepage = build_homepage(
        "https://script.google.com/macros/s/AKfycbSynthetic_123/exec"
    )

    assert BRAG_DOCUMENT_GID == 425749964
    assert SHEETS_HOMEPAGE_GID == 389581671
    assert homepage["source"] == {
        "kind": "brag-document",
        "gid": BRAG_DOCUMENT_GID,
    }
    assert homepage["source"]["gid"] != SHEETS_HOMEPAGE_GID


def test_homepage_accepts_configured_brag_document_gid() -> None:
    homepage = build_homepage(
        "https://script.google.com/macros/s/AKfycbSynthetic_123/exec",
        brag_document_gid=123456789,
    )

    assert homepage["source"]["gid"] == 123456789


def test_promo_packet_selects_at_most_twelve_work_cards_and_collapses_community() -> None:
    work = tuple(synthetic_record(index) for index in range(13))
    community = tuple(
        synthetic_record(
            20 + index,
            title=f"[Community] Synthetic community {index}",
            tags=("community",),
            context="community",
        )
        for index in range(3)
    )

    packet = build_promo_packet((*work, *community), reference_year=2026)

    assert packet.status == "ready"
    assert len(packet.work_cards) == 12
    assert all(card.evidence_links for card in packet.work_cards)
    assert packet.community_summary.count == 3
    assert len(packet.community_summary.evidence_links) == 3
    assert all("community" not in card.delivery_types for card in packet.work_cards)


def test_promo_packet_reports_insufficient_evidence_without_fabricating_cards() -> None:
    evidenced = tuple(synthetic_record(index) for index in range(8))
    unsupported = (
        replace(
            synthetic_record(30),
            evidence=(),
            evidence_gaps=("supporting link unavailable",),
        ),
    )

    packet = build_promo_packet((*evidenced, *unsupported), reference_year=2026)

    assert packet.status == "insufficient_evidence"
    assert len(packet.work_cards) == 8
    assert packet.missing_work_cards == 2
    assert {card.record_id for card in packet.work_cards} == {
        record.id for record in evidenced
    }
    assert "delivery:synthetic-30" not in {
        card.record_id for card in packet.work_cards
    }


def test_timeline_face_prioritizes_evidence_backed_impact() -> None:
    supported = synthetic_record(
        1,
        tags=("impact",),
        context="impact",
        title="[Impact] Supported result",
        result="Reduced synthetic latency with linked measurements.",
        action="Changed a synthetic code path.",
    )
    unsupported = synthetic_record(
        2,
        tags=("impact",),
        context="impact",
        title="[Impact] Unsupported result",
        result="Claimed unsupported synthetic impact.",
        action="Changed another synthetic code path.",
        evidence=(),
        evidence_gaps=("impact evidence unavailable",),
    )

    timeline = build_timeline((unsupported, supported), reference_year=2026)
    cards = {card.record_id: card for card in timeline.cards}

    assert cards[supported.id].face == supported.result
    assert cards[unsupported.id].face == unsupported.action
    assert cards[unsupported.id].evidence_gaps == unsupported.evidence_gaps


def test_timeline_badges_are_delivery_types_and_quarters_use_shared_date_order() -> None:
    record = synthetic_record(
        4,
        period="jan–jun",
        tags=("impact", "community"),
        context="impact",
    )

    card = build_timeline((record,), reference_year=2026).cards[0]

    assert card.badges == ("impact", "community")
    assert card.quarter_badges == ("Q1 2026", "Q2 2026")
    assert all(not badge.startswith("Q") for badge in card.badges)
    assert card.sort_start == "2026-01-01"
