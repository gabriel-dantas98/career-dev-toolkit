"""SQLCipher DB-API driver boundary for production encrypted storage."""

import importlib
from types import ModuleType
from typing import Any

_MODULE: ModuleType | None = None
_IMPORT_ERROR: ImportError | None = None


def _load_module() -> ModuleType:
    global _MODULE, _IMPORT_ERROR
    if _MODULE is not None:
        return _MODULE
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR
    try:
        _MODULE = importlib.import_module("sqlcipher3.dbapi2")
    except ImportError as exc:
        _IMPORT_ERROR = exc
        raise
    return _MODULE


def connect(database: str) -> Any:
    return _load_module().connect(database)
