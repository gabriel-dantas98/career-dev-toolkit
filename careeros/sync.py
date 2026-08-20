from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from careeros.consent import ConsentService
from careeros.models import DeliveryRecord
from careeros.projections import BragSheetProjection, project_bragsheet


class ReadbackMismatch(RuntimeError):
    """Raised when Google does not return the exact canonical values written."""


class SyncGatewayError(RuntimeError):
    """Raised when a gateway write or read-back cannot be verified."""


class SyncGateway(Protocol):
    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]: ...


class SyncRunStore(Protocol):
    def record(self, run: SyncRun) -> None: ...


@dataclass(frozen=True)
class SyncRun:
    destination_id: str
    status: str
    started_at: str
    finished_at: str


class EncryptedSyncRunStore:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def record(self, run: SyncRun) -> None:
        self._connection.execute(
            """
            INSERT INTO sync_runs (
                job_name,
                destination_id,
                started_at,
                finished_at,
                status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "write-bragsheet",
                run.destination_id,
                run.started_at,
                run.finished_at,
                run.status,
            ),
        )
        self._connection.commit()


class SyncService:
    def __init__(
        self,
        *,
        consent: ConsentService,
        run_store: SyncRunStore,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._consent = consent
        self._run_store = run_store
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.last_run: SyncRun | None = None

    def preview(
        self,
        records: Sequence[DeliveryRecord],
        *,
        destination_id: str,
        sheet_name: str,
        start_row: int = 2,
    ) -> BragSheetProjection:
        return project_bragsheet(
            records,
            destination_id=destination_id,
            sheet_name=sheet_name,
            start_row=start_row,
        )

    def write_and_verify(
        self,
        projection: BragSheetProjection,
        gateway: SyncGateway,
    ) -> SyncRun:
        started_at = self._now()

        # This is intentionally adjacent to the first external mutation.
        self._consent.require(
            "destination",
            projection.destination_id,
            "write:bragsheet",
        )

        try:
            write_response = gateway.invoke(_write_payload(projection))
            _require_success(write_response, "write")

            read_response = gateway.invoke(_readback_payload(projection))
            _require_success(read_response, "read-back")
            actual = _extract_values(read_response)
            if not _matrices_match(projection.values, actual):
                raise ReadbackMismatch(
                    "Brag-sheet read-back did not exactly match the intended projection"
                )
        except Exception:
            self._finish(projection.destination_id, "reconciliation_required", started_at)
            raise

        return self._finish(projection.destination_id, "synced", started_at)

    def _finish(
        self,
        destination_id: str,
        status: str,
        started_at: str,
    ) -> SyncRun:
        run = SyncRun(
            destination_id=destination_id,
            status=status,
            started_at=started_at,
            finished_at=self._now(),
        )
        self._run_store.record(run)
        self.last_run = run
        return run

    def _now(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("Sync clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc).isoformat()


def _write_payload(projection: BragSheetProjection) -> dict[str, object]:
    return {
        "action": "sheets.writeBragsheet",
        "spreadsheetId": projection.destination_id.removeprefix("sheet:"),
        "sheetName": projection.sheet_name,
        "startRow": projection.start_row,
        "inputMode": "RAW",
        "values": [list(row) for row in projection.values],
    }


def _readback_payload(projection: BragSheetProjection) -> dict[str, object]:
    return {
        "action": "sheets.readBack",
        "spreadsheetId": projection.destination_id.removeprefix("sheet:"),
        "sheetName": projection.sheet_name,
        "startRow": projection.start_row,
        "rowCount": projection.row_count,
        "columnCount": projection.column_count,
    }


def _require_success(response: Mapping[str, object], operation: str) -> None:
    if response.get("ok") is not True:
        raise SyncGatewayError(f"Brag-sheet gateway {operation} was not successful")


def _extract_values(response: Mapping[str, object]) -> list[list[object]]:
    data = response.get("data")
    if not isinstance(data, Mapping):
        raise SyncGatewayError("Brag-sheet read-back data is missing")
    values = data.get("values")
    if not isinstance(values, list):
        raise SyncGatewayError("Brag-sheet read-back values are missing")
    if not all(isinstance(row, list) for row in values):
        raise SyncGatewayError("Brag-sheet read-back values are malformed")
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
        for expected_value, actual_value in zip(expected_row, actual_row, strict=True):
            if type(expected_value) is not type(actual_value):
                return False
            if expected_value != actual_value:
                return False
    return True
