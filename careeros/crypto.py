import re
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any

from careeros.sqlcipher_driver import connect as sqlcipher_connect

KEYRING_SERVICE = "careeros"
KEY_ACCOUNT_PREFIX = "db-key:"
DB_KEY_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvalidDatabaseKey(ValueError):
    """Raised when a database key fails format validation."""


def key_account_for(path: Path) -> str:
    return f"{KEY_ACCOUNT_PREFIX}{path.resolve()}"


def validate_db_key(key: str) -> str:
    if not DB_KEY_HEX_PATTERN.match(key):
        raise InvalidDatabaseKey("Database key format is invalid")
    return key


def get_or_create_db_key(keyring_backend: Any, path: Path) -> str:
    account = key_account_for(path)
    try:
        existing = keyring_backend.get_password(KEYRING_SERVICE, account)
    except Exception:
        raise KeyringUnavailable("Keychain backend unavailable") from None

    if existing:
        return validate_db_key(existing)

    key = secrets.token_hex(32)
    try:
        keyring_backend.set_password(KEYRING_SERVICE, account, key)
    except Exception:
        raise KeyringUnavailable("Keychain backend unavailable") from None
    return key


class KeyringUnavailable(Exception):
    """Raised when the keychain backend cannot be accessed."""


def open_sqlcipher_connection(
    database: str,
    key: str,
    *,
    connect: Callable[[str], Any] | None = None,
) -> Any:
    validated_key = validate_db_key(key)
    connector = connect if connect is not None else sqlcipher_connect
    connection = connector(database)
    connection.execute(f"PRAGMA key = '{validated_key}'")
    return connection


def verify_cipher_support(connection: Any) -> str:
    row = connection.execute("PRAGMA cipher_version").fetchone()
    if row is None or not row[0]:
        raise CipherUnavailable("SQLCipher cipher_version is empty")
    return str(row[0])


class CipherUnavailable(ValueError):
    """Raised when SQLCipher cipher support cannot be verified."""
