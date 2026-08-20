from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from careeros.crypto import get_or_create_db_key, open_sqlcipher_connection, verify_cipher_support

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
CURRENT_MIGRATION_VERSION = 1


class StoreUnavailable(Exception):
    """Raised when the encrypted store cannot be opened safely."""


@dataclass(frozen=True)
class StoreConfig:
    path: Path


class EncryptedStore:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def connection(self) -> Any:
        return self._connection

    def close(self) -> None:
        self._connection.close()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migration_is_applied(connection: Any, version: int) -> bool:
    table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
    ).fetchone()
    if table is None:
        return False

    row = connection.execute(
        "SELECT 1 FROM migrations WHERE version = ?",
        (version,),
    ).fetchone()
    return row is not None


def _apply_migration(connection: Any, version: int) -> None:
    candidates = sorted(MIGRATIONS_DIR.glob(f"{version:03d}_*.sql"))
    if not candidates:
        raise StoreUnavailable(f"Missing migration file for version {version}")

    connection.executescript(candidates[0].read_text())
    connection.execute(
        "INSERT INTO migrations (version, applied_at) VALUES (?, ?)",
        (version, _utc_now_iso()),
    )
    connection.commit()


def _ensure_migrations(connection: Any) -> None:
    for version in range(1, CURRENT_MIGRATION_VERSION + 1):
        if not _migration_is_applied(connection, version):
            _apply_migration(connection, version)


def open_encrypted_store(
    config: StoreConfig,
    keyring_backend: Any,
    *,
    connect: Callable[[str], Any] | None = None,
) -> EncryptedStore:
    config.path.parent.mkdir(parents=True, exist_ok=True)
    key = get_or_create_db_key(keyring_backend, config.path)

    try:
        connection = open_sqlcipher_connection(
            str(config.path),
            key,
            connect=connect,
        )
        cipher_version = verify_cipher_support(connection)
    except ImportError:
        raise StoreUnavailable("SQLCipher driver is unavailable") from None
    except ValueError as exc:
        raise StoreUnavailable(f"SQLCipher is required: {exc}") from exc

    if not cipher_version:
        raise StoreUnavailable("SQLCipher is required; cipher_version is empty")

    _ensure_migrations(connection)
    return EncryptedStore(connection)
