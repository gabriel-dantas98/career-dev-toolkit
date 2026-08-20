import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import keyring

from careeros import __version__
from careeros.consent import ConsentDenied, ConsentService
from careeros.google_client import BrowserModeClient
from careeros.jobs import InvalidJobId, JobResult, JobRunner, UnknownJob
from careeros.models import CommandResult
from careeros.projections import project_bragsheet
from careeros.record_store import EncryptedRecordStore
from careeros.store import StoreConfig, StoreUnavailable, open_encrypted_store
from careeros.sync import EncryptedSyncRunStore, SyncService

SCHEMA_VERSION = 1
DEFAULT_JOB_ID = "daily"


class JobRuntimeConfigurationError(RuntimeError):
    """Raised when local run-job configuration is incomplete."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="careeros")
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
    return parser


def handle_version() -> CommandResult:
    return CommandResult(
        ok=True,
        command="version",
        data={"schemaVersion": SCHEMA_VERSION, "version": __version__},
    )


def handle_unknown(command: str) -> CommandResult:
    return CommandResult(
        ok=False,
        command=command,
        data={},
        errors=(
            {
                "code": "unknown_command",
                "message": f"Unknown command: {command}",
            },
        ),
    )


def handle_run_job(
    job_id: str,
    *,
    run_job: Callable[[str], JobResult],
) -> CommandResult:
    try:
        result = run_job(job_id)
    except JobRuntimeConfigurationError as exc:
        return _job_error("job.configuration", str(exc))
    except (InvalidJobId, UnknownJob) as exc:
        return _job_error("job.invalid", str(exc))
    except ConsentDenied as exc:
        return _job_error("job.consent_denied", str(exc))
    except StoreUnavailable as exc:
        return _job_error("job.store_unavailable", str(exc))
    except Exception as exc:
        return _job_error(
            "job.failed",
            f"Background job failed: {type(exc).__name__}",
        )
    return CommandResult(
        ok=True,
        command="run-job",
        data={
            "jobId": result.job_id,
            "status": result.status,
            "idempotencyKey": result.idempotency_key,
        },
    )


def _job_error(code: str, message: str) -> CommandResult:
    return CommandResult(
        ok=False,
        command="run-job",
        data={},
        errors=({"code": code, "message": message},),
    )


def emit_result(result: CommandResult, *, as_json: bool) -> int:
    if as_json:
        json.dump(result.as_dict(), sys.stdout)
        sys.stdout.write("\n")
    elif result.ok:
        for key, value in result.data.items():
            sys.stdout.write(f"{key}: {value}\n")
    else:
        for error in result.errors:
            message = error.get("message", "Command failed")
            sys.stderr.write(f"{message}\n")

    return 0 if result.ok else 1


def main(
    argv: Sequence[str] | None = None,
    *,
    run_job: Callable[[str], JobResult] | None = None,
) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    as_json = "--json" in raw_argv
    parsed_argv = [arg for arg in raw_argv if arg != "--json"]

    if not parsed_argv:
        result = handle_unknown("")
        return emit_result(result, as_json=as_json)

    command = parsed_argv[0]
    if command in {"-h", "--help"}:
        build_parser().print_help()
        return 0

    if command == "version" and len(parsed_argv) == 1:
        result = handle_version()
    elif command == "run-job":
        if len(parsed_argv) != 2:
            result = _job_error(
                "job.arguments",
                "Usage: python -m careeros run-job <job-id> [--json]",
            )
        else:
            result = handle_run_job(
                parsed_argv[1],
                run_job=run_job or _run_configured_job,
            )
    else:
        result = handle_unknown(command)

    return emit_result(result, as_json=as_json)


def _run_configured_job(job_id: str) -> JobResult:
    web_app_url = _required_environment("CAREEROS_WEB_APP_URL")
    destination_id = _required_environment("CAREEROS_BRAGSHEET_ID")
    configured_job_id = os.environ.get("CAREEROS_JOB_ID", DEFAULT_JOB_ID)
    sheet_name = os.environ.get("CAREEROS_BRAGSHEET_NAME", "Brag Sheet")
    database_path = Path(
        os.environ.get(
            "CAREEROS_DB_PATH",
            "~/.local/share/careeros/careeros.db",
        )
    ).expanduser()
    lock_directory = Path(
        os.environ.get(
            "CAREEROS_LOCK_DIR",
            "~/.local/state/careeros/locks",
        )
    ).expanduser()
    start_row = _configured_start_row()

    store = open_encrypted_store(StoreConfig(database_path), keyring)
    try:
        records = EncryptedRecordStore.from_encrypted_store(store).load_records()
        projection = project_bragsheet(
            records,
            destination_id=destination_id,
            sheet_name=sheet_name,
            start_row=start_row,
        )
        consent = ConsentService(store)
        runner = JobRunner(
            consent=consent,
            sync=SyncService(
                consent=consent,
                run_store=EncryptedSyncRunStore(store.connection()),
            ),
            gateway=BrowserModeClient(web_app_url),
            jobs={configured_job_id: projection},
            lock_directory=lock_directory,
        )
        return runner.run(job_id)
    finally:
        store.close()


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise JobRuntimeConfigurationError(f"{name} is required for run-job")
    return value


def _configured_start_row() -> int:
    raw_value = os.environ.get("CAREEROS_BRAGSHEET_START_ROW", "2")
    try:
        return int(raw_value)
    except ValueError as exc:
        raise JobRuntimeConfigurationError(
            "CAREEROS_BRAGSHEET_START_ROW must be an integer"
        ) from exc
