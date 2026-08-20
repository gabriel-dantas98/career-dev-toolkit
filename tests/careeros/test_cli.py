import json
import subprocess
import sys
from collections.abc import Callable

import pytest


@pytest.fixture
def run_cli() -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "careeros", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    return _run_cli


def test_version_is_machine_readable(run_cli: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    result = run_cli("version", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "ok": True,
        "command": "version",
        "data": {"schemaVersion": 1, "version": "0.2.0"},
        "errors": [],
    }
