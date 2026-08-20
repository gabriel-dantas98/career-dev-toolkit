from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from careeros.outputs import BRAG_DOCUMENT_GID, build_homepage
from careeros.urls import google_exec_urls_in_text, validate_google_exec_url


class DeploymentBlocked(RuntimeError):
    """Raised when deployment health or output cannot prove a safe deployment."""


class ClaspAdapter(Protocol):
    def health(self) -> bool: ...

    def deploy(self) -> str: ...


class DeploymentRegistry(Protocol):
    def register(self, web_app_url: str) -> None: ...


class FileDeploymentRegistry:
    """Registers the verified deployment URL in a private local JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser()

    def register(self, web_app_url: str) -> None:
        validate_google_exec_url(web_app_url)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"webAppUrl": web_app_url},
            separators=(",", ":"),
        ).encode("utf-8")
        descriptor = os.open(
            self._path,
            os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
        if os.name == "posix":
            os.chmod(self._path, 0o600)


@dataclass(frozen=True)
class DeploymentResult:
    web_app_url: str
    homepage: dict[str, object]


class SubprocessClaspAdapter:
    """Bounded clasp adapter that uses argv execution and returns raw deploy output."""

    def __init__(
        self,
        *,
        command: Sequence[str] = ("npx", "--yes", "@google/clasp"),
        cwd: Path | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        if not command:
            raise ValueError("clasp command cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._command = tuple(command)
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds

    def health(self) -> bool:
        result = self._run(("login", "--status"))
        output = f"{result.stdout}\n{result.stderr}".lower()
        return result.returncode == 0 and "not logged in" not in output

    def deploy(self) -> str:
        result = self._run(("deploy",))
        if result.returncode != 0:
            raise DeploymentBlocked("clasp deployment command failed")
        return f"{result.stdout}\n{result.stderr}"

    def _run(self, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                (*self._command, *arguments),
                cwd=self._cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DeploymentBlocked("clasp command could not complete") from exc


class DeployService:
    def __init__(
        self,
        *,
        clasp: ClaspAdapter,
        registry: DeploymentRegistry,
        brag_document_gid: int = BRAG_DOCUMENT_GID,
    ) -> None:
        self._clasp = clasp
        self._registry = registry
        self._brag_document_gid = brag_document_gid

    def deploy(self) -> DeploymentResult:
        if self._clasp.health() is not True:
            raise DeploymentBlocked("clasp health must pass before deployment")

        web_app_url = parse_web_app_url(self._clasp.deploy())
        homepage = build_homepage(
            web_app_url,
            brag_document_gid=self._brag_document_gid,
        )
        self._registry.register(web_app_url)
        return DeploymentResult(
            web_app_url=web_app_url,
            homepage=homepage,
        )


def parse_web_app_url(output: str) -> str:
    matches = google_exec_urls_in_text(output)
    if len(matches) != 1:
        raise DeploymentBlocked(
            "clasp deploy output must contain exactly one real Google /exec URL"
        )
    return matches[0]
