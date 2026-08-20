import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from careeros.crypto import (
    CipherUnavailable,
    InvalidDatabaseKey,
    KeyringUnavailable,
    get_or_create_db_key,
    open_sqlcipher_connection,
    verify_cipher_support,
)

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


def _check_existing_db_permissions(path: Path) -> None:
    if os.name != "posix" or not path.exists():
        return

    mode = path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
        raise StoreUnavailable("Database file permissions are too broad")


def _migration_table_exists(connection: Any) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
    ).fetchone()
    return row is not None


def _check_applied_migrations_not_ahead(connection: Any) -> None:
    if not _migration_table_exists(connection):
        return

    row = connection.execute("SELECT MAX(version) FROM migrations").fetchone()
    if row is not None and row[0] is not None and row[0] > CURRENT_MIGRATION_VERSION:
        raise StoreUnavailable("Applied migration version is newer than runtime")


def _migration_is_applied(connection: Any, version: int) -> bool:
    if not _migration_table_exists(connection):
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


def _map_startup_failure(exc: BaseException) -> StoreUnavailable:
    if isinstance(exc, StoreUnavailable):
        return exc
    if isinstance(exc, KeyringUnavailable):
        return StoreUnavailable(str(exc))
    if isinstance(exc, InvalidDatabaseKey):
        return StoreUnavailable("Database key from keychain is invalid")
    if isinstance(exc, CipherUnavailable):
        return StoreUnavailable("SQLCipher is required")
    if isinstance(exc, ImportError):
        return StoreUnavailable("SQLCipher driver is unavailable")
    if isinstance(exc, ValueError):
        return StoreUnavailable("SQLCipher is required")
    return StoreUnavailable("Encrypted store startup failed")


def open_encrypted_store(
    config: StoreConfig,
    keyring_backend: Any,
    *,
    connect: Callable[[str], Any] | None = None,
) -> EncryptedStore:
    config.path.parent.mkdir(parents=True, exist_ok=True)
    _check_existing_db_permissions(config.path)

    connection: Any | None = None
    try:
        key = get_or_create_db_key(keyring_backend, config.path)
        is_new_db = not config.path.exists()
        connection = open_sqlcipher_connection(
            str(config.path),
            key,
            connect=connect,
        )
        verify_cipher_support(connection)
        _check_applied_migrations_not_ahead(connection)
        _ensure_migrations(connection)

        if is_new_db and os.name == "posix":
            os.chmod(config.path, stat.S_IRUSR | stat.S_IWUSR)

        return EncryptedStore(connection)
    except BaseException as exc:
        if connection is not None:
            connection.close()
        mapped = _map_startup_failure(exc)
        if mapped is exc:
            raise
        raise mapped from None
