from __future__ import annotations

import os
import re
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


class UnknownJob(ValueError):
    """Raised when a requested background job is not configured."""


class InvalidJobId(ValueError):
    """Raised when a job ID is unsafe for grants or lock files."""


class JobSync(Protocol):
    def write_and_verify(
        self,
        projection: BragSheetProjection,
        gateway: SyncGateway,
        *,
        idempotency_key: str,
    ) -> SyncRun: ...


@dataclass(frozen=True)
class JobResult:
    job_id: str
    status: str
    idempotency_key: str | None
    sync_result: object | None = None


class _ExclusiveJobLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._descriptor: int | None = None

    def acquire(self) -> bool:
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

    def release(self) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is None:
            return
        try:
            os.close(descriptor)
        finally:
            self._path.unlink(missing_ok=True)


class _RunGateway:
    def __init__(
        self,
        *,
        consent: ConsentService,
        job_resource_id: str,
        gateway: SyncGateway,
        idempotency_key: str,
    ) -> None:
        self._consent = consent
        self._job_resource_id = job_resource_id
        self._gateway = gateway
        self._idempotency_key = idempotency_key
        self._completed_writes: list[
            tuple[dict[str, object], Mapping[str, object]]
        ] = []

    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        self._consent.require(
            "background",
            self._job_resource_id,
            "run",
        )
        request = dict(payload)
        request["idempotencyKey"] = self._idempotency_key

        if request.get("action") in WRITE_ACTIONS:
            for completed_request, response in self._completed_writes:
                if completed_request == request:
                    return response

        response = self._gateway.invoke(request)
        if request.get("action") in WRITE_ACTIONS and response.get("ok") is True:
            self._completed_writes.append((request, response))
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
    ) -> None:
        self.consent = consent
        self.sync = sync
        self.gateway = gateway
        self._jobs = dict(jobs)
        self._lock_directory = lock_directory.expanduser()
        self._lock_directory.mkdir(parents=True, exist_ok=True)
        self._idempotency_key_factory = idempotency_key_factory or (
            lambda: uuid.uuid4().hex
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
