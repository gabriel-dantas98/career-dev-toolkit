from __future__ import annotations

import subprocess
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from careeros.consent import ConsentDenied, ConsentService
from careeros.jobs import JobRunner
from careeros.projections import BragSheetProjection
from careeros.scheduler import Schedule, Scheduler
from careeros.sync import SyncService


class RecordingGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.values: list[list[object]] = []

    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        call = dict(payload)
        self.calls.append(call)
        if payload["action"] == "sheets.writeBragsheet":
            self.values = [list(row) for row in payload["values"]]  # type: ignore[index]
            return {"ok": True, "data": {"updatedRows": len(self.values)}}
        if payload["action"] == "sheets.readBack":
            return {"ok": True, "data": {"values": self.values}}
        raise AssertionError("unexpected gateway action")


class RecordingRunStore:
    def __init__(self) -> None:
        self.runs: list[object] = []

    def record(self, run: object) -> None:
        self.runs.append(run)


class ThreadSafeConsent:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._revoked = False
        self.checks: list[tuple[str, str, str]] = []

    def require(self, grant_type: str, resource_id: str, scope: str) -> None:
        with self._lock:
            self.checks.append((grant_type, resource_id, scope))
            if grant_type == "background" and self._revoked:
                raise ConsentDenied("background grant revoked")

    def revoke_background(self) -> None:
        with self._lock:
            self._revoked = True


class BlockingSync:
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self.entered = entered
        self.release = release
        self.calls = 0

    def write_and_verify(
        self,
        projection: BragSheetProjection,
        gateway: object,
        *,
        idempotency_key: str,
    ) -> object:
        del projection, gateway, idempotency_key
        self.calls += 1
        self.entered.set()
        assert self.release.wait(timeout=5)
        return type("SyncResult", (), {"status": "synced"})()


def projection() -> BragSheetProjection:
    return BragSheetProjection(
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
        start_row=2,
        columns=("record_id",),
        values=(("rec:synthetic",),),
        evidence_gaps={},
    )


def runner(
    tmp_path: Path,
    *,
    consent: object,
    sync: object,
    gateway: object,
    key_factory=None,
) -> JobRunner:
    return JobRunner(
        consent=consent,
        sync=sync,
        gateway=gateway,
        jobs={"daily": projection()},
        lock_directory=tmp_path / "locks",
        idempotency_key_factory=key_factory,
    )


def test_overlapping_job_exits_without_second_gateway_or_sync_call(tmp_path) -> None:
    entered = threading.Event()
    release = threading.Event()
    consent = ThreadSafeConsent()
    sync = BlockingSync(entered, release)
    gateway = RecordingGateway()
    job_runner = runner(
        tmp_path,
        consent=consent,
        sync=sync,
        gateway=gateway,
    )
    completed: list[object] = []

    thread = threading.Thread(target=lambda: completed.append(job_runner.run("daily")))
    thread.start()
    assert entered.wait(timeout=5)

    overlap = job_runner.run("daily")
    assert overlap.status == "already_running"
    assert sync.calls == 1
    assert gateway.calls == []

    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert completed[0].status == "synced"


def test_destination_grant_does_not_authorize_background_run(store, tmp_path) -> None:
    consent = ConsentService(store)
    consent.grant("destination", "sheet:synthetic-sheet", ("write:bragsheet",))
    sync = SyncService(consent=consent, run_store=RecordingRunStore())
    gateway = RecordingGateway()
    job_runner = runner(tmp_path, consent=consent, sync=sync, gateway=gateway)

    with pytest.raises(ConsentDenied, match="background"):
        job_runner.run("daily")

    assert gateway.calls == []


def test_revoked_background_grant_blocks_before_network(store, tmp_path) -> None:
    consent = ConsentService(store)
    consent.grant("background", "job:daily", ("run",))
    consent.grant("destination", "sheet:synthetic-sheet", ("write:bragsheet",))
    consent.revoke("background", "job:daily")
    sync = SyncService(consent=consent, run_store=RecordingRunStore())
    gateway = RecordingGateway()
    job_runner = runner(tmp_path, consent=consent, sync=sync, gateway=gateway)

    with pytest.raises(ConsentDenied, match="revoked"):
        job_runner.run("daily")

    assert gateway.calls == []


def test_background_consent_is_rechecked_before_each_external_call(tmp_path) -> None:
    consent = ThreadSafeConsent()

    class RevokeAfterWriteGateway(RecordingGateway):
        def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]:
            response = super().invoke(payload)
            if payload["action"] == "sheets.writeBragsheet":
                consent.revoke_background()
            return response

    gateway = RevokeAfterWriteGateway()
    sync = SyncService(consent=consent, run_store=RecordingRunStore())  # type: ignore[arg-type]
    job_runner = runner(tmp_path, consent=consent, sync=sync, gateway=gateway)

    with pytest.raises(ConsentDenied, match="revoked"):
        job_runner.run("daily")

    assert [call["action"] for call in gateway.calls] == ["sheets.writeBragsheet"]


