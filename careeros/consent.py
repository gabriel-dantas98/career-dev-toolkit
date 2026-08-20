import json
from datetime import datetime, timezone
from typing import Any

from careeros.store import EncryptedStore


class ConsentDenied(Exception):
    """Raised when consent is missing, revoked, or out of scope."""


def normalize_resource_id(resource_id: str) -> str:
    return resource_id.strip()


class ConsentService:
    def __init__(self, store: EncryptedStore) -> None:
        self._store = store

    def grant(self, grant_type: str, resource_id: str, scopes: tuple[str, ...]) -> None:
        normalized_id = normalize_resource_id(resource_id)
        now = datetime.now(timezone.utc).isoformat()
        connection = self._store.connection()
        connection.execute(
            """
            INSERT INTO grants (grant_type, resource_id, scopes, granted_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(grant_type, resource_id) DO UPDATE SET
                scopes = excluded.scopes,
                granted_at = excluded.granted_at,
                revoked_at = NULL
            """,
            (grant_type, normalized_id, json.dumps(list(scopes)), now),
        )
        connection.commit()

    def require(self, grant_type: str, resource_id: str, scope: str) -> None:
        normalized_id = normalize_resource_id(resource_id)
        connection = self._store.connection()
        row = connection.execute(
            """
            SELECT scopes, revoked_at
            FROM grants
            WHERE grant_type = ? AND resource_id = ?
            """,
            (grant_type, normalized_id),
        ).fetchone()

        if row is None:
            raise ConsentDenied(
                f"Consent denied: no {grant_type} grant for {normalized_id}"
            )

        scopes_json, revoked_at = row
        if revoked_at is not None:
            raise ConsentDenied(
                f"Consent denied: {grant_type} grant for {normalized_id} is revoked"
            )

        scopes = json.loads(scopes_json)
        if scope not in scopes:
            raise ConsentDenied(
                f"Consent denied: scope {scope} not granted for {normalized_id}"
            )

    def revoke(self, grant_type: str, resource_id: str) -> None:
        normalized_id = normalize_resource_id(resource_id)
        now = datetime.now(timezone.utc).isoformat()
        connection = self._store.connection()
        connection.execute(
            """
            UPDATE grants
            SET revoked_at = ?
            WHERE grant_type = ? AND resource_id = ?
            """,
            (now, grant_type, normalized_id),
        )
        connection.commit()
