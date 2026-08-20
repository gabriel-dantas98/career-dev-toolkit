from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from careeros.models import DeliveryRecord
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
        row = self._connection.execute(
            """
            SELECT id, title
            FROM records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None

        evidence_rows = self._connection.execute(
            """
            SELECT locator, excerpt, observed_at
            FROM evidence
            WHERE record_id = ?
            ORDER BY id
            """,
            (record_id,),
        ).fetchall()
        return {
            "id": row[0],
            "title": row[1],
            "evidence": [
                {"locator": item[0], "excerpt": item[1], "observed_at": item[2]}
                for item in evidence_rows
            ],
        }

    def persist_records(self, records: tuple[DeliveryRecord, ...]) -> None:
        connection = self._connection
        connection.execute("BEGIN")
        try:
            now = datetime.now(timezone.utc).isoformat()
            for record in records:
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
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.schema_version,
                        record.source_connector,
                        record.source_locator,
                        record.title,
                        record.period,
                        json.dumps(list(record.tags)),
                        record.context,
                        record.confidence,
                        record.situation,
                        record.task,
                        record.action,
                        record.result,
                        record.content_fingerprint,
                        record.observed_at,
                        now,
                    ),
                )
                for evidence in record.evidence:
                    connection.execute(
                        """
                        INSERT INTO evidence (record_id, locator, excerpt, observed_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            record.id,
                            evidence.locator,
                            evidence.excerpt,
                            evidence.observed_at,
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
