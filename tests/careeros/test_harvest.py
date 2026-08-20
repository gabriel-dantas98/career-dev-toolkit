from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from careeros.harvest import HarvestRequest, HarvestService, memory_store
from careeros.models import DeliveryRecord, EvidenceRef, RecordMetadata, ValidationIssue
from careeros.record_store import EncryptedRecordStore


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


def valid_delivery_record(*, record_id: str = "rec:test-001") -> DeliveryRecord:
    return DeliveryRecord(
        id=record_id,
        schema_version=1,
        source_connector="thread",
        source_locator="thread:test-001",
        title="[Impact] Stored delivery",
        period=None,
        tags=("impact",),
        context="impact",
        confidence="partial",
        situation=None,
        task=None,
        action=None,
        result="Synthetic stored result",
        evidence=(
            EvidenceRef(
                locator="thread:test-001",
                excerpt="Synthetic stored excerpt",
                observed_at="2026-01-15T00:00:00Z",
                connector="thread",
            ),
        ),
        evidence_gaps=(),
        content_fingerprint="fp-test-001",
        observed_at="2026-01-15T00:00:00Z",
        metadata=RecordMetadata(),
    )


@pytest.fixture
def record_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    migration = (
        Path(__file__).resolve().parents[2]
        / "careeros"
        / "migrations"
        / "001_initial.sql"
    )
    connection.executescript(migration.read_text())
    connection.commit()
    yield connection
    connection.close()


def test_harvest_merges_overlap_and_preserves_sources() -> None:
    result = HarvestService(memory_store()).run(overlap_request())
    assert len(result.records) == 1
    assert {ref.connector for ref in result.records[0].evidence} == {
        "thread",
        "github",
    }


def test_harvest_preserves_merged_provenance() -> None:
    result = HarvestService(memory_store()).run(overlap_request())
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
    result = HarvestService(store).run(invalid)
    assert any(issue.severity == "error" for issue in result.issues)
    assert result.persisted is False
    assert store.count_records() == 0


def test_invalid_impact_cannot_persist_with_default_validators() -> None:
    invalid = HarvestRequest(
        observations=(
            {
                "source_id": "thread:impact-invalid",
                "source_connector": "thread",
                "source_locator": "thread:impact-invalid",
                "title": "[Impact] Claim without proof",
                "tags": ("impact",),
                "result": "Improved latency by 40%",
                "provenance": (),
                "excerpt": "Synthetic impact claim without linked evidence",
                "observed_at": "2026-01-15T00:00:00Z",
            },
        )
    )
    store = memory_store()
    result = HarvestService(store).run(invalid)
    assert result.persisted is False
    assert store.count_records() == 0
    assert "impact.evidence.missing" in {issue.rule_id for issue in result.issues}


def test_harvest_persists_valid_records_transactionally() -> None:
    store = memory_store()
    result = HarvestService(store).run(overlap_request())
    assert result.persisted is True
    assert store.count_records() == 1
    row = store.get_record(result.records[0].id)
    assert row is not None
    assert len(row["evidence"]) == 2


def test_harvest_rolls_back_on_persist_failure() -> None:
    class FailingStore:
        def count_records(self) -> int:
            return 0

        def get_record(self, record_id: str) -> dict[str, object] | None:
            return None

        def persist_records(self, records: tuple[DeliveryRecord, ...]) -> None:
            raise RuntimeError("persist failed")

    result = HarvestService(FailingStore()).run(overlap_request())
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
    result = HarvestService(memory_store()).run(invalid)
    assert all(isinstance(issue, ValidationIssue) for issue in result.issues)
    assert any(issue.rule_id == "taxonomy.prefix.required" for issue in result.issues)


def test_encrypted_record_store_commits_atomically(record_connection) -> None:
    store = EncryptedRecordStore(record_connection)
    records = (valid_delivery_record(),)
    store.persist_records(records)
    assert store.count_records() == 1
    row = store.get_record("rec:test-001")
    assert row is not None
    assert len(row["evidence"]) == 1


def test_encrypted_record_store_rolls_back_on_failure(record_connection) -> None:
    store = EncryptedRecordStore(record_connection)
    records = (
        valid_delivery_record(record_id="rec:test-001"),
        valid_delivery_record(record_id="rec:test-001"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.persist_records(records)
    assert store.count_records() == 0


def test_encrypted_record_store_from_encrypted_store(store) -> None:
    record_store = EncryptedRecordStore.from_encrypted_store(store)
    record_store.persist_records((valid_delivery_record(record_id="rec:encrypted-001"),))
    assert record_store.count_records() == 1
