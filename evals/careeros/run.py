from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import count
from pathlib import Path

from careeros.consent import ConsentDenied, ConsentService
from careeros.connectors.base import CollectRequest, Observation
from careeros.connectors.github import GitHubConnector
from careeros.connectors.google import GoogleConnector
from careeros.connectors.thread import ThreadConnector
from careeros.crypto import KEYRING_SERVICE, key_account_for
from careeros.google_client import BrowserModeClient
from careeros.harvest import HarvestRequest, HarvestService
from careeros.jobs import JobRunner
from careeros.outputs import build_promo_packet, build_timeline
from careeros.privacy import scan_sensitive
from careeros.record_store import EncryptedRecordStore
from careeros.store import EncryptedStore, StoreConfig, open_encrypted_store
from careeros.sync import EncryptedSyncRunStore, SyncService
from evals.careeros.fake_gateway import FakeGateway, UrlLibTransport

STAGE_NAMES = (
    "harvest",
    "privacy",
    "validation",
    "encryptedStore",
    "safeWrite",
    "readBack",
    "outputs",
    "backgroundConsent",
)
SECRET_CANARY = "SYNTHETIC_SECRET_CANARY"
FIXED_GATEWAY_TIME = 1_787_198_400
DESTINATION_ID = "sheet:synthetic-eval-sheet"
JOB_ID = "synthetic-eval"

EXPECTED_RULE_IDS: dict[str, list[str]] = {
    "harvest": [
        "harvest.overlap.merged",
        "harvest.persistence.succeeded",
    ],
    "privacy": ["privacy.blocked"],
    "validation": ["impact.evidence.missing"],
    "encryptedStore": [
        "store.sqlcipher.active",
        "store.plaintext.rejected",
        "store.reopen.succeeded",
    ],
    "safeWrite": ["sync.raw.required", "sync.synced"],
    "readBack": ["sync.read_back.exact"],
    "outputs": ["outputs.period.resolved"],
    "backgroundConsent": ["consent.background.required"],
}

EMPTY_COUNTS = {
    "sourceObservations": 0,
    "mergedRecords": 0,
    "persistedRecords": 0,
    "rejectedRecords": 0,
    "validationIssues": 0,
    "gatewayRequests": 0,
    "gatewayWrites": 0,
    "gatewayReadBacks": 0,
    "timelineCards": 0,
    "promotionWorkCards": 0,
}


class EvalFailure(RuntimeError):
    def __init__(self, stage: str) -> None:
        super().__init__(f"Required eval stage failed: {stage}")
        self.stage = stage


class SyntheticKeyring:
    def __init__(self) -> None:
        self._passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self._passwords.get((service, account))

    def set_password(self, service: str, account: str, password: str) -> None:
        self._passwords[(service, account)] = password

    def delete_password(self, service: str, account: str) -> None:
        self._passwords.pop((service, account), None)


