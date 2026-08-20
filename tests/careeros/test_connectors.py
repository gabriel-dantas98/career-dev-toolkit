from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from careeros.consent import ConsentDenied, ConsentService
from careeros.connectors.base import (
    CollectRequest,
    ConnectorRequestInvalid,
    PrivacyBlocked,
)
from careeros.connectors import base as connector_base
from careeros.connectors.github import GITHUB_CONNECTOR_RESOURCE, GitHubConnector
from careeros.connectors.google import (
    GOOGLE_ALLOWED_ACTIONS,
    GoogleConnector,
)
from careeros.connectors.thread import ThreadConnector
from careeros import deploy as deploy_module
from careeros import google_client, projections

GATEWAY_HANDLER = (
    Path(__file__).resolve().parents[1] / "apps-script" / "handler_cli.mjs"
)
GATEWAY_SOURCE = Path(__file__).resolve().parents[2] / "apps-script" / "Code.gs"


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


def allow_github(consent: ConsentService) -> ConsentService:
    consent.grant("connector", GITHUB_CONNECTOR_RESOURCE, ("read",))
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
                                "id": f"msg-synthetic-{index}",
                                "subject": f"Recognition note {index}",
                                "snippet": f"Synthetic kudos excerpt {index}",
                                "date": "2026-01-10T00:00:00Z",
                            }
                            for index in range(1, 6)
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


@pytest.fixture
def github_consent(store) -> ConsentService:
    return allow_github(ConsentService(store))


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


def test_google_connector_rejects_invalid_time_window(
    fake_gateway,
    google_consent,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)
    with pytest.raises(ConnectorRequestInvalid, match="ISO-8601"):
        connector.collect(
            CollectRequest(
                source="gmail",
                action="gmail.search",
                query="recognition",
                time_window=("not-a-date", "2026-01-31T00:00:00Z"),
                max_results=10,
            )
        )


def test_google_connector_rejects_inverted_time_window(
    fake_gateway,
    google_consent,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)
    with pytest.raises(ConnectorRequestInvalid, match="before end"):
        connector.collect(
            CollectRequest(
                source="gmail",
                action="gmail.search",
                query="recognition",
                time_window=("2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                max_results=10,
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
                time_window=("2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z"),
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
                time_window=("2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z"),
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
            time_window=("2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z"),
            max_results=2,
        )
    )
    assert len(observations) == 2
    assert observations[0].source_connector == "google"
    assert fake_gateway.calls[0]["action"] == "gmail.search"  # type: ignore[attr-defined]
    assert fake_gateway.calls[0]["maxResults"] == 2  # type: ignore[attr-defined]


def test_google_connector_extracts_kudos_sender_name_and_iso_month(
    google_consent,
) -> None:
    class KudosGateway:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "ok": True,
                "data": {
                    "messages": [
                        {
                            "id": "msg-kudos-synthetic",
                            "subject": "Synthetic recognition",
                            "from": (
                                "Synthetic Sender "
                                "<synthetic.sender@example.invalid>"
                            ),
                            "snippet": "Synthetic kudos evidence",
                            "date": "2026-03-17T12:30:00Z",
                        }
                    ]
                },
            }

    observations = GoogleConnector(
        KudosGateway(),
        consent=google_consent,
    ).collect(
        CollectRequest(
            source="gmail",
            action="gmail.search",
            query="recognition",
            time_window=("2026-03-01T00:00:00Z", "2026-04-01T00:00:00Z"),
            max_results=1,
        )
    )

    assert len(observations) == 1
    assert observations[0].record_type == "kudos"
    assert observations[0].tags == ("kudos",)
    assert observations[0].name == "Synthetic Sender"
    assert observations[0].month == "2026-03"


def test_google_connector_does_not_invent_kudos_name_or_month(
    google_consent,
) -> None:
    class UnresolvedGateway:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "ok": True,
                "data": {
                    "messages": [
                        {
                            "id": "msg-kudos-unresolved",
                            "subject": "Synthetic recognition",
                            "from": "synthetic.sender@example.invalid",
                            "snippet": "Synthetic unresolved kudos evidence",
                            "date": "not-an-iso-date",
                        }
                    ]
                },
            }

    observation = GoogleConnector(
        UnresolvedGateway(),
        consent=google_consent,
    ).collect(
        CollectRequest(
            source="gmail",
            action="gmail.search",
            query="recognition",
            time_window=("2026-03-01T00:00:00Z", "2026-04-01T00:00:00Z"),
            max_results=1,
        )
    )[0]

    assert observation.name is None
    assert observation.month is None


