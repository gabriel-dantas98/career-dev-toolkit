from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
from typing import Any

import pytest

from careeros.consent import ConsentDenied, ConsentService
from careeros.google_client import (
    BrowserModeClient,
    GatewayProtocolError,
    HttpResponse,
)
from careeros.models import DeliveryRecord, EvidenceRef
from careeros.projections import (
    BRAGSHEET_COLUMNS,
    project_bragsheet,
    serialize_period,
)
from careeros.record_store import EncryptedRecordStore
from careeros.sync import (
    EncryptedSyncRunStore,
    ReadbackMismatch,
    SyncService,
)


def synthetic_record(**overrides: object) -> DeliveryRecord:
    base: dict[str, object] = {
        "id": "delivery:synthetic-1",
        "schema_version": 1,
        "source_connector": "thread",
        "source_locator": "thread:synthetic",
        "title": "Feature: bounded sync",
        "period": "03/04/2026",
        "tags": ("feature",),
        "context": "delivery",
        "confidence": "partial",
        "situation": "A synthetic workflow needed a safe projection.",
        "task": "Define a bounded write contract.",
        "action": "Added deterministic checks.",
        "result": "The synthetic fixture verifies exact values.",
        "evidence": (
            EvidenceRef(
                locator="https://example.invalid/evidence/synthetic-1",
                excerpt="Synthetic evidence only.",
                observed_at="2026-08-20T00:00:00+00:00",
                connector="thread",
            ),
        ),
        "evidence_gaps": ("impact metric not supplied",),
        "content_fingerprint": "synthetic-fingerprint",
        "observed_at": "2026-08-20T00:00:00+00:00",
    }
    base.update(overrides)
    return DeliveryRecord(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["03/04/2026", "04/03/2026", "1/2"])
def test_ambiguous_period_is_forced_to_literal_text(value: str) -> None:
    cell = serialize_period(value)
    assert cell.value == f"'{value}"
    assert cell.input_mode == "RAW"


@pytest.mark.parametrize("value", ["13/04/2026", "04/13/2026", "Q2 2026", ""])
def test_unambiguous_period_remains_raw(value: str) -> None:
    cell = serialize_period(value)
    assert cell.value == value
    assert cell.input_mode == "RAW"


def test_period_is_trimmed_before_ambiguous_literal_prefix() -> None:
    cell = serialize_period("  03/04/2026  ")

    assert cell.value == "'03/04/2026"
    assert cell.input_mode == "RAW"


def test_projection_is_fixed_width_raw_and_preserves_evidence_gaps() -> None:
    projection = project_bragsheet(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
        start_row=2,
    )

    assert projection.columns == BRAGSHEET_COLUMNS
    assert len(projection.values) == 1
    assert len(projection.values[0]) == len(BRAGSHEET_COLUMNS)
    assert projection.values[0][1] == "'03/04/2026"
    assert projection.input_mode == "RAW"
    assert projection.evidence_gaps == {
        "delivery:synthetic-1": ("impact metric not supplied",)
    }


class OrderedConsent:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def require(self, grant_type: str, resource_id: str, scope: str) -> None:
        assert (grant_type, resource_id, scope) == (
            "destination",
            "sheet:synthetic-sheet",
            "write:bragsheet",
        )
        self.events.append("consent")


class ExactGateway:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.calls: list[dict[str, object]] = []
        self.values: list[list[object]] = []

    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        self.events.append(str(payload["action"]))
        self.calls.append(payload)
        if payload["action"] == "sheets.writeBragsheet":
            assert payload["inputMode"] == "RAW"
            self.values = [list(row) for row in payload["values"]]  # type: ignore[index]
            return envelope(payload, {"updatedRows": len(self.values)})
        if payload["action"] == "sheets.readBack":
            return envelope(payload, {"values": self.values})
        raise AssertionError("unexpected action")


class ExplodingExternalCollaborator:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"preview touched external collaborator: {name}")


def test_sync_service_preview_does_not_touch_external_collaborators() -> None:
    external = ExplodingExternalCollaborator()
    service = SyncService(
        consent=external,  # type: ignore[arg-type]
        run_store=external,  # type: ignore[arg-type]
    )

    projection = service.preview(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
    )

    assert projection.row_count == 1


def envelope(
    payload: dict[str, object],
    data: dict[str, object],
) -> dict[str, object]:
    return {
        "ok": True,
        "requestId": payload.get("requestId", "synthetic"),
        "data": data,
        "errors": [],
        "version": "1.0.0",
    }


