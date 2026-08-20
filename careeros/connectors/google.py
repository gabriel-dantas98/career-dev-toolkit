from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from careeros.consent import (
    ConsentService,
    InvalidResourceId,
    normalize_resource_id,
)
from careeros.connectors.base import (
    GOOGLE_SEARCH_ACTIONS,
    MAX_GOOGLE_RESULTS,
    CollectRequest,
    ConnectorRequestInvalid,
    Observation,
    bound_excerpt,
    validate_sheet_range,
    validate_time_window,
)
from careeros.connectors.timestamps import observation_timestamp, utc_now_iso

GOOGLE_ALLOWED_ACTIONS = frozenset(
    {
        "calendar.search",
        "gmail.search",
        "drive.search",
        "docs.read",
        "sheets.read",
    }
)

GOOGLE_CONNECTOR_RESOURCE = "connector:google"


class GoogleGateway(Protocol):
    def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]: ...


class GoogleConnector:
    def __init__(self, gateway: GoogleGateway, *, consent: ConsentService) -> None:
        self._gateway = gateway
        self._consent = consent

    def collect(self, request: CollectRequest) -> tuple[Observation, ...]:
        action = request.action
        if action is None:
            raise ConnectorRequestInvalid("Google action is required")
        if action not in GOOGLE_ALLOWED_ACTIONS:
            raise ConnectorRequestInvalid("Google action is not on the allowlist")

        max_results = request.max_results
        if action in GOOGLE_SEARCH_ACTIONS:
            if request.time_window is None:
                raise ConnectorRequestInvalid("Google search requires a bounded time window")
            validate_time_window(request.time_window)
            if max_results is None:
                raise ConnectorRequestInvalid("Google search requires max_results")
            if max_results < 1 or max_results > MAX_GOOGLE_RESULTS:
                raise ConnectorRequestInvalid(
                    f"Google max_results must be between 1 and {MAX_GOOGLE_RESULTS}"
                )

        if action in {"docs.read", "sheets.read"}:
            if not request.resource_id or not request.resource_id.strip():
                raise ConnectorRequestInvalid("Google read requires an explicit resource_id")
            _bare_google_id(request.resource_id, "doc" if action == "docs.read" else "sheet")

        if action == "sheets.read":
            if (
                request.sheet_name is None
                or not request.sheet_name.strip()
                or len(request.sheet_name) > 100
                or any(ord(character) < 32 for character in request.sheet_name)
            ):
                raise ConnectorRequestInvalid(
                    "sheets.read requires a bounded explicit sheet_name"
                )
            if request.range is None:
                raise ConnectorRequestInvalid("sheets.read requires a finite range")
            validate_sheet_range(request.range)

        self._consent.require("connector", GOOGLE_CONNECTOR_RESOURCE, action)

        payload = _build_payload(request, action)
        response = self._gateway.invoke(payload)
        return _observations_from_response(action, response, max_results=max_results)


def _build_payload(request: CollectRequest, action: str) -> dict[str, object]:
    payload: dict[str, object] = {"action": action}
    if request.query is not None:
        payload["query"] = request.query
    if request.time_window is not None:
        payload["timeMin"], payload["timeMax"] = request.time_window
    if request.max_results is not None:
        payload["maxResults"] = request.max_results
    if action == "docs.read" and request.resource_id is not None:
        payload["documentId"] = _bare_google_id(request.resource_id, "doc")
    if action == "sheets.read" and request.resource_id is not None:
        payload["spreadsheetId"] = _bare_google_id(request.resource_id, "sheet")
        payload["sheetName"] = request.sheet_name.strip() if request.sheet_name else ""
        payload["range"] = validate_sheet_range(request.range or "")
    return payload


