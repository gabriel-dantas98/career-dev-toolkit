from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

from careeros.connectors.base import (
    MAX_GITHUB_RESULTS,
    CollectRequest,
    ConnectorRequestInvalid,
    Observation,
)


class GitHubConnector:
    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self._runner = runner or subprocess.run

    def collect(self, request: CollectRequest) -> tuple[Observation, ...]:
        if request.source != "github":
            raise ConnectorRequestInvalid("GitHubConnector requires source='github'")

        endpoint = request.endpoint
        if not endpoint or not endpoint.strip():
            raise ConnectorRequestInvalid("GitHub endpoint is required")

        fields = request.fields
        if not fields or not fields.strip():
            raise ConnectorRequestInvalid("GitHub fields must be explicit")

        max_results = request.max_results
        if max_results is None:
            raise ConnectorRequestInvalid("GitHub max_results is required")
        if max_results < 1 or max_results > MAX_GITHUB_RESULTS:
            raise ConnectorRequestInvalid(
                f"GitHub max_results must be between 1 and {MAX_GITHUB_RESULTS}"
            )

        jq_filter = _jq_projection(fields)
        argv = [
            "gh",
            "api",
            endpoint.strip(),
            "-f",
            f"per_page={max_results}",
            "--jq",
            jq_filter,
        ]

        completed = self._runner(
            argv,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        payload = json.loads(completed.stdout or "[]")
        items = payload if isinstance(payload, list) else [payload]

        observations: list[Observation] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            observations.append(_observation_from_github(item))

        return tuple(observations)


def _jq_projection(fields: str) -> str:
    parts = [part.strip() for part in fields.split(",") if part.strip()]
    projection = ", ".join(f"{part}: .{part}" for part in parts)
    return f".[] | {{{projection}}}"


def _observation_from_github(item: dict[str, Any]) -> Observation:
    number = item.get("number")
    html_url = str(item.get("html_url", ""))
    title = str(item.get("title", "Untitled GitHub item"))
    state = str(item.get("state", ""))
    source_id = f"github:pull/{number}" if number is not None else f"github:{html_url}"

    tags = ("impact",) if title.startswith("[Impact]") else ("delivery",)

    return Observation(
        source_id=source_id,
        source_connector="github",
        source_locator=html_url or source_id,
        title=title,
        tags=tags,
        period=None,
        observed_at="1970-01-01T00:00:00Z",
        excerpt=title,
        pr_locator=html_url or None,
        pr_status=state or None,
        narrative_status=state or None,
        provenance=("github",),
    )
