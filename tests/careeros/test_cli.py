import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from careeros.cli import (
    handle_sync_careeros_background,
    handle_write_bragsheet_safe,
)
from careeros.consent import ConsentDenied, ConsentService
from careeros.models import DeliveryRecord, EvidenceRef
from careeros.sync import EncryptedSyncRunStore, SyncService

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def run_cli() -> Callable[..., subprocess.CompletedProcess[str]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    def _run_cli(
        *args: str,
        stdin: str | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "careeros", *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            env={**env, **dict(extra_env or {})},
        )

    return _run_cli


def test_version_is_machine_readable(run_cli: Callable[..., subprocess.CompletedProcess[str]]) -> None:
    result = run_cli("version", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "ok": True,
        "command": "version",
        "data": {"schemaVersion": 1, "version": "0.2.0"},
        "errors": [],
    }


def test_unknown_command_returns_structured_error(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    result = run_cli("unknown", "--json")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "ok": False,
        "command": "unknown",
        "data": {},
        "errors": [{"code": "unknown_command", "message": "Unknown command: unknown"}],
    }


PORTABLE_SKILL_COMMANDS = (
    "capture-delivery",
    "harvest-retrospective",
    "validate-bragsheet-integrity",
    "write-bragsheet-safe",
    "deploy-careeros-timeline",
    "build-promo-packet",
    "sync-careeros",
)


@pytest.mark.parametrize("command", PORTABLE_SKILL_COMMANDS)
def test_portable_skill_command_is_registered(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
    command: str,
) -> None:
    payload = (
        {"records": []}
        if command in {"validate-bragsheet-integrity", "build-promo-packet"}
        else {}
    )
    result = run_cli(command, "--json", stdin=json.dumps(payload))
    envelope = json.loads(result.stdout)

    assert envelope["command"] == command
    assert all(error["code"] != "unknown_command" for error in envelope["errors"])


@pytest.mark.parametrize("command", ("capture-delivery", "harvest-retrospective"))
def test_private_input_blocks_before_configuration_and_never_echoes_secret(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
    command: str,
) -> None:
    synthetic_secret = "sk-SYNTHETIC_CANARY_123456"
    result = run_cli(
        command,
        "--json",
        stdin=json.dumps({"excerpt": f"Title: Delivery\nToken: {synthetic_secret}"}),
    )
    envelope = json.loads(result.stdout)

    assert result.returncode == 1
    assert envelope["ok"] is False
    assert envelope["errors"][0]["code"] == "privacy.blocked"
    assert envelope["data"]["findings"][0]["category"] == "api-key"
    assert synthetic_secret not in result.stdout
    assert synthetic_secret not in result.stderr


def test_capture_returns_fixed_draft_shape_with_explicit_star_gaps(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    result = run_cli(
        "capture-delivery",
        "--json",
        stdin=json.dumps({"excerpt": "Title: [Delivery] Synthetic CLI wiring"}),
    )
    envelope = json.loads(result.stdout)

    assert result.returncode == 0
    assert envelope["ok"] is True
    draft = envelope["data"]["drafts"][0]
    assert set(draft) == {
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
    }
    assert all(
        draft[field].startswith("Evidence gap:")
        for field in ("situation", "task", "action", "result")
    )


def test_validate_returns_rule_ids_and_fails_on_error_severity(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    record = _record_mapping(
        title="Missing canonical prefix",
        tags=["impact"],
        confidence="partial",
    )
    result = run_cli(
        "validate-bragsheet-integrity",
        "--json",
        stdin=json.dumps({"records": [record]}),
    )
    envelope = json.loads(result.stdout)

    assert result.returncode == 1
    assert envelope["ok"] is False
    assert {
        issue["rule_id"] for issue in envelope["data"]["issues"]
    } >= {"taxonomy.prefix.required"}
    assert all(set(issue) == {"rule_id", "severity", "field"} for issue in envelope["data"]["issues"])


def test_write_readback_mismatch_is_reconciliation_required(store) -> None:
    consent = ConsentService(store)
    consent.grant(
        "destination",
        "sheet:synthetic-sheet",
        ("write:bragsheet",),
    )
    sync = SyncService(
        consent=consent,
        run_store=EncryptedSyncRunStore(store.connection()),
    )

    class MismatchingGateway:
        def invoke(self, payload: Mapping[str, object]) -> Mapping[str, object]:
            if payload["action"] == "sheets.writeBragsheet":
                return {"ok": True, "data": {}}
            return {"ok": True, "data": {"values": [["different"]]}}

    result = handle_write_bragsheet_safe(
        (_delivery_record(),),
        destination_id="sheet:synthetic-sheet",
        sheet_name="Brag Sheet",
        start_row=2,
        sync=sync,
        gateway=MismatchingGateway(),
    )

    assert result.ok is False
    assert result.data["status"] == "reconciliation_required"
    assert result.errors[0]["code"] == "sync.reconciliation_required"


def test_sync_background_revocation_blocks() -> None:
    def revoked_job(_job_id: str) -> Any:
        raise ConsentDenied("synthetic revoked grant")

    result = handle_sync_careeros_background("daily", run_job=revoked_job)

    assert result.ok is False
    assert result.command == "sync-careeros"
    assert result.errors == (
        {
            "code": "sync.consent_denied",
            "message": "Background consent is missing or revoked",
        },
    )


def _record_mapping(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "rec:synthetic-cli",
        "schema_version": 1,
        "source_connector": "thread",
        "source_locator": "thread:synthetic-cli",
        "title": "[Delivery] Synthetic CLI record",
        "period": "Q3 2026",
        "tags": ["delivery"],
        "context": "delivery",
        "confidence": "partial",
        "situation": None,
        "task": None,
        "action": "Wired synthetic command coverage.",
        "result": None,
        "evidence": [],
        "evidence_gaps": ["Evidence gap: Result not present in source."],
        "content_fingerprint": "synthetic-cli-fingerprint",
        "observed_at": "2026-08-20T00:00:00+00:00",
    }
    record.update(overrides)
    return record


def _delivery_record() -> DeliveryRecord:
    return DeliveryRecord(
        id="rec:synthetic-cli",
        schema_version=1,
        source_connector="thread",
        source_locator="thread:synthetic-cli",
        title="[Delivery] Synthetic CLI record",
        period="Q3 2026",
        tags=("delivery",),
        context="delivery",
        confidence="partial",
        situation="Synthetic command surface was incomplete.",
        task="Wire one deterministic command.",
        action="Added a synthetic command test.",
        result="Synthetic read-back is verified by the test gateway.",
        evidence=(
            EvidenceRef(
                locator="https://example.invalid/evidence/cli",
                excerpt="Synthetic evidence.",
                observed_at="2026-08-20T00:00:00+00:00",
                connector="thread",
            ),
        ),
        evidence_gaps=(),
        content_fingerprint="synthetic-cli-fingerprint",
        observed_at="2026-08-20T00:00:00+00:00",
    )
