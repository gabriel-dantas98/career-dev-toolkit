from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from careeros.consent import normalize_resource_id
from careeros.outputs import BRAG_DOCUMENT_GID, build_homepage
from careeros.urls import google_exec_urls_in_text, validate_google_exec_url

MAX_HOMEPAGE_ROWS = 3
MAX_HOMEPAGE_COLUMNS = 2
HOMEPAGE_SHEET_NAME = "Homepage"
HOMEPAGE_RANGE = "A1:B3"


class DeploymentBlocked(RuntimeError):
    """Raised when deployment health or output cannot prove a safe deployment."""


class ClaspAdapter(Protocol):
    def health(self) -> bool: ...

    def deploy(self) -> str: ...


class DeploymentRegistry(Protocol):
    def register(self, web_app_url: str) -> None: ...


class HomepageGateway(Protocol):
    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]: ...


class DestinationConsent(Protocol):
    def require(self, grant_type: str, resource_id: str, scope: str) -> None: ...


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
    homepage_written: bool = False


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
        gateway: HomepageGateway | None = None,
        consent: DestinationConsent | None = None,
        homepage_destination_id: str | None = None,
    ) -> None:
        homepage_options = (gateway, consent, homepage_destination_id)
        if any(option is not None for option in homepage_options) and not all(
            option is not None for option in homepage_options
        ):
            raise ValueError(
                "gateway, consent, and homepage_destination_id must be configured together"
            )
        canonical_destination: str | None = None
        if homepage_destination_id is not None:
            canonical_destination = normalize_resource_id(homepage_destination_id)
            if not canonical_destination.startswith("sheet:"):
                raise ValueError("homepage_destination_id must identify a Google Sheet")
            if brag_document_gid != BRAG_DOCUMENT_GID:
                raise ValueError(
                    "homepage writes require the fixed brag-document gid"
                )
        self._clasp = clasp
        self._registry = registry
        self._brag_document_gid = brag_document_gid
        self._gateway = gateway
        self._consent = consent
        self._homepage_destination_id = canonical_destination

    def deploy(self) -> DeploymentResult:
        if self._clasp.health() is not True:
            raise DeploymentBlocked("clasp health must pass before deployment")

        web_app_url = parse_web_app_url(self._clasp.deploy())
        homepage = build_homepage(
            web_app_url,
            brag_document_gid=self._brag_document_gid,
        )
        self._registry.register(web_app_url)
        homepage_written = False
        if (
            self._gateway is not None
            and self._consent is not None
            and self._homepage_destination_id is not None
        ):
            self._write_homepage(homepage)
            homepage_written = True
        return DeploymentResult(
            web_app_url=web_app_url,
            homepage=homepage,
            homepage_written=homepage_written,
        )

    def _write_homepage(self, homepage: Mapping[str, object]) -> None:
        destination_id = self._homepage_destination_id
        gateway = self._gateway
        consent = self._consent
        if destination_id is None or gateway is None or consent is None:
            raise DeploymentBlocked("homepage gateway configuration is incomplete")

        consent.require(
            "destination",
            destination_id,
            "write:homepage",
        )
        try:
            write_response = gateway.invoke(
                {
                    "action": "sheets.writeHomepage",
                    "spreadsheetId": destination_id.removeprefix("sheet:"),
                    "sheetName": HOMEPAGE_SHEET_NAME,
                    "range": HOMEPAGE_RANGE,
                    "inputMode": "RAW",
                    "homepage": dict(homepage),
                }
            )
        except Exception as exc:
            raise DeploymentBlocked("homepage write could not be verified") from exc
        _require_gateway_success(write_response, "write")

        consent.require(
            "destination",
            destination_id,
            "write:homepage",
        )
        try:
            read_response = gateway.invoke(
                {
                    "action": "sheets.readBack",
                    "spreadsheetId": destination_id.removeprefix("sheet:"),
                    "sheetName": HOMEPAGE_SHEET_NAME,
                    "startRow": 1,
                    "rowCount": MAX_HOMEPAGE_ROWS,
                    "columnCount": MAX_HOMEPAGE_COLUMNS,
                }
            )
        except Exception as exc:
            raise DeploymentBlocked("homepage read-back could not be verified") from exc
        _require_gateway_success(read_response, "read-back")
        actual = _homepage_readback_values(read_response)
        expected = _homepage_matrix(homepage)
        if not _matrices_match(expected, actual):
            raise DeploymentBlocked(
                "homepage read-back did not exactly match the intended model"
            )


def parse_web_app_url(output: str) -> str:
    matches = google_exec_urls_in_text(output)
    if len(matches) != 1:
        raise DeploymentBlocked(
            "clasp deploy output must contain exactly one real Google /exec URL"
        )
    return matches[0]


def _homepage_matrix(homepage: Mapping[str, object]) -> tuple[tuple[object, ...], ...]:
    source = homepage.get("source")
    if not isinstance(source, Mapping):
        raise DeploymentBlocked("homepage model is missing its source")
    return (
        ("webAppUrl", homepage.get("webAppUrl")),
        ("source.kind", source.get("kind")),
        ("source.gid", source.get("gid")),
    )


def _require_gateway_success(
    response: Mapping[str, object],
    operation: str,
) -> None:
    if response.get("ok") is not True:
        raise DeploymentBlocked(f"homepage gateway {operation} was not successful")


def _homepage_readback_values(
    response: Mapping[str, object],
) -> list[list[object]]:
    data = response.get("data")
    if not isinstance(data, Mapping):
        raise DeploymentBlocked("homepage read-back data is missing")
    values = data.get("values")
    if not isinstance(values, list) or not all(
        isinstance(row, list) for row in values
    ):
        raise DeploymentBlocked("homepage read-back values are malformed")
    return values


def _matrices_match(
    expected: tuple[tuple[object, ...], ...],
    actual: list[list[object]],
) -> bool:
    if len(expected) != len(actual):
        return False
    for expected_row, actual_row in zip(expected, actual, strict=True):
        if len(expected_row) != len(actual_row):
            return False
        for expected_value, actual_value in zip(
            expected_row,
            actual_row,
            strict=True,
        ):
            if type(expected_value) is not type(actual_value):
                return False
            if expected_value != actual_value:
                return False
    return True