def _observations_from_response(
    action: str,
    response: Mapping[str, object],
    *,
    max_results: int | None,
) -> tuple[Observation, ...]:
    if not response.get("ok", False):
        return ()

    data = response.get("data")
    if not isinstance(data, Mapping):
        return ()

    if action == "gmail.search":
        messages = data.get("messages")
        if not isinstance(messages, list):
            return ()
        bounded = messages if max_results is None else messages[:max_results]
        return tuple(_gmail_observation(item) for item in bounded if isinstance(item, Mapping))

    if action == "calendar.search":
        events = data.get("events")
        if not isinstance(events, list):
            return ()
        bounded = events if max_results is None else events[:max_results]
        return tuple(_calendar_observation(item) for item in bounded if isinstance(item, Mapping))

    if action == "drive.search":
        files = data.get("files")
        if not isinstance(files, list):
            return ()
        bounded = files if max_results is None else files[:max_results]
        return tuple(_drive_observation(item) for item in bounded if isinstance(item, Mapping))

    if action == "docs.read":
        content = str(data.get("content", ""))
        resource_id = _canonical_response_id(data.get("resourceId"), "doc")
        return (
            Observation(
                source_id=resource_id,
                source_connector="google",
                source_locator=resource_id,
                title="Google Doc excerpt",
                tags=("delivery",),
                period=None,
                observed_at=utc_now_iso(),
                excerpt=bound_excerpt(content),
                provenance=("google",),
            ),
        )

    if action == "sheets.read":
        values = data.get("values")
        excerpt = bound_excerpt(str(values))
        resource_id = _canonical_response_id(data.get("resourceId"), "sheet")
        return (
            Observation(
                source_id=resource_id,
                source_connector="google",
                source_locator=resource_id,
                title="Google Sheet excerpt",
                tags=("delivery",),
                period=None,
                observed_at=utc_now_iso(),
                excerpt=excerpt,
                provenance=("google",),
            ),
        )

    return ()


def _bare_google_id(resource_id: str, expected_prefix: str) -> str:
    try:
        canonical = normalize_resource_id(resource_id)
    except InvalidResourceId as exc:
        raise ConnectorRequestInvalid("Google read resource_id is invalid") from exc
    prefix, identifier = canonical.split(":", 1)
    if prefix != expected_prefix:
        raise ConnectorRequestInvalid(
            f"Google read requires a canonical {expected_prefix}: resource_id"
        )
    return identifier


def _canonical_response_id(value: object, prefix: str) -> str:
    identifier = str(value or "unknown")
    if identifier.startswith(f"{prefix}:"):
        return identifier
    return f"{prefix}:{identifier}"


def _gmail_observation(item: Mapping[str, Any]) -> Observation:
    message_id = str(item.get("id", "unknown"))
    subject = str(item.get("subject", "Gmail message"))
    snippet = str(item.get("snippet", ""))
    return Observation(
        source_id=f"gmail:{message_id}",
        source_connector="google",
        source_locator=f"gmail:{message_id}",
        title=subject,
        tags=("kudos",) if "kudos" in subject.lower() else ("delivery",),
        period=None,
        observed_at=observation_timestamp(item.get("date")),
        excerpt=bound_excerpt(snippet),
        provenance=("google",),
    )


def _calendar_observation(item: Mapping[str, Any]) -> Observation:
    event_id = str(item.get("id", "unknown"))
    summary = str(item.get("summary", "Calendar event"))
    return Observation(
        source_id=f"calendar:{event_id}",
        source_connector="google",
        source_locator=f"calendar:{event_id}",
        title=summary,
        tags=("delivery",),
        period=None,
        observed_at=observation_timestamp(item.get("start")),
        excerpt=summary,
        provenance=("google",),
    )


def _drive_observation(item: Mapping[str, Any]) -> Observation:
    file_id = str(item.get("id", "unknown"))
    name = str(item.get("name", "Drive file"))
    return Observation(
        source_id=f"drive:{file_id}",
        source_connector="google",
        source_locator=f"drive:{file_id}",
        title=name,
        tags=("delivery",),
        period=None,
        observed_at=observation_timestamp(item.get("modifiedTime")),
        excerpt=name,
        provenance=("google",),
    )
