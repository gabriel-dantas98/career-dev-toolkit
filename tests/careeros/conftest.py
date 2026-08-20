import sqlite3

import pytest

from careeros.store import StoreConfig, open_encrypted_store


class FakeSqlCipherConnection(sqlite3.Connection):
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
def fake_sqlcipher_connect():
    def connect(database: str) -> sqlite3.Connection:
        return sqlite3.connect(database, factory=FakeSqlCipherConnection)

    return connect


@pytest.fixture
def store(fake_keyring, fake_sqlcipher_connect, tmp_path):
    encrypted = open_encrypted_store(
        StoreConfig(tmp_path / "career.db"),
        fake_keyring,
        connect=fake_sqlcipher_connect,
    )
    yield encrypted
    encrypted.close()