def run_eval(output_root: Path) -> dict[str, object]:
    root = output_root.resolve()
    work_directory = root / ".eval-results" / "careeros"
    work_directory.mkdir(parents=True, exist_ok=True)
    database_path = work_directory / "synthetic-eval.db"
    database_path.unlink(missing_ok=True)

    stages = {stage: "failed" for stage in STAGE_NAMES}
    counts = dict(EMPTY_COUNTS)
    rule_ids = {stage: [] for stage in STAGE_NAMES}
    keyring = SyntheticKeyring()
    keyring.set_password(
        KEYRING_SERVICE,
        key_account_for(database_path),
        "ab" * 32,
    )

    store: EncryptedStore | None = None
    active_stage = "encryptedStore"
    try:
        store = open_encrypted_store(StoreConfig(database_path), keyring)
        cipher_row = store.connection().execute("PRAGMA cipher_version").fetchone()
        _require(
            active_stage,
            cipher_row is not None and bool(str(cipher_row[0]).strip()),
        )

        active_stage = "privacy"
        private_input = f"sk-{SECRET_CANARY}_123456"
        findings = scan_sensitive(private_input)
        _require(
            active_stage,
            len(findings) == 1 and findings[0].category == "api-key",
        )
        rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
        stages[active_stage] = "passed"

        repository = EncryptedRecordStore.from_encrypted_store(store)
        active_stage = "validation"
        invalid_result = HarvestService(repository).run(
            HarvestRequest(observations=(_invalid_impact_observation(),))
        )
        invalid_rule_ids = sorted({issue.rule_id for issue in invalid_result.issues})
        counts["rejectedRecords"] = 1 if not invalid_result.persisted else 0
        counts["validationIssues"] = len(invalid_result.issues)
        _require(
            active_stage,
            invalid_rule_ids == ["impact.evidence.missing"]
            and not invalid_result.persisted
            and repository.count_records() == 0,
        )
        rule_ids[active_stage] = invalid_rule_ids
        stages[active_stage] = "passed"

        consent = ConsentService(store)
        consent.grant("connector", "connector:github", ("read",))
        consent.grant("connector", "connector:google", ("calendar.search",))
        consent.grant(
            "destination",
            DESTINATION_ID,
            ("write:bragsheet",),
        )

        with FakeGateway() as gateway_fixture:
            gateway_client = _gateway_client(gateway_fixture)
            observations = _collect_observations(
                consent=consent,
                gateway_client=gateway_client,
            )
            counts["sourceObservations"] = len(observations)

            active_stage = "harvest"
            harvest_result = HarvestService(repository).run(
                HarvestRequest(
                    observations=tuple(
                        observation.as_dict() for observation in observations
                    )
                )
            )
            counts["mergedRecords"] = len(harvest_result.records)
            counts["persistedRecords"] = repository.count_records()
            _require(
                active_stage,
                harvest_result.persisted
                and not harvest_result.issues
                and len(harvest_result.records) == 1
                and repository.count_records() == 1
                and set(
                    harvest_result.records[0].metadata.provenance
                )
                == {"thread", "github", "google"},
            )
            rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
            stages[active_stage] = "passed"

            store.close()
            store = None
            plaintext_rejected = _plaintext_sqlite_rejected(database_path)
            store = open_encrypted_store(StoreConfig(database_path), keyring)
            repository = EncryptedRecordStore.from_encrypted_store(store)
            records = repository.load_records()

            active_stage = "encryptedStore"
            _require(
                active_stage,
                plaintext_rejected
                and len(records) == 1
                and records[0].period == "03/04/2026",
            )
            rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
            stages[active_stage] = "passed"

            consent = ConsentService(store)
            sync = SyncService(
                consent=consent,
                run_store=EncryptedSyncRunStore(store.connection()),
            )
            projection = sync.preview(
                records,
                destination_id=DESTINATION_ID,
                sheet_name="Brag Sheet",
                start_row=2,
            )

            active_stage = "safeWrite"
            _require(
                active_stage,
                projection.row_count == 1
                and projection.column_count == 12
                and projection.values[0][1] == "'03/04/2026",
            )
            sync_result = sync.write_and_verify(projection, gateway_client)
            _require(active_stage, sync_result.status == "synced")
            rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
            stages[active_stage] = "passed"

            active_stage = "readBack"
            actions = gateway_fixture.actions
            counts["gatewayRequests"] = len(actions)
            counts["gatewayWrites"] = actions.count("sheets.writeBragsheet")
            counts["gatewayReadBacks"] = actions.count("sheets.readBack")
            _require(
                active_stage,
                actions
                == (
                    "calendar.search",
                    "sheets.writeBragsheet",
                    "sheets.readBack",
                ),
            )
            rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
            stages[active_stage] = "passed"

            active_stage = "outputs"
            timeline = build_timeline(records)
            promotion = build_promo_packet(records)
            counts["timelineCards"] = len(timeline.cards)
            counts["promotionWorkCards"] = len(promotion.work_cards)
            _require(
                active_stage,
                len(timeline.cards) == 1
                and not timeline.unresolved_records
                and timeline.cards[0].sort_start == "2026-04-03"
                and len(promotion.work_cards) == 1
                and promotion.unresolved_work_summary.count == 0,
            )
            rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
            stages[active_stage] = "passed"

            active_stage = "backgroundConsent"
            requests_before_background = len(gateway_fixture.actions)
            job_runner = JobRunner(
                consent=consent,
                sync=sync,
                gateway=gateway_client,
                jobs={JOB_ID: projection},
                lock_directory=work_directory / "locks",
                idempotency_key_factory=lambda: "synthetic-eval-idempotency-key",
            )
            background_denied = False
            try:
                job_runner.run(JOB_ID)
            except ConsentDenied:
                background_denied = True
            _require(
                active_stage,
                background_denied
                and len(gateway_fixture.actions) == requests_before_background,
            )
            rule_ids[active_stage] = list(EXPECTED_RULE_IDS[active_stage])
            stages[active_stage] = "passed"
    except EvalFailure:
        rule_ids[active_stage] = [f"eval.{active_stage}.failed"]
    except Exception:
        rule_ids[active_stage] = [f"eval.{active_stage}.failed"]
    finally:
        if store is not None:
            store.close()

    report: dict[str, object] = {
        "schemaVersion": 1,
        "status": (
            "passed"
            if all(status == "passed" for status in stages.values())
            else "failed"
        ),
        "stages": stages,
        "counts": counts,
        "ruleIds": rule_ids,
    }
    _write_sanitized_report(report, work_directory / "report.json")
    return report


