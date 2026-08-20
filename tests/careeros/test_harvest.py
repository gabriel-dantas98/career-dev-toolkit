from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from careeros.harvest import HarvestRequest, HarvestService, memory_store
from careeros.models import DeliveryRecord, EvidenceRef, RecordMetadata, ValidationIssue
from careeros.record_metadata import deserialize_metadata, serialize_metadata
from careeros.record_store import EncryptedRecordStore
from careeros.store import CURRENT_MIGRATION_VERSION


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
                "pr_status": "merged",
                "narrative_status": "merged",
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
                "observed_at": "2026-01-16T00:00:00Z",
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
        metadata=RecordMetadata(
            jira_key="SYN-STORE-1",
            pr_status="merged",
            narrative_status="merged",
            epic_parent="SYN-EPIC-9",
            provenance=("thread", "github"),
            merged_source_ids=("thread:test-001", "github:pull/9"),
            evidence_locators=("thread:test-001",),
        ),
    )


def _apply_migrations(connection: sqlite3.Connection) -> None:
    migrations_dir = Path(__file__).resolve().parents[2] / "careeros" / "migrations"
    for version in range(1, CURRENT_MIGRATION_VERSION + 1):
        migration_file = sorted(migrations_dir.glob(f"{version:03d}_*.sql"))[0]
        connection.executescript(migration_file.read_text())
        connection.execute(
            "INSERT INTO migrations (version, applied_at) VALUES (?, ?)",
            (version, "2026-01-01T00:00:00+00:00"),
        )
    connection.commit()


@pytest.fixture
def record_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    _apply_migrations(connection)
    yield connection
    connection.close()


def test_metadata_json_round_trip_is_canonical() -> None:
    metadata = RecordMetadata(
        jira_key="SYN-42",
        pr_status="merged",
        narrative_status="merged",
        epic_parent="SYN-EPIC-1",
        provenance=("github", "thread"),
        merged_source_ids=("github:pull/1", "thread:msg-9"),
        evidence_locators=(
            "https://github.test/org/repo/pull/1",
            "thread:msg-9",
        ),
    )
    encoded = serialize_metadata(metadata)
    assert encoded == (
        '{"epic_parent":"SYN-EPIC-1","evidence_locators":'
        '["https://github.test/org/repo/pull/1","thread:msg-9"],'
        '"jira_key":"SYN-42","merged_source_ids":["github:pull/1","thread:msg-9"],'
        '"narrative_status":"merged","pr_status":"merged","provenance":["github","thread"]}'
    )
    assert deserialize_metadata(encoded) == metadata


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
    assert set(record.metadata.evidence_locators) == {
        "https://github.test/org/repo/pull/1",
        "thread:msg-9",
    }


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
    assert result.persistence_error is None
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
    assert result.persistence_error is None
    assert store.count_records() == 1
    row = store.get_record(result.records[0].id)
    assert row is not None
    assert len(row["evidence"]) == 2


def test_harvest_enriches_and_persists_complete_gmail_kudos() -> None:
    store = memory_store()
    result = HarvestService(store).run(
        HarvestRequest(
            observations=(
                {
                    "source_id": "gmail:msg-kudos-complete",
                    "source_connector": "google",
                    "source_locator": "gmail:msg-kudos-complete",
                    "title": "Synthetic recognition",
                    "record_type": "kudos",
                    "name": "Synthetic Sender",
                    "month": "2026-03",
                    "tags": ("kudos",),
                    "period": "2026-03",
                    "provenance": ("google",),
                    "excerpt": "Synthetic kudos evidence",
                    "observed_at": "2026-03-17T12:30:00Z",
                },
            )
        )
    )

    assert result.persisted is True
    assert result.issues == ()
    assert result.records[0].record_type == "kudos"
    assert result.records[0].name == "Synthetic Sender"
    assert result.records[0].month == "2026-03"
    row = store.get_record("rec:gmail:msg-kudos-complete")
    assert row is not None
    assert row["record_type"] == "kudos"
    assert row["name"] == "Synthetic Sender"
    assert row["month"] == "2026-03"


