from __future__ import annotations

import pytest

from careeros.harvest import HarvestRequest, HarvestService, memory_store
from careeros.models import DeliveryRecord, EvidenceRef, ValidationIssue
from careeros.validation import validate_records


def overlap_request() -> HarvestRequest:
    return HarvestRequest(
        observations=(
            {
                "source_id": "github:pull/1",
                "source_connector": "github",
                "source_locator": "https://github.test/org/repo/pull/1",
                "title": "[Impact] Synthetic delivery",
                "tags": ("impact",),
                "jira_key": "SYN-42",
                "pr_locator": "https://github.test/org/repo/pull/1",
                "provenance": ("github",),
                "excerpt": "Synthetic GitHub excerpt",
                "observed_at": "2026-01-15T00:00:00Z",
            },
            {
                "source_id": "thread:msg-9",
                "source_connector": "thread",
                "source_locator": "thread:msg-9",
                "title": "[Impact] Synthetic delivery",
                "tags": ("impact",),
                "jira_key": "SYN-42",
                "pr_locator": "https://github.test/org/repo/pull/1",
                "provenance": ("thread",),
                "excerpt": "Synthetic thread excerpt",
                "observed_at": "2026-01-15T00:00:00Z",
            },
        )
    )


def test_harvest_merges_overlap_and_preserves_sources() -> None:
    result = HarvestService(memory_store(), validators=[]).run(overlap_request())
    assert len(result.records) == 1
    assert {ref.connector for ref in result.records[0].evidence} == {
        "thread",
        "github",
    }


def test_harvest_preserves_merged_provenance() -> None:
    result = HarvestService(memory_store(), validators=[]).run(overlap_request())
    record = result.records[0]
    assert set(record.metadata.merged_source_ids) == {
        "github:pull/1",
        "thread:msg-9",
    }
    assert set(record.metadata.provenance) == {"github", "thread"}


def test_harvest_does_not_persist_on_validation_errors() -> None:
    invalid = HarvestRequest(
        observations=(
            {
                "source_id": "thread:invalid-1",
                "source_connector": "thread",
                "source_locator": "thread:invalid-1",
                "title": "Missing prefix",
                "tags": ("impact",),
                "provenance": ("thread",),
                "excerpt": "Synthetic invalid excerpt",
                "observed_at": "2026-01-15T00:00:00Z",
            },
        )
    )
    store = memory_store()
    result = HarvestService(store, validators=[validate_records]).run(invalid)
    assert any(issue.severity == "error" for issue in result.issues)
    assert result.persisted is False
    assert store.count_records() == 0


def test_harvest_persists_valid_records_transactionally() -> None:
    store = memory_store()
    result = HarvestService(store, validators=[validate_records]).run(overlap_request())
    assert result.persisted is True
    assert store.count_records() == 1
    row = store.get_record(result.records[0].id)
    assert row is not None
    assert len(row["evidence"]) == 2


def test_harvest_rolls_back_on_persist_failure() -> None:
    class FailingStore:
        def __init__(self) -> None:
            self.committed = False

        def count_records(self) -> int:
            return 0

        def get_record(self, record_id: str) -> dict[str, object] | None:
            return None

        def persist_records(self, records: tuple[DeliveryRecord, ...]) -> None:
            raise RuntimeError("persist failed")

    result = HarvestService(FailingStore(), validators=[]).run(overlap_request())
    assert result.persisted is False


def test_harvest_result_includes_validation_issues() -> None:
    invalid = HarvestRequest(
        observations=(
            {
                "source_id": "thread:invalid-2",
                "source_connector": "thread",
                "source_locator": "thread:invalid-2",
                "title": "Missing prefix",
                "tags": ("impact",),
                "provenance": ("thread",),
                "excerpt": "Synthetic invalid excerpt",
                "observed_at": "2026-01-15T00:00:00Z",
            },
        )
    )
    result = HarvestService(memory_store(), validators=[validate_records]).run(invalid)
    assert all(isinstance(issue, ValidationIssue) for issue in result.issues)
    assert any(issue.rule_id == "taxonomy.prefix.required" for issue in result.issues)