def test_google_connector_caps_gmail_snippet_to_bounded_excerpt(
    fake_gateway,
    google_consent,
) -> None:
    class LongSnippetGateway:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            return {
                "ok": True,
                "data": {
                    "messages": [
                        {
                            "id": "msg-long",
                            "subject": "Long snippet",
                            "snippet": "x" * 10_000,
                            "date": "2026-01-10T00:00:00Z",
                        }
                    ]
                },
            }

    connector = GoogleConnector(LongSnippetGateway(), consent=google_consent)
    observations = connector.collect(
        CollectRequest(
            source="gmail",
            action="gmail.search",
            query="recognition",
            time_window=("2026-01-01T00:00:00Z", "2026-01-31T00:00:00Z"),
            max_results=1,
        )
    )
    assert len(observations) == 1
    assert len(observations[0].excerpt) == 8_000


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


def test_google_sheets_read_payload_runs_through_real_gateway_handler(
    google_consent,
) -> None:
    calls: list[dict[str, object]] = []

    class RealHandlerGateway:
        def invoke(self, payload: dict[str, object]) -> dict[str, object]:
            calls.append(payload)
            completed = subprocess.run(
                ["node", str(GATEWAY_HANDLER)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(completed.stdout)

    connector = GoogleConnector(RealHandlerGateway(), consent=google_consent)
    observations = connector.collect(
        CollectRequest(
            source="sheets",
            action="sheets.read",
            resource_id="sheet:synthetic-sheet-id",
            sheet_name="Brag Sheet",
            range="A1:B1",
        )
    )

    assert calls == [
        {
            "action": "sheets.read",
            "spreadsheetId": "synthetic-sheet-id",
            "sheetName": "Brag Sheet",
            "range": "A1:B1",
        }
    ]
    assert len(observations) == 1
    assert observations[0].source_id == "sheet:synthetic-sheet-id"
    assert "Synthetic" in observations[0].excerpt


@pytest.mark.parametrize(
    ("sheet_name", "range_value", "message"),
    [
        (None, "A1:B1", "sheet_name"),
        ("Brag Sheet", None, "range"),
        ("Brag Sheet", "A:A", "range"),
        ("Brag Sheet", "A1:Z1000", "range"),
    ],
)
def test_google_sheets_read_requires_finite_sheet_and_range(
    fake_gateway,
    google_consent,
    sheet_name: str | None,
    range_value: str | None,
    message: str,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)

    with pytest.raises(ConnectorRequestInvalid, match=message):
        connector.collect(
            CollectRequest(
                source="sheets",
                action="sheets.read",
                resource_id="sheet:synthetic-sheet-id",
                sheet_name=sheet_name,
                range=range_value,
            )
        )


def test_google_docs_read_normalizes_canonical_id_to_bare_payload(
    fake_gateway,
    google_consent,
) -> None:
    connector = GoogleConnector(fake_gateway, consent=google_consent)

    connector.collect(
        CollectRequest(
            source="docs",
            action="docs.read",
            resource_id="doc:synthetic-document-id",
        )
    )

    assert fake_gateway.calls[-1] == {  # type: ignore[attr-defined]
        "action": "docs.read",
        "documentId": "synthetic-document-id",
    }


def test_python_and_apps_script_gateway_bounds_stay_in_parity() -> None:
    source = GATEWAY_SOURCE.read_text()

    def numeric_constant(name: str) -> int:
        match = re.search(rf"var {name} = (\d+);", source)
        assert match is not None
        return int(match.group(1))

    assert numeric_constant("MAX_RESULTS") == connector_base.MAX_GOOGLE_RESULTS
    assert numeric_constant("MAX_DOC_CHARS") == connector_base.MAX_THREAD_EXCERPT
    assert (
        numeric_constant("MAX_SHEET_READ_CELLS")
        == connector_base.MAX_SHEET_READ_CELLS
    )
    assert numeric_constant("MAX_SHEET_ROWS") == connector_base.MAX_SHEET_ROWS
    assert numeric_constant("MAX_SHEET_COLUMNS") == connector_base.MAX_SHEET_COLUMNS
    assert numeric_constant("MAX_BRAGSHEET_ROWS") == projections.MAX_BRAGSHEET_ROWS
    assert (
        numeric_constant("MAX_BRAGSHEET_COLUMNS")
        == projections.MAX_BRAGSHEET_COLUMNS
    )
    assert numeric_constant("MAX_HOMEPAGE_ROWS") == getattr(
        deploy_module,
        "MAX_HOMEPAGE_ROWS",
        None,
    )
    assert numeric_constant("MAX_HOMEPAGE_COLUMNS") == getattr(
        deploy_module,
        "MAX_HOMEPAGE_COLUMNS",
        None,
    )
    assert "var MAX_REQUEST_BYTES = 256 * 1024;" in source
    assert google_client.MAX_REQUEST_BYTES == 256 * 1024
    assert "sheets.writeHomepage" in google_client.MUTATING_ACTIONS


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
    assert "1970-01-01" not in observations[0].observed_at


def test_github_connector_invokes_gh_as_argv(store, github_consent) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["shell"] = kwargs.get("shell")
        captured["call_count"] = captured.get("call_count", 0) + 1
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                '[{"number":1,"title":"[Impact] PR title","state":"merged",'
                '"html_url":"https://github.test/org/repo/pull/1",'
                '"updated_at":"2026-01-12T00:00:00Z"}]'
            ),
            stderr="",
        )

    connector = GitHubConnector(consent=github_consent, runner=fake_run)
    observations = connector.collect(
        CollectRequest(
            source="github",
            endpoint="repos/synthetic-org/synthetic-repo/pulls",
            fields="number,title,state,html_url,updated_at",
            max_results=10,
        )
    )
    assert captured["shell"] is not True
    assert captured["argv"][0] == "gh"
    assert captured["argv"][1] == "api"
    assert "--jq" in captured["argv"] or "-f" in " ".join(captured["argv"])
    assert len(observations) == 1
    assert observations[0].source_connector == "github"
    assert observations[0].observed_at == "2026-01-12T00:00:00Z"


