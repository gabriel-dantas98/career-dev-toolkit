from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from careeros.models import DeliveryRecord, EvidenceRef
from careeros.record_metadata import deserialize_metadata, metadata_from_record, serialize_metadata
from careeros.store import EncryptedStore


class EncryptedRecordStore:
    """Production harvest persistence over the SQLCipher-backed store."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    @classmethod
    def from_encrypted_store(cls, store: EncryptedStore) -> EncryptedRecordStore:
        return cls(store.connection())

    def count_records(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM records").fetchone()
        return int(row[0]) if row is not None else 0

    def get_record(self, record_id: str) -> dict[str, object] | None:
        loaded = self.load_record(record_id)
        if loaded is None:
            return None
        return {
            "id": loaded.id,
            "title": loaded.title,
            "record_type": loaded.record_type,
            "name": loaded.name,
            "month": loaded.month,
            "metadata": loaded.metadata,
            "evidence": [
                {
                    "locator": evidence.locator,
                    "excerpt": evidence.excerpt,
                    "observed_at": evidence.observed_at,
                    "connector": evidence.connector,
                }
                for evidence in loaded.evidence
            ],
        }

    def load_record(self, record_id: str) -> DeliveryRecord | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                schema_version,
                source_connector,
                source_locator,
                title,
                period,
                tags,
                context,
                confidence,
                situation,
                task,
                action,
                result,
                content_fingerprint,
                observed_at,
                metadata_json,
                evidence_gaps,
                record_type,
                name,
                month
            FROM records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None

        evidence_rows = self._connection.execute(
            """
            SELECT locator, excerpt, observed_at, connector
            FROM evidence
            WHERE record_id = ?
            ORDER BY id
            """,
            (record_id,),
        ).fetchall()

        tags = json.loads(row[6]) if row[6] else []
        return DeliveryRecord(
            id=row[0],
            schema_version=row[1],
            source_connector=row[2],
            source_locator=row[3],
            title=row[4],
            period=row[5],
            tags=tuple(str(tag) for tag in tags),
            context=row[7],
            confidence=row[8],
            situation=row[9],
            task=row[10],
            action=row[11],
            result=row[12],
            content_fingerprint=row[13],
            observed_at=row[14],
            evidence=tuple(
                EvidenceRef(
                    locator=item[0],
                    excerpt=item[1],
                    observed_at=item[2],
                    connector=str(item[3] or ""),
                )
                for item in evidence_rows
            ),
            evidence_gaps=tuple(str(gap) for gap in json.loads(row[16] or "[]")),
            metadata=deserialize_metadata(row[15]),
            record_type=str(row[17] or "delivery"),
            name=str(row[18]) if row[18] is not None else None,
            month=str(row[19]) if row[19] is not None else None,
        )

    def load_records(self) -> tuple[DeliveryRecord, ...]:
        rows = self._connection.execute(
            "SELECT id FROM records ORDER BY id"
        ).fetchall()
        records: list[DeliveryRecord] = []
        for row in rows:
            record = self.load_record(str(row[0]))
            if record is not None:
                records.append(record)
        return tuple(records)

    def persist_records(self, records: tuple[DeliveryRecord, ...]) -> None:
        connection = self._connection
        connection.execute("BEGIN")
        try:
            now = datetime.now(timezone.utc).isoformat()
            for record in records:
                metadata = metadata_from_record(record)
                connection.execute(
                    """
                    INSERT INTO records (
                        id,
                        schema_version,
                        source_connector,
                        source_locator,
                        title,
                        period,
                        tags,
                        context,
                        confidence,
                        situation,
                        task,
                        action,
                        result,
                        content_fingerprint,
                        observed_at,
                        created_at,
                        metadata_json,
                        evidence_gaps,
                        record_type,
                        name,
                        month
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.schema_version,
                        record.source_connector,
                        record.source_locator,
                        record.title,
                        record.period,
                        json.dumps(list(record.tags), separators=(",", ":")),
                        record.context,
                        record.confidence,
                        record.situation,
                        record.task,
                        record.action,
                        record.result,
                        record.content_fingerprint,
                        record.observed_at,
                        now,
                        serialize_metadata(metadata),
                        json.dumps(list(record.evidence_gaps), separators=(",", ":")),
                        record.record_type,
                        record.name,
                        record.month,
                    ),
                )
                for evidence in record.evidence:
                    connection.execute(
                        """
                        INSERT INTO evidence (
                            record_id,
                            locator,
                            excerpt,
                            observed_at,
                            connector
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            record.id,
                            evidence.locator,
                            evidence.excerpt,
                            evidence.observed_at,
                            evidence.connector,
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