@pytest.mark.parametrize(
    ("name", "month", "expected_rule"),
    [
        (None, "2026-03", "kudos.name.required"),
        ("Synthetic Sender", None, "kudos.month.required"),
    ],
)
def test_harvest_does_not_persist_unresolved_gmail_kudos(
    name: str | None,
    month: str | None,
    expected_rule: str,
) -> None:
    store = memory_store()
    result = HarvestService(store).run(
        HarvestRequest(
            observations=(
                {
                    "source_id": f"gmail:msg-{expected_rule}",
                    "source_connector": "google",
                    "source_locator": f"gmail:msg-{expected_rule}",
                    "title": "Synthetic recognition",
                    "record_type": "kudos",
                    "name": name,
                    "month": month,
                    "tags": ("kudos",),
                    "period": month,
                    "provenance": ("google",),
                    "excerpt": "Synthetic unresolved kudos evidence",
                    "observed_at": "2026-03-17T12:30:00Z",
                },
            )
        )
    )

    assert result.persisted is False
    assert expected_rule in {issue.rule_id for issue in result.issues}
    assert store.count_records() == 0


def test_harvest_can_build_records_without_persisting() -> None:
    store = memory_store()
    request = HarvestRequest(
        observations=overlap_request().observations,
        persist=False,
    )

    result = HarvestService(store).run(request)

    assert len(result.records) == 1
    assert result.persisted is False
    assert result.persistence_error is None
    assert store.count_records() == 0


def test_harvest_reports_structured_persistence_error() -> None:
    class FailingStore:
        def count_records(self) -> int:
            return 0

        def get_record(self, record_id: str) -> dict[str, object] | None:
            return None

        def persist_records(self, records: tuple[DeliveryRecord, ...]) -> None:
            raise RuntimeError("persist failed")

    store = FailingStore()
    result = HarvestService(store).run(overlap_request())
    assert result.persisted is False
    assert result.persistence_error == {
        "code": "harvest.persistence.failed",
        "message": "RuntimeError",
    }
    assert store.count_records() == 0


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
    loaded = store.load_record("rec:test-001")
    assert loaded is not None
    assert loaded.metadata == valid_delivery_record().metadata
    assert loaded.evidence[0].connector == "thread"


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
    loaded = record_store.load_record("rec:encrypted-001")
    assert loaded is not None
    assert loaded.metadata.jira_key == "SYN-STORE-1"
    assert loaded.evidence[0].connector == "thread"


def test_harvest_encrypted_store_round_trip_preserves_provenance(store) -> None:
    record_store = EncryptedRecordStore.from_encrypted_store(store)
    result = HarvestService(record_store).run(overlap_request())
    assert result.persisted is True
    assert result.persistence_error is None
    assert record_store.count_records() == 1

    loaded = record_store.load_record(result.records[0].id)
    assert loaded is not None
    assert set(loaded.metadata.provenance) == {"github", "thread"}
    assert set(loaded.metadata.merged_source_ids) == {
        "github:pull/1",
        "thread:msg-9",
    }
    assert loaded.metadata.jira_key == "SYN-42"
    assert loaded.metadata.pr_status == "merged"
    assert loaded.metadata.narrative_status == "merged"
    assert {ref.connector for ref in loaded.evidence} == {"github", "thread"}
    assert set(loaded.metadata.evidence_locators) == {
        "https://github.test/org/repo/pull/1",
        "thread:msg-9",
    }


def test_encrypted_store_round_trip_preserves_kudos_fields(record_connection) -> None:
    record_store = EncryptedRecordStore(record_connection)
    result = HarvestService(record_store).run(
        HarvestRequest(
            observations=(
                {
                    "source_id": "gmail:msg-kudos-encrypted",
                    "source_connector": "google",
                    "source_locator": "gmail:msg-kudos-encrypted",
                    "title": "Synthetic recognition",
                    "record_type": "kudos",
                    "name": "Synthetic Sender",
                    "month": "2026-03",
                    "tags": ("kudos",),
                    "period": "2026-03",
                    "provenance": ("google",),
                    "excerpt": "Synthetic kudos evidence",
                    "observed_at": "2026-03-17T12:30:00Z",
                },
            )
        )
    )

    assert result.persisted is True
    loaded = record_store.load_record("rec:gmail:msg-kudos-encrypted")
    assert loaded is not None
    assert loaded.record_type == "kudos"
    assert loaded.name == "Synthetic Sender"
    assert loaded.month == "2026-03"
