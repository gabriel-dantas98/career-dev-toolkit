import pytest

from careeros.consent import (
    ConsentDenied,
    ConsentService,
    InvalidResourceId,
    normalize_resource_id,
)
from careeros.crypto import InvalidDatabaseKey, validate_db_key


def test_background_grant_does_not_follow_destination_grant(store) -> None:
    consent = ConsentService(store)
    consent.grant("destination", "sheet:synthetic-123", ("write:bragsheet",))
    with pytest.raises(ConsentDenied):
        consent.require("background", "job:daily-sync", "run")


def test_destination_grant_allows_matching_require(store) -> None:
    consent = ConsentService(store)
    consent.grant("destination", "sheet:synthetic-123", ("write:bragsheet",))
    consent.require("destination", "sheet:synthetic-123", "write:bragsheet")


def test_require_checks_scope(store) -> None:
    consent = ConsentService(store)
    consent.grant("destination", "sheet:synthetic-123", ("write:bragsheet",))
    with pytest.raises(ConsentDenied):
        consent.require("destination", "sheet:synthetic-123", "read:bragsheet")


def test_revoke_denies_subsequent_require(store) -> None:
    consent = ConsentService(store)
    consent.grant("background", "job:daily-sync", ("run",))
    consent.revoke("background", "job:daily-sync")
    with pytest.raises(ConsentDenied):
        consent.require("background", "job:daily-sync", "run")


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("sheet:synthetic-123", "sheet:synthetic-123"),
        ("SHEET:synthetic-123", "sheet:synthetic-123"),
        (
            "https://docs.google.com/spreadsheets/d/syntheticSheetId/edit#gid=0",
            "sheet:syntheticSheetId",
        ),
        (
            "https://docs.google.com/document/d/syntheticDocId/edit",
            "doc:syntheticDocId",
        ),
        ("job:daily-sync", "job:daily-sync"),
        ("connector:github", "connector:github"),
    ],
)
def test_normalize_resource_id_canonicalizes_namespaced_and_google_urls(
    raw: str,
    canonical: str,
) -> None:
    assert normalize_resource_id(raw) == canonical


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ambiguous-display-name",
        "https://example.com/not-google",
    ],
)
def test_normalize_resource_id_rejects_unsupported_ids(raw: str) -> None:
    with pytest.raises(InvalidResourceId):
        normalize_resource_id(raw)


def test_grant_with_sheet_url_matches_namespaced_require(store) -> None:
    consent = ConsentService(store)
    sheet_url = "https://docs.google.com/spreadsheets/d/syntheticSheetId/edit"
    consent.grant("destination", sheet_url, ("write:bragsheet",))
    consent.require("destination", "sheet:syntheticSheetId", "write:bragsheet")


def test_validate_db_key_accepts_64_char_lowercase_hex() -> None:
    assert validate_db_key("a" * 64) == "a" * 64


@pytest.mark.parametrize(
    "key",
    [
        "",
        "short",
        "A" * 64,
        "g" * 64,
        "a" * 63,
        "a" * 65,
        "'; DROP TABLE grants; --",
    ],
)
def test_validate_db_key_rejects_invalid_keys(key: str) -> None:
    with pytest.raises(InvalidDatabaseKey):
        validate_db_key(key)
