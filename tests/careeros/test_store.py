import sqlite3

import pytest

from careeros.store import StoreConfig, StoreUnavailable, open_encrypted_store


def test_store_refuses_driver_without_cipher(fake_keyring, tmp_path) -> None:
    with pytest.raises(StoreUnavailable, match="SQLCipher"):
        open_encrypted_store(
            StoreConfig(tmp_path / "career.db"),
            fake_keyring,
            connect=sqlite3.connect,
        )


def test_store_opens_with_sqlcipher_and_applies_migrations(fake_keyring, tmp_path) -> None:
    config = StoreConfig(tmp_path / "career.db")
    store = open_encrypted_store(config, fake_keyring)

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

        applied = store.connection().execute("SELECT version FROM migrations").fetchall()
        assert applied == [(1,)]
    finally:
        store.close()


def test_store_reuses_key_from_keyring(fake_keyring, tmp_path) -> None:
    config = StoreConfig(tmp_path / "career.db")
    first = open_encrypted_store(config, fake_keyring)
    first.close()

    second = open_encrypted_store(config, fake_keyring)
    second.close()

    assert fake_keyring.get_password("careeros", f"db-key:{config.path.resolve()}") is not None
