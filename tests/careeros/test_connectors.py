from __future__ import annotations

import subprocess
from typing import Any

import pytest

from careeros.consent import ConsentDenied, ConsentService
from careeros.connectors.base import (
    CollectRequest,
    ConnectorRequestInvalid,
    PrivacyBlocked,
)
from careeros.connectors.github import GitHubConnector
from careeros.connectors.google import (
    GOOGLE_ALLOWED_ACTIONS,
    GoogleConnector,
)
from careeros.connectors.thread import ThreadConnector


def allow_google(consent: ConsentService) -> ConsentService:
    consent.grant(
        "connector",
        "connector:google",
        (
            "calendar.search",
            "gmail.search",
            "drive.search",
            "docs.read",
            "sheets.read",
        ),
    )
    return consent


@pytest.fixture
def fake_gateway() -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class Gateway:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            calls.append(payload)
            action = payload["action"]
            if action == "gmail.search":
                return {
                    "ok": True,
                    "data": {
                        "messages": [
                            {
                                "id": "msg-synthetic-1",
                                "subject": "Recognition note",
                                "snippet": "Synthetic kudos excerpt",
                                "date": "2026-01-10T00:00:00Z",
                            }
                        ]
                    },
                }
            if action == "calendar.search":
                return {"ok": True, "data": {"events": []}}
            if action == "drive.search":
                return {"ok": True, "data": {"files": []}}
            if action == "docs.read":
                return {"ok": True, "data": {"content": "Synthetic doc excerpt"}}
            if action == "sheets.read":
                return {"ok": True, "data": {"values": [["Synthetic", "sheet"]]}}
            return {"ok": False, "errors": [{"message": "unknown action"}]}

    gateway = Gateway()
    gateway.calls = calls  # type: ignore[attr-defined]
    return gateway  # type: ignore[return-value]


@pytest.fixture
def google_consent(store) -> ConsentService:
    return allow_google(ConsentService(store))


def test_google_connector_rejects_unbounded_mail_query(
    fake_gateway,
    google_consent,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)
    with pytest.raises(ConnectorRequestInvalid, match="time window"):
        connector.collect(
            CollectRequest(
                source="gmail",
                action="gmail.search",
                query="recognition",
            )
        )


def test_google_connector_rejects_non_allowlisted_action(
    fake_gateway,
    google_consent,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)
    with pytest.raises(ConnectorRequestInvalid, match="allowlist"):
        connector.collect(
            CollectRequest(
                source="gmail",
                action="gmail.send",
                query="recognition",
                time_window=("2026-01-01", "2026-01-31"),
                max_results=10,
            )
        )


def test_google_connector_checks_consent_before_gateway(
    fake_gateway,
    store,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=ConsentService(store))
    with pytest.raises(ConsentDenied):
        connector.collect(
            CollectRequest(
                source="gmail",
                action="gmail.search",
                query="recognition",
                time_window=("2026-01-01", "2026-01-31"),
                max_results=10,
            )
        )
    assert fake_gateway.calls == []  # type: ignore[attr-defined]


def test_google_connector_bounded_search_invokes_gateway(
    fake_gateway,
    google_consent,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)
    observations = connector.collect(
        CollectRequest(
            source="gmail",
            action="gmail.search",
            query="recognition",
            time_window=("2026-01-01", "2026-01-31"),
            max_results=5,
        )
    )
    assert len(observations) == 1
    assert observations[0].source_connector == "google"
    assert fake_gateway.calls[0]["action"] == "gmail.search"  # type: ignore[attr-defined]
    assert fake_gateway.calls[0]["maxResults"] == 5  # type: ignore[attr-defined]


def test_google_allowed_actions_are_fixed() -> None:
    assert GOOGLE_ALLOWED_ACTIONS == frozenset(
        {
            "calendar.search",
            "gmail.search",
            "drive.search",
            "docs.read",
            "sheets.read",
        }
    )


def test_thread_connector_rejects_sensitive_excerpt() -> None:
    connector = ThreadConnector()
    with pytest.raises(PrivacyBlocked, match="privacy"):
        connector.collect(
            CollectRequest(
                source="thread",
                excerpt="Contact me at synthetic.user@example.test for details",
                thread_id="thread-synthetic-1",
            )
        )


def test_thread_connector_rejects_unbounded_excerpt() -> None:
    connector = ThreadConnector()
    with pytest.raises(ConnectorRequestInvalid, match="excerpt"):
        connector.collect(
            CollectRequest(
                source="thread",
                excerpt="x" * 10_000,
                thread_id="thread-synthetic-1",
            )
        )


def test_thread_connector_parses_bounded_excerpt() -> None:
    connector = ThreadConnector()
    observations = connector.collect(
        CollectRequest(
            source="thread",
            excerpt=(
                "title: [Impact] Thread delivery\n"
                "jira: SYN-THREAD-1\n"
                "pr: https://github.test/org/repo/pull/42\n"
                "result: Synthetic thread result"
            ),
            thread_id="thread-synthetic-1",
        )
    )
    assert len(observations) == 1
    assert observations[0].source_id == "thread:thread-synthetic-1"
    assert observations[0].jira_key == "SYN-THREAD-1"
    assert observations[0].provenance == ("thread",)


def test_github_connector_invokes_gh_as_argv(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["shell"] = kwargs.get("shell")
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout='[{"number":1,"title":"[Impact] PR title","state":"merged","html_url":"https://github.test/org/repo/pull/1"}]',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    connector = GitHubConnector()
    observations = connector.collect(
        CollectRequest(
            source="github",
            endpoint="repos/synthetic-org/synthetic-repo/pulls",
            fields="number,title,state,html_url",
            max_results=10,
        )
    )
    assert captured["shell"] is not True
    assert captured["argv"][0] == "gh"
    assert captured["argv"][1] == "api"
    assert "--jq" in captured["argv"] or "-f" in " ".join(captured["argv"])
    assert len(observations) == 1
    assert observations[0].source_connector == "github"


def test_github_connector_rejects_unbounded_request() -> None:
    connector = GitHubConnector()
    with pytest.raises(ConnectorRequestInvalid, match="max_results"):
        connector.collect(
            CollectRequest(
                source="github",
                endpoint="repos/synthetic-org/synthetic-repo/pulls",
                fields="number,title",
            )
        )


def test_github_connector_requires_explicit_fields() -> None:
    connector = GitHubConnector()
    with pytest.raises(ConnectorRequestInvalid, match="fields"):
        connector.collect(
            CollectRequest(
                source="github",
                endpoint="repos/synthetic-org/synthetic-repo/pulls",
                max_results=10,
            )
        )
