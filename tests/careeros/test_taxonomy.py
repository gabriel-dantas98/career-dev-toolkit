from careeros.models import DeliveryRecord, EvidenceRef
from careeros.taxonomy import (
    apply_confidence_cap,
    classify_context,
    normalize_delivery_prefix,
)


def _delivery(**overrides: object) -> DeliveryRecord:
    base = {
        "id": "rec-synthetic-001",
        "schema_version": 1,
        "source_connector": "thread",
        "source_locator": "thread:synthetic-001",
        "title": "[Impact] Synthetic delivery",
        "period": "Q1 2026",
        "tags": ("impact",),
        "context": None,
        "confidence": "complete",
        "situation": "Synthetic situation",
        "task": "Synthetic task",
        "action": "Synthetic action",
        "result": "Synthetic result",
        "evidence": (
            EvidenceRef(
                locator="https://github.test/org/repo/pull/1",
                excerpt="Synthetic PR excerpt",
                observed_at="2026-01-15T00:00:00Z",
            ),
        ),
        "evidence_gaps": (),
        "content_fingerprint": "fp-synthetic-001",
        "observed_at": "2026-01-15T00:00:00Z",
    }
    base.update(overrides)
    return DeliveryRecord(**base)


def test_classify_context_from_tags() -> None:
    record = _delivery(tags=("community", "mentoring"))
    assert classify_context(record) == "community"


def test_normalize_delivery_prefix_adds_missing_prefix() -> None:
    assert normalize_delivery_prefix("Shipped parser", tags=("impact",)) == "[Impact] Shipped parser"


def test_apply_confidence_cap_downgrades_without_evidence() -> None:
    record = _delivery(confidence="complete", evidence=())
    assert apply_confidence_cap(record) == "partial"


def test_apply_confidence_cap_preserves_complete_with_evidence() -> None:
    record = _delivery(confidence="complete")
    assert apply_confidence_cap(record) == "complete"
