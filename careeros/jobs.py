from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from careeros.consent import ConsentService
from careeros.projections import BragSheetProjection
from careeros.sync import SyncGateway, SyncRun

JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
WRITE_ACTIONS = frozenset({"sheets.writeBragsheet"})
STALE_MALFORMED_LOCK_SECONDS = 60 * 60


class UnknownJob(ValueError):
    """Raised when a requested background job is not configured."""


class InvalidJobId(ValueError):
    """Raised when a job ID is unsafe for grants or lock files."""


class IdempotencyConflict(RuntimeError):
    """Raised when one idempotency key is reused for a different write."""


class JobSync(Protocol):
    def write_and_verify(
        self,
        projection: BragSheetProjection,
        gateway: SyncGateway,
        *,
        idempotency_key: str,
    ) -> SyncRun: ...


class WriteReceiptStore(Protocol):
    def contains(
        self,
        idempotency_key: str,
        payload: Mapping[str, object],
    ) -> bool: ...

    def record(
        self,
        idempotency_key: str,
        payload: Mapping[str, object],
    ) -> None: ...


@dataclass(frozen=True)
class JobResult:
    job_id: str
    status: str
    idempotency_key: str | None
    sync_result: object | None = None


class _ExclusiveJobLock:
    def __init__(
        self,
        path: Path,
        *,
        pid_is_alive: Callable[[int], bool],
    ) -> None:
        self._path = path
        self._pid_is_alive = pid_is_alive
        self._descriptor: int | None = None

    def acquire(self) -> bool:
        if self._create():
            return True
        owner_pid = self._read_owner_pid()
        if owner_pid is None:
            if not self._malformed_lock_is_stale():
                return False
        elif self._pid_is_alive(owner_pid):
            return False
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
        return self._create()

    def _create(self) -> bool:
        try:
            self._descriptor = os.open(
                self._path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            return False
        try:
            os.write(self._descriptor, str(os.getpid()).encode("ascii"))
        except OSError:
            self.release()
            raise
        return True

    def _read_owner_pid(self) -> int | None:
        try:
            value = self._path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return None
        if not value.isascii() or not value.isdecimal():
            return None
        pid = int(value)
        return pid if pid > 0 else None

    def _malformed_lock_is_stale(self) -> bool:
        try:
            age_seconds = time.time() - self._path.stat().st_mtime
        except OSError:
            return False
        return age_seconds >= STALE_MALFORMED_LOCK_SECONDS

    def release(self) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is None:
            return
        try:
            os.close(descriptor)
        finally:
            self._path.unlink(missing_ok=True)


class FileWriteReceiptStore:
    """Stores only hashes proving that a local write returned success."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        _ensure_private_directory(self._directory)

    def contains(
        self,
        idempotency_key: str,
        payload: Mapping[str, object],
    ) -> bool:
        path = self._path(idempotency_key)
        try:
            recorded_digest = path.read_text(encoding="ascii")
        except FileNotFoundError:
            return False
        expected_digest = _payload_digest(payload)
        if recorded_digest != expected_digest:
            raise IdempotencyConflict(
                "Idempotency key was already used for a different write"
            )
        return True

    def record(
        self,
        idempotency_key: str,
        payload: Mapping[str, object],
    ) -> None:
        path = self._path(idempotency_key)
        digest = _payload_digest(payload)
        try:
            descriptor = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if self.contains(idempotency_key, payload):
                return
            raise
        try:
            os.write(descriptor, digest.encode("ascii"))
        finally:
            os.close(descriptor)

    def _path(self, idempotency_key: str) -> Path:
        key_digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return self._directory / f"{key_digest}.done"


class _RunGateway:
    def __init__(
        self,
        *,
        consent: ConsentService,
        job_resource_id: str,
        gateway: SyncGateway,
        idempotency_key: str,
        write_receipts: WriteReceiptStore,
    ) -> None:
        self._consent = consent
        self._job_resource_id = job_resource_id
        self._gateway = gateway
        self._idempotency_key = idempotency_key
        self._write_receipts = write_receipts

    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        self._consent.require(
            "background",
            self._job_resource_id,
            "run",
        )
        request = dict(payload)
        request["idempotencyKey"] = self._idempotency_key

        is_write = request.get("action") in WRITE_ACTIONS
        if is_write and self._write_receipts.contains(
            self._idempotency_key,
            request,
        ):
            return {"ok": True, "data": {"deduplicated": True}}

        response = self._gateway.invoke(request)
        if is_write and response.get("ok") is True:
            self._write_receipts.record(self._idempotency_key, request)
        return response


class JobRunner:
    def __init__(
        self,
        *,
        consent: ConsentService,
        sync: JobSync,
        gateway: SyncGateway,
        jobs: Mapping[str, BragSheetProjection],
        lock_directory: Path,
        idempotency_key_factory: Callable[[], str] | None = None,
        pid_is_alive: Callable[[int], bool] | None = None,
        write_receipts: WriteReceiptStore | None = None,
    ) -> None:
        self.consent = consent
        self.sync = sync
        self.gateway = gateway
        self._jobs = dict(jobs)
        self._lock_directory = lock_directory.expanduser()
        _ensure_private_directory(self._lock_directory)
        self._idempotency_key_factory = idempotency_key_factory or (
            lambda: uuid.uuid4().hex
        )
        self._pid_is_alive = pid_is_alive or _pid_is_alive
        self._write_receipts = write_receipts or FileWriteReceiptStore(
            self._lock_directory / "write-receipts"
        )

    def run(self, job_id: str) -> JobResult:
        normalized_job_id = _validate_job_id(job_id)
        try:
            projection = self._jobs[normalized_job_id]
        except KeyError as exc:
            raise UnknownJob(
                f"Background job is not configured: {normalized_job_id}"
            ) from exc

        lock = _ExclusiveJobLock(
            self._lock_directory / f"{normalized_job_id}.lock",
            pid_is_alive=self._pid_is_alive,
        )
        if not lock.acquire():
            return JobResult(
                job_id=normalized_job_id,
                status="already_running",
                idempotency_key=None,
            )

        try:
            resource_id = f"job:{normalized_job_id}"
            self.consent.require("background", resource_id, "run")
            idempotency_key = self._idempotency_key_factory()
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise ValueError("Idempotency key factory must return a nonempty string")

            gateway = _RunGateway(
                consent=self.consent,
                job_resource_id=resource_id,
                gateway=self.gateway,
                idempotency_key=idempotency_key,
                write_receipts=self._write_receipts,
            )
            sync_result = self.sync.write_and_verify(
                projection,
                gateway,
                idempotency_key=idempotency_key,
            )
            status = getattr(sync_result, "status", "completed")
            if not isinstance(status, str):
                raise TypeError("Sync result status must be a string")
            return JobResult(
                job_id=normalized_job_id,
                status=status,
                idempotency_key=idempotency_key,
                sync_result=sync_result,
            )
        finally:
            lock.release()


def _validate_job_id(job_id: str) -> str:
    normalized = job_id.strip()
    if not JOB_ID_PATTERN.fullmatch(normalized):
        raise InvalidJobId(
            "Job ID must contain only letters, digits, underscores, or hyphens"
        )
    return normalized


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _payload_digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        dict(payload),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