def test_github_connector_checks_consent_before_runner(store) -> None:
    call_count = 0

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")

    connector = GitHubConnector(consent=ConsentService(store), runner=fake_run)
    with pytest.raises(ConsentDenied):
        connector.collect(
            CollectRequest(
                source="github",
                endpoint="repos/synthetic-org/synthetic-repo/pulls",
                fields="number,title",
                max_results=10,
            )
        )
    assert call_count == 0


def test_github_connector_revocation_blocks_with_zero_runner_calls(store, github_consent) -> None:
    call_count = 0

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal call_count
        call_count += 1
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")

    github_consent.revoke("connector", GITHUB_CONNECTOR_RESOURCE)
    connector = GitHubConnector(consent=github_consent, runner=fake_run)
    with pytest.raises(ConsentDenied):
        connector.collect(
            CollectRequest(
                source="github",
                endpoint="repos/synthetic-org/synthetic-repo/pulls",
                fields="number,title",
                max_results=10,
            )
        )
    assert call_count == 0


def test_github_connector_truncates_over_returned_results(store, github_consent) -> None:
    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        payload = [
            {
                "number": index,
                "title": f"PR {index}",
                "state": "open",
                "html_url": f"https://github.test/org/repo/pull/{index}",
            }
            for index in range(1, 6)
        ]
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(payload),
            stderr="",
        )

    connector = GitHubConnector(consent=github_consent, runner=fake_run)
    observations = connector.collect(
        CollectRequest(
            source="github",
            endpoint="repos/synthetic-org/synthetic-repo/pulls",
            fields="number,title,state,html_url",
            max_results=2,
        )
    )
    assert len(observations) == 2


def test_github_connector_rejects_unbounded_request(github_consent) -> None:
    connector = GitHubConnector(consent=github_consent)
    with pytest.raises(ConnectorRequestInvalid, match="max_results"):
        connector.collect(
            CollectRequest(
                source="github",
                endpoint="repos/synthetic-org/synthetic-repo/pulls",
                fields="number,title",
            )
        )


def test_github_connector_requires_explicit_fields(github_consent) -> None:
    connector = GitHubConnector(consent=github_consent)
    with pytest.raises(ConnectorRequestInvalid, match="fields"):
        connector.collect(
            CollectRequest(
                source="github",
                endpoint="repos/synthetic-org/synthetic-repo/pulls",
                max_results=10,
            )
        )
