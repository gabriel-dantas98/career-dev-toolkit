from __future__ import annotations

import re

from careeros.connectors.base import (
    MAX_THREAD_EXCERPT,
    CollectRequest,
    ConnectorRequestInvalid,
    Observation,
    PrivacyBlocked,
)
from careeros.privacy import scan_sensitive

_FIELD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("title", re.compile(r"^title:\s*(.+)$", re.IGNORECASE | re.MULTILINE)),
    ("jira", re.compile(r"^jira:\s*(\S+)$", re.IGNORECASE | re.MULTILINE)),
    ("pr", re.compile(r"^pr:\s*(\S+)$", re.IGNORECASE | re.MULTILINE)),
    ("result", re.compile(r"^result:\s*(.+)$", re.IGNORECASE | re.MULTILINE)),
)


class ThreadConnector:
    def collect(self, request: CollectRequest) -> tuple[Observation, ...]:
        if request.source != "thread":
            raise ConnectorRequestInvalid("ThreadConnector requires source='thread'")

        excerpt = request.excerpt
        if excerpt is None or not excerpt.strip():
            raise ConnectorRequestInvalid("Thread excerpt is required")

        if len(excerpt) > MAX_THREAD_EXCERPT:
            raise ConnectorRequestInvalid("Thread excerpt exceeds bounded limit")

        if scan_sensitive(excerpt):
            raise PrivacyBlocked("Thread excerpt blocked by privacy preflight")

        thread_id = request.thread_id
        if not thread_id or not thread_id.strip():
            raise ConnectorRequestInvalid("thread_id is required")

        fields = _parse_excerpt(excerpt)
        title = fields.get("title", "Untitled thread excerpt")
        tags = _infer_tags(title)

        return (
            Observation(
                source_id=f"thread:{thread_id.strip()}",
                source_connector="thread",
                source_locator=f"thread:{thread_id.strip()}",
                title=title,
                tags=tags,
                period=None,
                observed_at="1970-01-01T00:00:00Z",
                excerpt=excerpt,
                jira_key=fields.get("jira"),
                pr_locator=fields.get("pr"),
                result=fields.get("result"),
                provenance=("thread",),
            ),
        )


def _parse_excerpt(excerpt: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for name, pattern in _FIELD_PATTERNS:
        match = pattern.search(excerpt)
        if match:
            parsed[name] = match.group(1).strip()
    return parsed


def _infer_tags(title: str) -> tuple[str, ...]:
    if title.startswith("[Impact]"):
        return ("impact",)
    if title.startswith("[Community]"):
        return ("community",)
    if title.startswith("[Kudos]"):
        return ("kudos",)
    return ("delivery",)