def _collect_observations(
    *,
    consent: ConsentService,
    gateway_client: BrowserModeClient,
) -> tuple[Observation, ...]:
    thread = ThreadConnector().collect(
        CollectRequest(
            source="thread",
            thread_id="synthetic-overlap-901",
            excerpt=(
                "Title: [Impact] Synthetic bounded sync\n"
                "Jira: SYN-901\n"
                "PR: https://github.test/synthetic/repo/pull/901\n"
                "Result: Synthetic output was verified."
            ),
        )
    )[0]
    github = GitHubConnector(
        consent=consent,
        runner=_synthetic_github_runner,
    ).collect(
        CollectRequest(
            source="github",
            endpoint="repos/synthetic/repo/pulls",
            fields="number,html_url,title,state,updated_at",
            max_results=1,
        )
    )[0]
    google = GoogleConnector(
        gateway_client,
        consent=consent,
    ).collect(
        CollectRequest(
            source="google",
            action="calendar.search",
            query="synthetic bounded sync",
            time_window=(
                "2026-04-01T00:00:00+00:00",
                "2026-04-30T23:59:59+00:00",
            ),
            max_results=1,
        )
    )[0]
    overlapping_google = replace(
        google,
        tags=("impact",),
        period="03/04/2026",
        jira_key="SYN-901",
        pr_locator="https://github.test/synthetic/repo/pull/901",
        result="Synthetic output was verified.",
        pr_status="merged",
        narrative_status="merged",
        confidence="complete",
    )
    return thread, github, overlapping_google


def _synthetic_github_runner(
    argv: Sequence[str],
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    del kwargs
    payload = [
        {
            "number": 901,
            "html_url": "https://github.test/synthetic/repo/pull/901",
            "title": "[Impact] Synthetic bounded sync",
            "state": "merged",
            "updated_at": "2026-04-03T10:00:00+00:00",
        }
    ]
    return subprocess.CompletedProcess(
        argv,
        0,
        stdout=json.dumps(payload),
        stderr="",
    )


def _invalid_impact_observation() -> Mapping[str, object]:
    return {
        "source_id": "thread:synthetic-invalid-impact",
        "source_connector": "thread",
        "source_locator": "thread:synthetic-invalid-impact",
        "title": "[Impact] Unsupported synthetic claim",
        "tags": ("impact",),
        "period": "Q2 2026",
        "observed_at": "2026-04-02T00:00:00+00:00",
        "excerpt": "Synthetic unsupported impact fixture.",
        "provenance": (),
        "result": "Synthetic unsupported impact result.",
        "confidence": "partial",
    }


def _gateway_client(fixture: FakeGateway) -> BrowserModeClient:
    request_ids = count(1)
    nonces = count(1)
    return BrowserModeClient(
        fixture.url,
        transport=UrlLibTransport(),
        clock=lambda: FIXED_GATEWAY_TIME,
        request_id_factory=lambda: f"eval-request-{next(request_ids):04d}",
        nonce_factory=lambda: f"eval-nonce-{next(nonces):04d}",
        sleep=lambda _delay: None,
        max_attempts=1,
        timeout_seconds=5,
    )


def _plaintext_sqlite_rejected(database_path: Path) -> bool:
    connection = sqlite3.connect(
        f"file:{database_path}?mode=ro",
        uri=True,
    )
    try:
        connection.execute("SELECT name FROM sqlite_master").fetchall()
    except sqlite3.DatabaseError:
        return True
    finally:
        connection.close()
    return False


def _require(stage: str, condition: bool) -> None:
    if not condition:
        raise EvalFailure(stage)


def _write_sanitized_report(report: Mapping[str, object], path: Path) -> None:
    serialized = json.dumps(
        dict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if SECRET_CANARY in serialized:
        raise RuntimeError("Eval report sanitization failed")
    path.write_text(f"{serialized}\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="careeros-eval")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    arguments = parser.parse_args(argv)
    report = run_eval(arguments.output_root)
    json.dump(report, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
