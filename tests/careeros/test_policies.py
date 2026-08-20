from dataclasses import replace

from careeros.enrichment import (
    EventDateCandidate,
    enrich_credential,
    enrich_kudos,
    enrich_talk,
    resolve_event_date,
)
from careeros.models import DeliveryRecord, EvidenceRef
from careeros.outputs import build_timeline
from careeros.policies import HeroMetric, timeline_parity, validate_hero_metrics
from careeros.review import leader_review


def synthetic_record(**overrides: object) -> DeliveryRecord:
    base: dict[str, object] = {
        "id": "delivery:synthetic-review",
        "schema_version": 1,
        "source_connector": "thread",
        "source_locator": "thread:synthetic-review",
        "title": "[Impact] Synthetic review record",
        "period": "Q2 2026",
        "tags": ("impact",),
        "context": "impact",
        "confidence": "complete",
        "situation": "Synthetic situation.",
        "task": "Synthetic task.",
        "action": "Synthetic action.",
        "result": "Synthetic supported result.",
        "evidence": (
            EvidenceRef(
                locator="https://example.invalid/evidence/review",
                excerpt="Synthetic evidence.",
                observed_at="2026-08-20T00:00:00+00:00",
                connector="thread",
            ),
        ),
        "evidence_gaps": (),
        "content_fingerprint": "synthetic-review-fingerprint",
        "observed_at": "2026-08-20T00:00:00+00:00",
    }
    base.update(overrides)
    return DeliveryRecord(**base)  # type: ignore[arg-type]


def test_hero_metrics_require_supporting_evidence_links() -> None:
    findings = validate_hero_metrics(
        (
            HeroMetric(
                label="Synthetic adoption",
                value="42",
                kind="derived",
                evidence_links=(),
            ),
            HeroMetric(
                label="Synthetic reliability",
                value="99.9%",
                kind="outcome",
                evidence_links=("https://example.invalid/evidence/metric",),
            ),
        )
    )

    assert [(finding.rule_id, finding.metric_label) for finding in findings] == [
        ("hero_metric.evidence.required", "Synthetic adoption")
    ]


def test_vanity_metric_without_links_is_never_accepted() -> None:
    findings = validate_hero_metrics(
        (
            HeroMetric(
                label="Synthetic views",
                value="1000",
                kind="vanity",
                evidence_links=("",),
            ),
        )
    )

    assert {finding.rule_id for finding in findings} == {
        "hero_metric.evidence.required"
    }


def test_event_date_resolution_prefers_calendar_then_gmail() -> None:
    calendar = EventDateCandidate(
        date="2026-04-10",
        evidence_link="https://calendar.invalid/event/synthetic",
    )
    gmail = EventDateCandidate(
        date="2026-04-11",
        evidence_link="https://mail.invalid/message/synthetic",
    )

    calendar_result = resolve_event_date(
        calendar_candidates=(calendar,),
        gmail_candidates=(gmail,),
    )
    gmail_result = resolve_event_date(
        calendar_candidates=(),
        gmail_candidates=(gmail,),
    )

    assert calendar_result.status == "resolved"
    assert calendar_result.source == "calendar"
    assert calendar_result.date == calendar.date
    assert calendar_result.queried_sources == ("calendar",)
    assert gmail_result.source == "gmail"
    assert gmail_result.date == gmail.date
    assert gmail_result.queried_sources == ("calendar", "gmail")


def test_event_date_marks_luma_unavailable_without_claiming_it_was_queried() -> None:
    result = resolve_event_date(calendar_candidates=(), gmail_candidates=())

    assert result.status == "unresolved"
    assert result.date is None
    assert result.queried_sources == ("calendar", "gmail")
    assert result.unavailable_sources == ("luma",)
    assert "luma" not in result.queried_sources


def test_kudos_enrichment_requires_name_and_month() -> None:
    result = enrich_kudos(
        name="",
        month=None,
        evidence_links=("https://mail.invalid/message/kudos",),
    )

    assert result.status == "unresolved"
    assert result.unresolved_fields == ("name", "month")
    assert result.evidence_links == ("https://mail.invalid/message/kudos",)


def test_talk_and_credential_enrichment_preserve_links_and_unresolved_states() -> None:
    talk = enrich_talk(
        title="Synthetic talk",
        event_date=None,
        evidence_links=("https://events.invalid/talk",),
    )
    credential = enrich_credential(
        name="Synthetic credential",
        issuer=None,
        issued_on=None,
        evidence_links=("https://credentials.invalid/item",),
    )

    assert talk.status == "unresolved"
    assert talk.unresolved_fields == ("event_date",)
    assert talk.evidence_links == ("https://events.invalid/talk",)
    assert credential.status == "unresolved"
    assert credential.unresolved_fields == ("issuer", "issued_on")
    assert credential.evidence_links == ("https://credentials.invalid/item",)


def test_leader_review_is_deterministic_and_emits_findings_not_verdicts() -> None:
    supported = synthetic_record()
    unsupported = replace(
        supported,
        id="delivery:synthetic-gap",
        confidence="partial",
        evidence=(),
        evidence_gaps=("impact evidence unavailable",),
    )

    forward = leader_review((supported, unsupported))
    reverse = leader_review((unsupported, supported))

    assert forward == reverse
    assert forward.findings
    assert all(finding.rule_id for finding in forward.findings)
    assert not hasattr(forward, "verdict")
    assert not hasattr(forward, "promotion_recommendation")
    assert "promote" not in repr(forward).lower()
    assert "level" not in repr(forward).lower()


def test_timeline_parity_compares_complete_apps_script_compatible_preview() -> None:
    timeline = build_timeline((synthetic_record(),), reference_year=2026)
    preview = timeline.as_dict()

    matching = timeline_parity(timeline, preview)
    changed_preview = {
        **preview,
        "cards": [{**preview["cards"][0], "face": "Different synthetic face"}],
    }
    mismatch = timeline_parity(timeline, changed_preview)

    assert matching.matches is True
    assert matching.differences == ()
    assert mismatch.matches is False
    assert mismatch.differences == ("cards[0].face",)
