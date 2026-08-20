from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from careeros.consent import ConsentService
from careeros.connectors.base import (
    GOOGLE_SEARCH_ACTIONS,
    MAX_GOOGLE_RESULTS,
    CollectRequest,
    ConnectorRequestInvalid,
    Observation,
)

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

        if action in GOOGLE_SEARCH_ACTIONS:
            if request.time_window is None:
                raise ConnectorRequestInvalid("Google search requires a bounded time window")
            if request.max_results is None:
                raise ConnectorRequestInvalid("Google search requires max_results")
            if request.max_results < 1 or request.max_results > MAX_GOOGLE_RESULTS:
                raise ConnectorRequestInvalid(
                    f"Google max_results must be between 1 and {MAX_GOOGLE_RESULTS}"
                )

        if action in {"docs.read", "sheets.read"}:
            if not request.resource_id or not request.resource_id.strip():
                raise ConnectorRequestInvalid("Google read requires an explicit resource_id")

        self._consent.require("connector", GOOGLE_CONNECTOR_RESOURCE, action)

        payload = _build_payload(request, action)
        response = self._gateway.invoke(payload)
        return _observations_from_response(action, response)


def _build_payload(request: CollectRequest, action: str) -> dict[str, object]:
    payload: dict[str, object] = {"action": action}
    if request.query is not None:
        payload["query"] = request.query
    if request.time_window is not None:
        payload["timeMin"], payload["timeMax"] = request.time_window
    if request.max_results is not None:
        payload["maxResults"] = request.max_results
    if request.resource_id is not None:
        payload["resourceId"] = request.resource_id
    return payload


def _observations_from_response(
    action: str,
    response: Mapping[str, object],
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
        return tuple(_gmail_observation(item) for item in messages if isinstance(item, Mapping))

    if action == "calendar.search":
        events = data.get("events")
        if not isinstance(events, list):
            return ()
        return tuple(_calendar_observation(item) for item in events if isinstance(item, Mapping))

    if action == "drive.search":
        files = data.get("files")
        if not isinstance(files, list):
            return ()
        return tuple(_drive_observation(item) for item in files if isinstance(item, Mapping))

    if action == "docs.read":
        content = str(data.get("content", ""))
        resource_id = str(data.get("resourceId", "doc:unknown"))
        return (
            Observation(
                source_id=resource_id,
                source_connector="google",
                source_locator=resource_id,
                title="Google Doc excerpt",
                tags=("delivery",),
                period=None,
                observed_at="1970-01-01T00:00:00Z",
                excerpt=content[:MAX_GOOGLE_RESULTS * 100],
                provenance=("google",),
            ),
        )

    if action == "sheets.read":
        values = data.get("values")
        excerpt = str(values)[: MAX_GOOGLE_RESULTS * 100]
        resource_id = str(data.get("resourceId", "sheet:unknown"))
        return (
            Observation(
                source_id=resource_id,
                source_connector="google",
                source_locator=resource_id,
                title="Google Sheet excerpt",
                tags=("delivery",),
                period=None,
                observed_at="1970-01-01T00:00:00Z",
                excerpt=excerpt,
                provenance=("google",),
            ),
        )

    return ()


def _gmail_observation(item: Mapping[str, Any]) -> Observation:
    message_id = str(item.get("id", "unknown"))
    subject = str(item.get("subject", "Gmail message"))
    snippet = str(item.get("snippet", ""))
    observed_at = str(item.get("date", "1970-01-01T00:00:00Z"))
    return Observation(
        source_id=f"gmail:{message_id}",
        source_connector="google",
        source_locator=f"gmail:{message_id}",
        title=subject,
        tags=("kudos",) if "kudos" in subject.lower() else ("delivery",),
        period=None,
        observed_at=observed_at,
        excerpt=snippet,
        provenance=("google",),
    )


def _calendar_observation(item: Mapping[str, Any]) -> Observation:
    event_id = str(item.get("id", "unknown"))
    summary = str(item.get("summary", "Calendar event"))
    observed_at = str(item.get("start", "1970-01-01T00:00:00Z"))
    return Observation(
        source_id=f"calendar:{event_id}",
        source_connector="google",
        source_locator=f"calendar:{event_id}",
        title=summary,
        tags=("delivery",),
        period=None,
        observed_at=observed_at,
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
        observed_at="1970-01-01T00:00:00Z",
        excerpt=name,
        provenance=("google",),
    )
