import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

KEYRING_SERVICE = "careeros"
KEY_ACCOUNT_PREFIX = "db-key:"


def key_account_for(path: Path) -> str:
    return f"{KEY_ACCOUNT_PREFIX}{path.resolve()}"


def get_or_create_db_key(keyring_backend: Any, path: Path) -> str:
    account = key_account_for(path)
    existing = keyring_backend.get_password(KEYRING_SERVICE, account)
    if existing:
        return existing

    key = secrets.token_hex(32)
    keyring_backend.set_password(KEYRING_SERVICE, account, key)
    return key


def default_sqlcipher_connect(database: str) -> Any:
    from sqlcipher3 import dbapi2 as sqlcipher

    return sqlcipher.connect(database)


def open_sqlcipher_connection(
    database: str,
    key: str,
    *,
    connect: Callable[[str], Any] | None = None,
) -> Any:
    connector = connect if connect is not None else default_sqlcipher_connect
    connection = connector(database)
    connection.execute(f"PRAGMA key = '{key}'")
    return connection


def verify_cipher_support(connection: Any) -> str:
    row = connection.execute("PRAGMA cipher_version").fetchone()
    if row is None or not row[0]:
        raise ValueError("SQLCipher cipher_version is empty")
    return str(row[0])
