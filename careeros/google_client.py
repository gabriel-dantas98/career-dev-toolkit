from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

try:
    from playwright import sync_api as playwright_sync_api
except ImportError:
    playwright_sync_api = None

MAX_REQUEST_BYTES = 256 * 1024
MAX_ATTEMPTS = 5
DEFAULT_TIMEOUT_SECONDS = 120.0
MUTATING_ACTIONS = frozenset({"sheets.writeBragsheet"})
TRANSIENT_MARKERS = (
    "unable to open the file",
    "sorry, unable to open",
    "não foi possível abrir o arquivo",
    "nao foi possivel abrir o arquivo",
    "temporarily unavailable",
    "service invoked too many times",
    "try again later",
    "rate limit",
)


class GatewayProtocolError(RuntimeError):
    """Raised when browser transport does not return the CareerOS protocol."""


class BrowserTransportUnavailable(RuntimeError):
    """Raised when the optional browser runtime cannot be loaded."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    text: str


class BrowserTransport(Protocol):
    def post(
        self,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse: ...


class PlaywrightBrowserTransport:
    """POST through a persistent Chromium profile carrying Google auth cookies."""

    def __init__(
        self,
        profile_dir: Path,
        *,
        headless: bool = True,
    ) -> None:
        self._profile_dir = profile_dir.expanduser()
        self._headless = headless

    def post(
        self,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        if playwright_sync_api is None:
            raise BrowserTransportUnavailable(
                "Browser mode requires the optional Playwright runtime"
            )

        self._profile_dir.mkdir(parents=True, exist_ok=True)
        timeout_ms = int(timeout_seconds * 1_000)
        with playwright_sync_api.sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                headless=self._headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                response = context.request.post(
                    url,
                    data=body,
                    headers=headers,
                    timeout=timeout_ms,
                )
                return HttpResponse(status=int(response.status), text=response.text())
            finally:
                context.close()


class BrowserModeClient:
    def __init__(
        self,
        web_app_url: str,
        *,
        transport: BrowserTransport | None = None,
        browser_profile: Path | None = None,
        clock: Callable[[], float] = time.time,
        nonce_factory: Callable[[], str] | None = None,
        request_id_factory: Callable[[], str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        _validate_web_app_url(web_app_url)
        if max_attempts < 1 or max_attempts > MAX_ATTEMPTS:
            raise ValueError(f"max_attempts must be between 1 and {MAX_ATTEMPTS}")
        if timeout_seconds <= 0 or timeout_seconds > DEFAULT_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds must be between 0 and {DEFAULT_TIMEOUT_SECONDS:g}"
            )

        profile = browser_profile or Path.home() / ".config" / "careeros" / "browser-profile"
        self._web_app_url = web_app_url
        self._transport = transport or PlaywrightBrowserTransport(profile)
        self._clock = clock
        self._nonce_factory = nonce_factory or (lambda: uuid.uuid4().hex)
        self._request_id_factory = request_id_factory or (lambda: uuid.uuid4().hex)
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds

    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        action = payload.get("action")
        if not isinstance(action, str) or not action:
            raise GatewayProtocolError("Gateway payload requires an action")
        is_mutating = action in MUTATING_ACTIONS

        request_id = self._request_id_factory()
        request = dict(payload)
        request.update(
            {
                "requestId": request_id,
                "timestamp": int(self._clock()),
                "nonce": self._nonce_factory(),
            }
        )
        body = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        if len(body.encode("utf-8")) > MAX_REQUEST_BYTES:
            raise GatewayProtocolError("Gateway request exceeds the fixed body limit")

        response: HttpResponse | None = None
        for attempt in range(self._max_attempts):
            try:
                response = self._transport.post(
                    self._web_app_url,
                    body,
                    {"Content-Type": "application/json"},
                    self._timeout_seconds,
                )
            except (OSError, TimeoutError) as exc:
                if is_mutating:
                    raise GatewayProtocolError(
                        "Mutating gateway request has an ambiguous outcome"
                    ) from exc
                if attempt == self._max_attempts - 1:
                    raise GatewayProtocolError("Browser transport failed") from exc
                self._sleep(_retry_delay(attempt))
                continue

            if _is_transient(response):
                if is_mutating:
                    raise GatewayProtocolError(
                        "Mutating gateway request has an ambiguous outcome"
                    )
                if attempt == self._max_attempts - 1:
                    raise GatewayProtocolError(
                        "Browser transport remained transient after bounded retries"
                    )
                self._sleep(_retry_delay(attempt))
                continue
            break

        if response is None:
            raise GatewayProtocolError("Browser transport produced no response")
        if response.status < 200 or response.status >= 300:
            raise GatewayProtocolError("Gateway returned a non-success HTTP status")

        parsed = _parse_envelope(response.text)
        if parsed["requestId"] != request_id:
            raise GatewayProtocolError("Gateway response requestId does not match request")
        return parsed


def _validate_web_app_url(value: str) -> None:
    parsed = urlparse(value)
    is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    is_google = parsed.scheme == "https" and parsed.hostname == "script.google.com"
    if not (is_google or (is_loopback and parsed.scheme == "http")):
        raise ValueError("web_app_url must be Google HTTPS or a loopback HTTP fixture")
    if not parsed.path.endswith("/exec"):
        raise ValueError("web_app_url must end in /exec")


def _is_transient(response: HttpResponse) -> bool:
    if response.status in {429, 502, 503, 504}:
        return True
    stripped = response.text.strip().lower()
    if not stripped or stripped == "drive":
        return True
    return any(marker in stripped for marker in TRANSIENT_MARKERS)


def _retry_delay(attempt: int) -> float:
    return 0.25 * (2**attempt)


def _parse_envelope(text: str) -> dict[str, object]:
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GatewayProtocolError("Gateway response is not JSON") from exc
    if not isinstance(parsed, dict):
        raise GatewayProtocolError("Gateway response must be a JSON object")

    required = {"ok", "requestId", "data", "errors", "version"}
    if set(parsed) != required:
        raise GatewayProtocolError("Gateway response does not match the fixed envelope")
    if not isinstance(parsed["ok"], bool):
        raise GatewayProtocolError("Gateway response ok must be boolean")
    if not isinstance(parsed["requestId"], str):
        raise GatewayProtocolError("Gateway response requestId must be a string")
    if not isinstance(parsed["data"], (dict, type(None))):
        raise GatewayProtocolError("Gateway response data must be an object or null")
    if not isinstance(parsed["errors"], list):
        raise GatewayProtocolError("Gateway response errors must be a list")
    if not isinstance(parsed["version"], str) or not parsed["version"]:
        raise GatewayProtocolError("Gateway response version must be nonempty")
    return parsed
