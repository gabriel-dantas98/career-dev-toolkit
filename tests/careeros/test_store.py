import os
import sqlite3
import stat

import pytest

from careeros.crypto import KEYRING_SERVICE, key_account_for
from careeros.store import (
    CURRENT_MIGRATION_VERSION,
    StoreConfig,
    StoreUnavailable,
    open_encrypted_store,
)


def test_store_refuses_driver_without_cipher(fake_keyring, tmp_path) -> None:
    with pytest.raises(StoreUnavailable, match="SQLCipher"):
        open_encrypted_store(
            StoreConfig(tmp_path / "career.db"),
            fake_keyring,
            connect=sqlite3.connect,
        )


def test_production_sqlcipher_driver_encrypts_migrates_and_reopens(
    fake_keyring,
    tmp_path,
) -> None:
    config = StoreConfig(tmp_path / "production-cipher.db")
    synthetic_key = "ab" * 32
    fake_keyring.set_password(
        KEYRING_SERVICE,
        key_account_for(config.path),
        synthetic_key,
    )

    store = open_encrypted_store(config, fake_keyring)
    try:
        cipher_version = store.connection().execute(
            "PRAGMA cipher_version"
        ).fetchone()
        migrations = store.connection().execute(
            "SELECT version FROM migrations ORDER BY version"
        ).fetchall()
        store.connection().execute(
            "INSERT INTO records "
            "(id, schema_version, source_connector, source_locator, title, "
            "tags, content_fingerprint, observed_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "delivery:sqlcipher-canary",
                1,
                "synthetic",
                "synthetic:sqlcipher-canary",
                "Synthetic SQLCipher canary",
                "[]",
                "sqlcipher-canary-fingerprint",
                "2026-08-20T00:00:00+00:00",
                "2026-08-20T00:00:00+00:00",
            ),
        )
        store.connection().commit()
    finally:
        store.close()

    assert cipher_version is not None
    assert cipher_version[0]
    assert migrations == [
        (version,) for version in range(1, CURRENT_MIGRATION_VERSION + 1)
    ]

    reopened = open_encrypted_store(config, fake_keyring)
    try:
        row = reopened.connection().execute(
            "SELECT title FROM records WHERE id = ?",
            ("delivery:sqlcipher-canary",),
        ).fetchone()
    finally:
        reopened.close()
    assert row == ("Synthetic SQLCipher canary",)

    plaintext = sqlite3.connect(config.path)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            plaintext.execute("SELECT name FROM sqlite_master").fetchall()
    finally:
        plaintext.close()


def test_store_unit_cipher_capability_stub_applies_migrations(
    fake_keyring,
    cipher_capability_stub_connect,
    tmp_path,
) -> None:
    config = StoreConfig(tmp_path / "career.db")
    store = open_encrypted_store(
        config,
        fake_keyring,
        connect=cipher_capability_stub_connect,
    )

    try:
        tables = {
            row[0]
            for row in store.connection().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "migrations",
            "records",
            "evidence",
            "grants",
            "sync_runs",
        } <= tables

        applied = store.connection().execute(
            "SELECT version FROM migrations ORDER BY version"
        ).fetchall()
        assert applied == [
            (version,) for version in range(1, CURRENT_MIGRATION_VERSION + 1)
        ]
    finally:
        store.close()


def test_store_reuses_key_from_keyring(
    fake_keyring,
    cipher_capability_stub_connect,
    tmp_path,
) -> None:
    config = StoreConfig(tmp_path / "career.db")
    first = open_encrypted_store(
        config,
        fake_keyring,
        connect=cipher_capability_stub_connect,
    )
    first.close()

    second = open_encrypted_store(
        config,
        fake_keyring,
        connect=cipher_capability_stub_connect,
    )
    second.close()

    assert fake_keyring.get_password("careeros", f"db-key:{config.path.resolve()}") is not None


def test_store_refuses_keychain_backend_failure(tmp_path) -> None:
    class FailingKeyring:
        def get_password(self, service: str, account: str) -> str | None:
            raise OSError("keychain locked")

        def set_password(self, service: str, account: str, password: str) -> None:
            raise OSError("keychain locked")

        def delete_password(self, service: str, account: str) -> None:
            raise OSError("keychain locked")

    with pytest.raises(StoreUnavailable, match="Keychain backend unavailable"):
        open_encrypted_store(StoreConfig(tmp_path / "career.db"), FailingKeyring())


def test_store_refuses_migration_version_ahead_of_runtime(
    fake_keyring,
    cipher_capability_stub_connect,
    tmp_path,
) -> None:
    config = StoreConfig(tmp_path / "career.db")
    store = open_encrypted_store(
        config,
        fake_keyring,
        connect=cipher_capability_stub_connect,
    )
    store.connection().execute(
        "INSERT INTO migrations (version, applied_at) VALUES (?, ?)",
        (CURRENT_MIGRATION_VERSION + 1, "2026-01-01T00:00:00+00:00"),
    )
    store.connection().commit()
    store.close()

    with pytest.raises(StoreUnavailable, match="newer than runtime"):
        open_encrypted_store(
            config,
            fake_keyring,
            connect=cipher_capability_stub_connect,
        )


def test_store_refuses_broad_existing_db_permissions(fake_keyring, tmp_path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX permission checks only")

    db_path = tmp_path / "career.db"
    db_path.write_bytes(b"")
    os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

    with pytest.raises(StoreUnavailable, match="permissions are too broad"):
        open_encrypted_store(StoreConfig(db_path), fake_keyring)

    assert db_path.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH)


def test_store_creates_new_db_with_user_only_permissions(
    fake_keyring,
    cipher_capability_stub_connect,
    tmp_path,
) -> None:
    if os.name != "posix":
        pytest.skip("POSIX permission checks only")

    config = StoreConfig(tmp_path / "career.db")
    store = open_encrypted_store(
        config,
        fake_keyring,
        connect=cipher_capability_stub_connect,
    )
    store.close()

    mode = config.path.stat().st_mode
    assert mode & stat.S_IRUSR
    assert mode & stat.S_IWUSR
    assert not mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)


def test_store_refuses_invalid_keychain_key_without_leaking(fake_keyring, tmp_path) -> None:
    config = StoreConfig(tmp_path / "career.db")
    fake_keyring.set_password(
        "careeros",
        f"db-key:{config.path.resolve()}",
        "not-a-valid-database-key",
    )

    with pytest.raises(StoreUnavailable, match="invalid") as exc_info:
        open_encrypted_store(config, fake_keyring)

    assert "not-a-valid-database-key" not in str(exc_info.value)


def test_store_closes_connection_on_startup_failure(fake_keyring, tmp_path) -> None:
    connection_holder: dict[str, sqlite3.Connection] = {}

    def tracking_connect(path: str) -> sqlite3.Connection:
        connection = sqlite3.connect(path)
        connection_holder["connection"] = connection
        return connection

    with pytest.raises(StoreUnavailable, match="SQLCipher"):
        open_encrypted_store(
            StoreConfig(tmp_path / "career.db"),
            fake_keyring,
            connect=tracking_connect,
        )

    with pytest.raises(sqlite3.ProgrammingError):
        connection_holder["connection"].execute("SELECT 1")
