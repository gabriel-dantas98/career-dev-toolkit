import pytest

from careeros.store import StoreConfig, open_encrypted_store


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
def store(fake_keyring, tmp_path):
    encrypted = open_encrypted_store(StoreConfig(tmp_path / "career.db"), fake_keyring)
    yield encrypted
    encrypted.close()
