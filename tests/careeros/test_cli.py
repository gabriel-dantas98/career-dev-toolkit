import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def run_cli() -> Callable[..., subprocess.CompletedProcess[str]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "careeros", *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
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


def test_unknown_command_returns_structured_error(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    result = run_cli("unknown", "--json")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "ok": False,
        "command": "unknown",
        "data": {},
        "errors": [{"code": "unknown_command", "message": "Unknown command: unknown"}],
    }