def test_sync_checks_destination_consent_immediately_before_write(store) -> None:
    events: list[str] = []
    service = SyncService(
        consent=OrderedConsent(events),  # type: ignore[arg-type]
        run_store=EncryptedSyncRunStore(store.connection()),
    )
    projection = project_bragsheet(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
    )

    assert events == []
    service.write_and_verify(projection, ExactGateway(events))
    assert events == [
        "consent",
        "sheets.writeBragsheet",
        "consent",
        "sheets.readBack",
    ]


def test_sync_rechecks_destination_consent_before_readback(store) -> None:
    consent = ConsentService(store)
    consent.grant(
        "destination",
        "sheet:synthetic-sheet",
        ("write:bragsheet",),
    )

    class RevokingGateway(ExactGateway):
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            response = super().invoke(payload)
            if payload["action"] == "sheets.writeBragsheet":
                consent.revoke("destination", "sheet:synthetic-sheet")
            return response

    service = SyncService(
        consent=consent,
        run_store=EncryptedSyncRunStore(store.connection()),
    )
    projection = project_bragsheet(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
    )
    gateway = RevokingGateway()

    with pytest.raises(ConsentDenied, match="revoked"):
        service.write_and_verify(projection, gateway)

    assert [call["action"] for call in gateway.calls] == ["sheets.writeBragsheet"]


