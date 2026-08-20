import sqlite3

import pytest

from careeros.store import StoreConfig, open_encrypted_store


class CipherCapabilityStubConnection(sqlite3.Connection):
    """Unit-only SQLite connection reporting synthetic cipher capability."""

    def execute(
        self,
        sql: str,
        parameters: object = (),
    ) -> sqlite3.Cursor:
        if sql.strip().lower() == "pragma cipher_version":
            return super().execute("SELECT 'synthetic-sqlcipher'")
        return super().execute(sql, parameters)  # type: ignore[arg-type]


@pytest.fixture
def fake_keyring():
    passwords: dict[tuple[str, str], str] = {}

    class FakeKeyring:
        def get_password(self, service: str, account: str) -> str | None:
            return passwords.get((service, account))

        def set_password(self, service: str, account: str, password: str) -> None:
            passwords[(service, account)] = password

        def delete_password(self, service: str, account: str) -> None:
            passwords.pop((service, account), None)

    return FakeKeyring()


@pytest.fixture
def cipher_capability_stub_connect():
    def connect(database: str) -> sqlite3.Connection:
        return sqlite3.connect(database, factory=CipherCapabilityStubConnection)

    return connect


@pytest.fixture
def store(fake_keyring, cipher_capability_stub_connect, tmp_path):
    encrypted = open_encrypted_store(
        StoreConfig(tmp_path / "career.db"),
        fake_keyring,
        connect=cipher_capability_stub_connect,
    )
    yield encrypted
    encrypted.close()