def test_run_uses_one_idempotency_key_and_separate_runs_use_new_keys(tmp_path) -> None:
    consent = ThreadSafeConsent()
    gateway = RecordingGateway()
    sync = SyncService(consent=consent, run_store=RecordingRunStore())  # type: ignore[arg-type]
    keys = iter(("synthetic-run-1", "synthetic-run-2"))
    job_runner = runner(
        tmp_path,
        consent=consent,
        sync=sync,
        gateway=gateway,
        key_factory=lambda: next(keys),
    )

    first = job_runner.run("daily")
    second = job_runner.run("daily")

    assert first.idempotency_key == "synthetic-run-1"
    assert second.idempotency_key == "synthetic-run-2"
    assert [call["idempotencyKey"] for call in gateway.calls] == [
        "synthetic-run-1",
        "synthetic-run-1",
        "synthetic-run-2",
        "synthetic-run-2",
    ]
    assert [call["action"] for call in gateway.calls].count(
        "sheets.writeBragsheet"
    ) == 2


def test_retried_write_within_run_does_not_call_gateway_twice(tmp_path) -> None:
    consent = ThreadSafeConsent()
    gateway = RecordingGateway()

    class RetryingSync:
        def write_and_verify(
            self,
            projection: BragSheetProjection,
            guarded_gateway: object,
            *,
            idempotency_key: str,
        ) -> object:
            del projection, idempotency_key
            payload = {
                "action": "sheets.writeBragsheet",
                "values": [["synthetic"]],
            }
            guarded_gateway.invoke(payload)  # type: ignore[attr-defined]
            guarded_gateway.invoke(payload)  # type: ignore[attr-defined]
            return type("SyncResult", (), {"status": "synced"})()

    job_runner = runner(
        tmp_path,
        consent=consent,
        sync=RetryingSync(),
        gateway=gateway,
        key_factory=lambda: "synthetic-retry-key",
    )

    result = job_runner.run("daily")

    assert result.status == "synced"
    assert len(gateway.calls) == 1
    assert gateway.calls[0]["idempotencyKey"] == "synthetic-retry-key"


@pytest.mark.parametrize("failure", [False, True], ids=["success", "failure"])
def test_lock_is_released_after_run_completion(tmp_path, failure: bool) -> None:
    consent = ThreadSafeConsent()

    class SometimesFailingSync:
        def __init__(self) -> None:
            self.calls = 0

        def write_and_verify(self, projection, gateway, *, idempotency_key):
            del projection, gateway, idempotency_key
            self.calls += 1
            if failure and self.calls == 1:
                raise RuntimeError("synthetic sync failure")
            return type("SyncResult", (), {"status": "synced"})()

    sync = SometimesFailingSync()
    job_runner = runner(
        tmp_path,
        consent=consent,
        sync=sync,
        gateway=RecordingGateway(),
    )

    if failure:
        with pytest.raises(RuntimeError, match="synthetic sync failure"):
            job_runner.run("daily")
    else:
        assert job_runner.run("daily").status == "synced"

    assert job_runner.run("daily").status == "synced"
    assert sync.calls == 2


class RecordingCommandRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(tuple(command))
        return subprocess.CompletedProcess(command, 0, "", "")


@pytest.mark.parametrize(
    ("system_name", "native_command"),
    [
        ("Linux", "systemctl"),
        ("Darwin", "launchctl"),
        ("Windows", "schtasks"),
    ],
)
def test_scheduler_uses_user_level_native_adapter(
    tmp_path,
    system_name: str,
    native_command: str,
) -> None:
    commands = RecordingCommandRunner()
    scheduler = Scheduler(
        system_name=system_name,
        home=tmp_path,
        command_runner=commands,
        user_id=501,
    )

    result = scheduler.install(
        Schedule(
            job_id="daily",
            command=("python", "-m", "careeros", "run-job", "daily"),
            interval_minutes=60,
        )
    )

    assert result.ok is True
    assert result.status == "installed"
    assert commands.calls
    assert all(call[0] == native_command for call in commands.calls)
    assert all("cron" not in part.lower() for call in commands.calls for part in call)
    if system_name == "Linux":
        assert all("--user" in call for call in commands.calls)
    if system_name == "Darwin":
        assert any("gui/501" in call for call in commands.calls)


def test_scheduler_remove_uses_native_user_adapter(tmp_path) -> None:
    commands = RecordingCommandRunner()
    scheduler = Scheduler(
        system_name="Linux",
        home=tmp_path,
        command_runner=commands,
    )
    schedule = Schedule(job_id="daily", command=("careeros", "run-job", "daily"))
    assert scheduler.install(schedule).ok

    result = scheduler.remove("daily")

    assert result.ok is True
    assert result.status == "removed"
    assert any(call[:3] == ("systemctl", "--user", "disable") for call in commands.calls)


def test_unsupported_scheduler_returns_structured_error_without_command(
    tmp_path,
) -> None:
    commands = RecordingCommandRunner()
    scheduler = Scheduler(
        system_name="FreeBSD",
        home=tmp_path,
        command_runner=commands,
    )

    result = scheduler.install(
        Schedule(job_id="daily", command=("careeros", "run-job", "daily"))
    )

    assert result.ok is False
    assert result.status == "unsupported"
    assert result.error is not None
    assert result.error.code == "scheduler.unsupported"
    assert result.error.platform == "FreeBSD"
    assert commands.calls == []
