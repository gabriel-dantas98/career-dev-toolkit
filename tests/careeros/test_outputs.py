from dataclasses import replace

from careeros.models import DeliveryRecord, EvidenceRef
from careeros.outputs import (
    BRAG_DOCUMENT_GID,
    SHEETS_HOMEPAGE_GID,
    TIMELINE_CONTRACT_VERSION,
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

    packet = build_promo_packet((*work, *community))

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

    packet = build_promo_packet((*evidenced, *unsupported))

    assert packet.status == "insufficient_evidence"
    assert len(packet.work_cards) == 8
    assert packet.missing_work_cards == 2
    assert packet.unresolved_work_summary.count == 1
    assert packet.unresolved_work_summary.evidence_gaps == (
        "supporting link unavailable",
        "evidence.locator.required",
    )
    assert {card.record_id for card in packet.work_cards} == {
        record.id for record in evidenced
    }
    assert "delivery:synthetic-30" not in {
        card.record_id for card in packet.work_cards
    }


def test_empty_inputs_return_insufficient_packet_and_empty_valid_timeline() -> None:
    packet = build_promo_packet(())
    timeline = build_timeline(())

    assert packet.status == "insufficient_evidence"
    assert packet.work_cards == ()
    assert packet.missing_work_cards == 10
    assert packet.community_summary.count == 0
    assert packet.recognition_summary.count == 0
    assert packet.unresolved_work_summary.count == 0
    assert timeline.version == TIMELINE_CONTRACT_VERSION
    assert timeline.cards == ()
    assert timeline.unresolved_records == ()


def test_yearless_period_never_borrows_another_records_year() -> None:
    unresolved = synthetic_record(
        40,
        period="jan–jun",
        observed_at="",
    )
    dated = synthetic_record(
        41,
        period="Q3 2031",
        observed_at="2031-08-20T00:00:00+00:00",
    )

    timeline = build_timeline((unresolved, dated))

    assert [card.record_id for card in timeline.cards] == [dated.id]
    assert len(timeline.unresolved_records) == 1
    assert timeline.unresolved_records[0].record_id == unresolved.id
    assert timeline.unresolved_records[0].evidence_gaps == (
        "period.year.required",
    )


def test_yearless_period_uses_only_its_own_observed_at_year() -> None:
    record = synthetic_record(
        42,
        period="jan–jun",
        observed_at="2024-08-20T00:00:00+00:00",
    )

    card = build_timeline((record,)).cards[0]

    assert card.quarter_badges == ("Q1 2024", "Q2 2024")
    assert card.sort_start == "2024-01-01"
    assert card.evidence_gaps == ("period.year.inferred",)


def test_all_unresolved_yearless_inputs_are_explicit_and_do_not_crash() -> None:
    records = tuple(
        synthetic_record(index + 50, period="jan–jun", observed_at="")
        for index in range(10)
    )

    packet = build_promo_packet(records)
    timeline = build_timeline(records)

    assert packet.status == "insufficient_evidence"
    assert packet.work_cards == ()
    assert packet.unresolved_work_summary.count == 10
    assert len(packet.unresolved_work_summary.evidence_links) == 10
    assert timeline.cards == ()
    assert len(timeline.unresolved_records) == 10


def test_promo_sorts_undated_work_after_dated_work() -> None:
    undated = synthetic_record(61, period=None)
    dated = synthetic_record(62, period="Q1 2026")

    packet = build_promo_packet((undated, dated))

    assert [card.record_id for card in packet.work_cards] == [
        dated.id,
        undated.id,
    ]


def test_kudos_are_collapsed_as_recognition_and_never_consume_work_slots() -> None:
    work = tuple(synthetic_record(index + 70) for index in range(10))
    kudos = synthetic_record(
        90,
        title="[Kudos] Synthetic recognition",
        tags=("kudos",),
        context="kudos",
    )

    packet = build_promo_packet((*work, kudos))

    assert packet.status == "ready"
    assert len(packet.work_cards) == 10
    assert kudos.id not in {card.record_id for card in packet.work_cards}
    assert packet.recognition_summary.count == 1
    assert packet.recognition_summary.evidence_links == (
        "https://example.invalid/evidence/90",
    )


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

    timeline = build_timeline((unsupported, supported))
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

    card = build_timeline((record,)).cards[0]

    assert card.badges == ("impact", "community")
    assert card.quarter_badges == ("Q1 2026", "Q2 2026")
    assert all(not badge.startswith("Q") for badge in card.badges)
    assert card.sort_start == "2026-01-01"
    assert card.evidence_gaps == ("period.year.inferred",)


def test_timeline_ui_contract_has_version_and_required_card_fields() -> None:
    record = synthetic_record(
        100,
        period="Q2 2026",
        tags=("impact",),
        context="impact",
        title="[Impact] UI contract",
        result="Evidence-backed synthetic impact face.",
    )

    contract = build_timeline((record,))
    rendered = contract.as_dict()
    card = rendered["cards"][0]

    assert rendered["version"] == TIMELINE_CONTRACT_VERSION
    assert set(rendered) == {"version", "cards", "unresolvedRecords"}
    assert set(card) == {
        "recordId",
        "title",
        "face",
        "badges",
        "quarterBadges",
        "sortStart",
        "evidenceLinks",
        "evidenceGaps",
    }
    assert card["face"] == record.result
    assert card["badges"] == ["impact"]
    assert card["quarterBadges"] == ["Q2 2026"]


def test_timeline_sorts_dates_descending_and_same_date_record_ids_ascending() -> None:
    newest_b = synthetic_record(110, id="delivery:b", period="Q3 2026")
    newest_a = synthetic_record(111, id="delivery:a", period="Q3 2026")
    older = synthetic_record(112, id="delivery:z", period="Q2 2026")

    timeline = build_timeline((newest_b, older, newest_a))

    assert [card.record_id for card in timeline.cards] == [
        "delivery:a",
        "delivery:b",
        "delivery:z",
    ]


def test_dated_work_without_evidence_stays_in_unresolved_summary() -> None:
    dated_without_evidence = replace(
        synthetic_record(120, period="Q1 2026"),
        evidence=(),
        evidence_gaps=("supporting link unavailable",),
    )
    evidenced = synthetic_record(121, period="Q2 2026")

    packet = build_promo_packet((dated_without_evidence, evidenced))

    assert dated_without_evidence.id not in {
        card.record_id for card in packet.work_cards
    }
    assert packet.unresolved_work_summary.count == 1
    assert packet.unresolved_work_summary.evidence_gaps == (
        "supporting link unavailable",
        "evidence.locator.required",
    )
    assert packet.missing_work_cards == 9
