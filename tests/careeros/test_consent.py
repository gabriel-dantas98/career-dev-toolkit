import pytest

from careeros.consent import ConsentDenied, ConsentService


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
