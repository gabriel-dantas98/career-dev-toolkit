from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from careeros.google_client import HttpResponse

MAX_BODY_BYTES = 256 * 1024
VERSION = "1.0.0"


class UrlLibTransport:
    def post(
        self,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        request = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return HttpResponse(
                status=response.status,
                text=response.read().decode("utf-8"),
            )


class FakeGateway:
    """Loopback fixture implementing the fixed Apps Script gateway envelope."""

    def __init__(self) -> None:
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._actions: list[str] = []
        self._nonces: set[str] = set()
        self._sheet_values: list[list[object]] = []
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        if self._server is None:
            raise RuntimeError("Synthetic gateway is not running")
        host, port = self._server.server_address
        return f"http://{host}:{port}/exec"

    @property
    def actions(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._actions)

    def __enter__(self) -> FakeGateway:
        handler = _handler_type(self)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="careeros-eval-gateway",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        self._server = None

    def handle(self, raw_body: bytes) -> dict[str, object]:
        if len(raw_body) > MAX_BODY_BYTES:
            return _error("", "REQUEST_TOO_LARGE")
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error("", "INVALID_JSON")
        if not isinstance(payload, dict):
            return _error("", "INVALID_REQUEST")

        request_id = payload.get("requestId")
        action = payload.get("action")
        timestamp = payload.get("timestamp")
        nonce = payload.get("nonce")
        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(action, str)
            or not action
            or isinstance(timestamp, bool)
            or not isinstance(timestamp, int)
            or not isinstance(nonce, str)
            or len(nonce) < 12
        ):
            return _error(
                request_id if isinstance(request_id, str) else "",
                "INVALID_REQUEST",
            )

        with self._lock:
            if nonce in self._nonces:
                return _error(request_id, "NONCE_REPLAYED")
            self._nonces.add(nonce)
            self._actions.append(action)

            if action == "calendar.search":
                return _success(
                    request_id,
                    {
                        "events": [
                            {
                                "id": "synthetic-overlap-901",
                                "summary": "[Impact] Synthetic bounded sync",
                                "start": "2026-04-03T09:00:00+00:00",
                            }
                        ]
                    },
                )
            if action == "sheets.writeBragsheet":
                return self._write(request_id, payload)
            if action == "sheets.readBack":
                return self._read_back(request_id, payload)
            return _error(request_id, "ACTION_NOT_ALLOWED")

    def _write(
        self,
        request_id: str,
        payload: Mapping[str, Any],
    ) -> dict[str, object]:
        values = payload.get("values")
        if payload.get("inputMode") != "RAW":
            return _error(request_id, "RAW_REQUIRED")
        if (
            not isinstance(values, list)
            or not values
            or len(values) > 200
            or not all(isinstance(row, list) for row in values)
        ):
            return _error(request_id, "INVALID_VALUES")
        column_count = len(values[0])
        if (
            column_count < 1
            or column_count > 12
            or any(len(row) != column_count for row in values)
        ):
            return _error(request_id, "INVALID_VALUES")
        self._sheet_values = [list(row) for row in values]
        return _success(request_id, {"updatedRows": len(self._sheet_values)})

    def _read_back(
        self,
        request_id: str,
        payload: Mapping[str, Any],
    ) -> dict[str, object]:
        row_count = payload.get("rowCount")
        column_count = payload.get("columnCount")
        if (
            isinstance(row_count, bool)
            or not isinstance(row_count, int)
            or isinstance(column_count, bool)
            or not isinstance(column_count, int)
            or row_count != len(self._sheet_values)
            or any(len(row) != column_count for row in self._sheet_values)
        ):
            return _error(request_id, "READBACK_OUT_OF_BOUNDS")
        return _success(
            request_id,
            {"values": [list(row) for row in self._sheet_values]},
        )


def _handler_type(gateway: FakeGateway) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != "/exec":
                self.send_error(404)
                return
            raw_length = self.headers.get("Content-Length", "0")
            try:
                content_length = int(raw_length)
            except ValueError:
                content_length = 0
            body = self.rfile.read(max(0, content_length))
            response = gateway.handle(body)
            encoded = json.dumps(
                response,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return Handler


def _success(request_id: str, data: Mapping[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "requestId": request_id,
        "data": dict(data),
        "errors": [],
        "version": VERSION,
    }


def _error(request_id: str, code: str) -> dict[str, object]:
    return {
        "ok": False,
        "requestId": request_id,
        "data": None,
        "errors": [{"code": code, "message": "Synthetic request was rejected."}],
        "version": VERSION,
    }