def test_write_and_exact_readback_marks_synced(store) -> None:
    consent = ConsentService(store)
    consent.grant(
        "destination",
        "sheet:synthetic-sheet",
        ("write:bragsheet",),
    )
    service = SyncService(
        consent=consent,
        run_store=EncryptedSyncRunStore(store.connection()),
    )
    projection = project_bragsheet(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
    )

    result = service.write_and_verify(projection, ExactGateway())

    assert result.status == "synced"
    assert service.last_run == result
    stored = store.connection().execute(
        "SELECT status FROM sync_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert stored == ("synced",)


class MismatchingGateway(ExactGateway):
    def invoke(self, payload: dict[str, object]) -> dict[str, object]:
        response = super().invoke(payload)
        if payload["action"] == "sheets.readBack":
            response["data"] = {"values": [["different"]]}
        return response


def test_readback_mismatch_never_marks_synced(store) -> None:
    consent = ConsentService(store)
    consent.grant(
        "destination",
        "sheet:synthetic-sheet",
        ("write:bragsheet",),
    )
    service = SyncService(
        consent=consent,
        run_store=EncryptedSyncRunStore(store.connection()),
    )
    projection = project_bragsheet(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
    )

    with pytest.raises(ReadbackMismatch):
        service.write_and_verify(projection, MismatchingGateway())

    assert service.last_run is not None
    assert service.last_run.status == "reconciliation_required"
    stored = store.connection().execute(
        "SELECT status FROM sync_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert stored == ("reconciliation_required",)


def test_reconciliation_record_failure_preserves_original_readback_error(store) -> None:
    class FailingRunStore:
        def record(self, _run) -> None:
            raise RuntimeError("synthetic run-store failure")

    consent = ConsentService(store)
    consent.grant(
        "destination",
        "sheet:synthetic-sheet",
        ("write:bragsheet",),
    )
    service = SyncService(
        consent=consent,
        run_store=FailingRunStore(),  # type: ignore[arg-type]
    )
    projection = project_bragsheet(
        (synthetic_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
    )

    with pytest.raises(ReadbackMismatch) as raised:
        service.write_and_verify(projection, MismatchingGateway())

    assert any(
        "reconciliation status could not be recorded" in note
        for note in getattr(raised.value, "__notes__", ())
    )


def test_evidence_gaps_round_trip_after_projection_migration(store) -> None:
    repository = EncryptedRecordStore.from_encrypted_store(store)
    record = synthetic_record()

    repository.persist_records((record,))

    loaded = repository.load_record(record.id)
    assert loaded is not None
    assert loaded.evidence_gaps == ("impact metric not supplied",)


class SequenceTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        body: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        self.requests.append(
            {
                "url": url,
                "body": json.loads(body),
                "headers": headers,
                "timeout": timeout_seconds,
            }
        )
        return self.responses.pop(0)


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


def unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_fixture(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("gateway fixture exited before accepting requests")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("gateway fixture did not start within five seconds")


def test_browser_client_posts_protocol_metadata_and_accepts_json_envelope() -> None:
    transport = SequenceTransport(
        [
            HttpResponse(
                status=200,
                text=json.dumps(
                    {
                        "ok": True,
                        "requestId": "request-1",
                        "data": {"status": "healthy"},
                        "errors": [],
                        "version": "1.0.0",
                    }
                ),
            )
        ]
    )
    client = BrowserModeClient(
        "https://script.google.com/macros/s/synthetic/exec",
        transport=transport,
        clock=lambda: 1_787_198_400,
        nonce_factory=lambda: "synthetic-nonce-0001",
        request_id_factory=lambda: "request-1",
        sleep=lambda _: None,
    )

    response = client.invoke({"action": "health"})

    assert response["data"] == {"status": "healthy"}
    assert transport.requests[0]["body"] == {
        "action": "health",
        "requestId": "request-1",
        "timestamp": 1_787_198_400,
        "nonce": "synthetic-nonce-0001",
    }
    assert transport.requests[0]["headers"] == {
        "Content-Type": "application/json",
    }


def test_browser_client_exercises_loopback_fixture_url_path() -> None:
    port = unused_loopback_port()
    environment = {
        **os.environ,
        "CAREEROS_FIXTURE_PORT": str(port),
        "CAREEROS_FIXTURE_NOW": "1787198400",
    }
    process = subprocess.Popen(
        ["node", "tests/apps-script/fixture_server.mjs"],
        cwd=os.fspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_fixture(port, process)
        client = BrowserModeClient(
            f"http://127.0.0.1:{port}/exec",
            transport=UrlLibTransport(),
            clock=lambda: 1_787_198_400,
            nonce_factory=lambda: "loopback-fixture-nonce-0001",
            request_id_factory=lambda: "loopback-fixture-request",
            sleep=lambda _: None,
        )

        response = client.invoke({"action": "health"})

        assert response == {
            "ok": True,
            "requestId": "loopback-fixture-request",
            "data": {"status": "healthy"},
            "errors": [],
            "version": "1.0.0",
        }
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_browser_client_retries_transient_interstitial_with_finite_attempts() -> None:
    transport = SequenceTransport(
        [
            HttpResponse(status=503, text="Sorry, unable to open the file"),
            HttpResponse(
                status=200,
                text=json.dumps(
                    {
                        "ok": True,
                        "requestId": "request-1",
                        "data": {"status": "healthy"},
                        "errors": [],
                        "version": "1.0.0",
                    }
                ),
            ),
        ]
    )
    delays: list[float] = []
    client = BrowserModeClient(
        "https://script.google.com/macros/s/synthetic/exec",
        transport=transport,
        clock=lambda: 1_787_198_400,
        nonce_factory=lambda: "synthetic-nonce-0001",
        request_id_factory=lambda: "request-1",
        sleep=delays.append,
        max_attempts=2,
    )

    client.invoke({"action": "health"})

    assert len(transport.requests) == 2
    assert delays == [0.25]


@pytest.mark.parametrize(
    "action",
    ("sheets.writeBragsheet", "sheets.writeHomepage"),
)
def test_browser_client_does_not_retry_ambiguous_write(action: str) -> None:
    transport = SequenceTransport(
        [
            HttpResponse(status=503, text="Sorry, unable to open the file"),
            HttpResponse(status=200, text="must not be reached"),
        ]
    )
    client = BrowserModeClient(
        "https://script.google.com/macros/s/synthetic/exec",
        transport=transport,
        clock=lambda: 1_787_198_400,
        nonce_factory=lambda: "synthetic-nonce-0001",
        request_id_factory=lambda: "request-1",
        sleep=lambda _: None,
        max_attempts=2,
    )

    with pytest.raises(GatewayProtocolError, match="ambiguous"):
        client.invoke(
            {
                "action": action,
                "idempotencyKey": "synthetic-write-key",
            }
        )

    assert len(transport.requests) == 1


def test_browser_client_rejects_wrong_request_id() -> None:
    body = {
        "ok": True,
        "requestId": "other-request",
        "data": {},
        "errors": [],
        "version": "1.0.0",
    }
    transport = SequenceTransport([HttpResponse(status=200, text=json.dumps(body))])
    client = BrowserModeClient(
        "https://script.google.com/macros/s/synthetic/exec",
        transport=transport,
        clock=lambda: 1_787_198_400,
        nonce_factory=lambda: "synthetic-nonce-0001",
        request_id_factory=lambda: "request-1",
        sleep=lambda _: None,
    )

    with pytest.raises(GatewayProtocolError, match="requestId"):
        client.invoke({"action": "health"})

