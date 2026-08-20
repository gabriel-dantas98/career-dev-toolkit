from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from careeros.consent import normalize_resource_id
from careeros.models import DeliveryRecord

MAX_BRAGSHEET_ROWS = 200
MAX_BRAGSHEET_COLUMNS = 12
BRAGSHEET_COLUMNS = (
    "record_id",
    "period",
    "title",
    "tags",
    "context",
    "confidence",
    "situation",
    "task",
    "action",
    "result",
    "evidence",
    "evidence_gaps",
)

_SLASH_PERIOD = re.compile(
    r"^\s*(?P<first>\d{1,2})/(?P<second>\d{1,2})(?:/(?P<year>\d{2,4}))?\s*$"
)


@dataclass(frozen=True)
class SerializedCell:
    value: object
    input_mode: str = "RAW"


@dataclass(frozen=True)
class BragSheetProjection:
    destination_id: str
    sheet_name: str
    start_row: int
    columns: tuple[str, ...]
    values: tuple[tuple[object, ...], ...]
    evidence_gaps: Mapping[str, tuple[str, ...]]
    input_mode: str = "RAW"

    @property
    def row_count(self) -> int:
        return len(self.values)

    @property
    def column_count(self) -> int:
        return len(self.columns)


def serialize_period(value: str | None) -> SerializedCell:
    normalized = value or ""
    match = _SLASH_PERIOD.fullmatch(normalized)
    if match:
        first = int(match.group("first"))
        second = int(match.group("second"))
        if 1 <= first <= 12 and 1 <= second <= 12:
            return SerializedCell(value=f"'{normalized}")
    return SerializedCell(value=normalized)


def project_bragsheet(
    records: Sequence[DeliveryRecord],
    *,
    destination_id: str,
    sheet_name: str,
    start_row: int = 2,
) -> BragSheetProjection:
    canonical_destination = normalize_resource_id(destination_id)
    if not canonical_destination.startswith("sheet:"):
        raise ValueError("Brag-sheet destination must be a sheet ID")
    if not sheet_name.strip() or len(sheet_name) > 100:
        raise ValueError("sheet_name must contain 1 to 100 characters")
    if start_row < 1 or start_row > 1_000_000:
        raise ValueError("start_row is outside Google Sheets bounds")
    if len(records) > MAX_BRAGSHEET_ROWS:
        raise ValueError(f"Brag-sheet projection is limited to {MAX_BRAGSHEET_ROWS} rows")
    if len(BRAGSHEET_COLUMNS) > MAX_BRAGSHEET_COLUMNS:
        raise RuntimeError("Brag-sheet projection exceeds its fixed column bound")

    values = tuple(_project_record(record) for record in records)
    gaps = MappingProxyType(
        {
            record.id: tuple(record.evidence_gaps)
            for record in records
            if record.evidence_gaps
        }
    )
    return BragSheetProjection(
        destination_id=canonical_destination,
        sheet_name=sheet_name.strip(),
        start_row=start_row,
        columns=BRAGSHEET_COLUMNS,
        values=values,
        evidence_gaps=gaps,
    )


def _project_record(record: DeliveryRecord) -> tuple[object, ...]:
    period = serialize_period(record.period)
    evidence = "\n".join(ref.locator for ref in record.evidence)
    evidence_gaps = "\n".join(record.evidence_gaps)
    row = (
        record.id,
        period.value,
        record.title,
        ", ".join(record.tags),
        record.context or "",
        record.confidence or "",
        record.situation or "",
        record.task or "",
        record.action or "",
        record.result or "",
        evidence,
        evidence_gaps,
    )
    if len(row) != len(BRAGSHEET_COLUMNS):
        raise RuntimeError("Brag-sheet row does not match the fixed schema")
    return row
