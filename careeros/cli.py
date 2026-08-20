import argparse
import json
import os
import shlex
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import keyring

from careeros import __version__
from careeros.cli_commands import (
    handle_build_promo_packet,
    handle_capture_delivery,
    handle_deploy_careeros_timeline,
    handle_harvest_retrospective,
    handle_sync_careeros_background,
    handle_validate_bragsheet_integrity,
    handle_write_bragsheet_safe,
    privacy_result,
    records_from_payload,
)
from careeros.consent import ConsentDenied, ConsentService
from careeros.connectors.github import GitHubConnector
from careeros.connectors.google import GoogleConnector
from careeros.deploy import (
    DeployService,
    FileDeploymentRegistry,
    SubprocessClaspAdapter,
)
from careeros.google_client import BrowserModeClient
from careeros.jobs import InvalidJobId, JobResult, JobRunner, UnknownJob
from careeros.models import CommandResult
from careeros.projections import project_bragsheet
from careeros.record_store import EncryptedRecordStore
from careeros.store import StoreConfig, StoreUnavailable, open_encrypted_store
from careeros.sync import EncryptedSyncRunStore, SyncGateway, SyncService

SCHEMA_VERSION = 1
DEFAULT_JOB_ID = "daily"
PORTABLE_COMMANDS = frozenset(
    {
        "capture-delivery",
        "harvest-retrospective",
        "validate-bragsheet-integrity",
        "write-bragsheet-safe",
        "deploy-careeros-timeline",
        "build-promo-packet",
        "sync-careeros",
    }
)


class JobRuntimeConfigurationError(RuntimeError):
    """Raised when local run-job configuration is incomplete."""


class CommandRuntimeConfigurationError(RuntimeError):
    """Raised when a portable command's local configuration is incomplete."""


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
    gateway: SyncGateway | None = None,
    deploy_service: DeployService | None = None,
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
    elif command in PORTABLE_COMMANDS:
        if len(parsed_argv) != 1:
            result = _command_error(
                command,
                "input.arguments",
                f"Usage: python -m careeros {command} [--json]",
            )
        else:
            try:
                payload = _read_stdin_payload()
                result = _dispatch_portable_command(
                    command,
                    payload,
                    run_job=run_job,
                    gateway=gateway,
                    deploy_service=deploy_service,
                )
            except CommandRuntimeConfigurationError as exc:
                result = _command_error(
                    command,
                    "command.configuration",
                    str(exc),
                )
            except StoreUnavailable:
                result = _command_error(
                    command,
                    "command.store_unavailable",
                    "The encrypted local record store is unavailable",
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                result = _command_error(
                    command,
                    "input.invalid",
                    "Standard input must be one valid JSON object",
                )
            except Exception as exc:
                result = _command_error(
                    command,
                    "command.failed",
                    f"Command failed: {type(exc).__name__}",
                )
    else:
        result = handle_unknown(command)

    return emit_result(result, as_json=as_json)


def _read_stdin_payload() -> Mapping[str, object]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("stdin JSON must be an object")
    return payload


def _dispatch_portable_command(
    command: str,
    payload: Mapping[str, object],
    *,
    run_job: Callable[[str], JobResult] | None,
    gateway: SyncGateway | None,
    deploy_service: DeployService | None,
) -> CommandResult:
    if command == "capture-delivery":
        return handle_capture_delivery(payload)
    if command == "harvest-retrospective":
        return _run_harvest_command(payload, gateway=gateway)
    if command == "validate-bragsheet-integrity":
        return _run_validate_command(payload)
    if command == "write-bragsheet-safe":
        return _run_foreground_sync_command(
            payload,
            command=command,
            gateway=gateway,
        )
    if command == "deploy-careeros-timeline":
        return _run_deploy_command(deploy_service=deploy_service)
    if command == "build-promo-packet":
        return _run_promo_command(payload)
    if command == "sync-careeros":
        return _run_sync_command(
            payload,
            run_job=run_job,
            gateway=gateway,
        )
    return handle_unknown(command)


def _run_harvest_command(
    payload: Mapping[str, object],
    *,
    gateway: SyncGateway | None,
) -> CommandResult:
    blocked = privacy_result("harvest-retrospective", payload)
    if blocked is not None:
        return blocked
    if not any(
        key in payload
        for key in ("observations", "excerpt", "thread", "github", "google")
    ):
        return handle_harvest_retrospective(payload, store=_NoopRecordStore())

    store = _open_configured_store()
    try:
        consent = ConsentService(store)
        github_connector = (
            GitHubConnector(consent=consent) if "github" in payload else None
        )
        google_connector = None
        if "google" in payload:
            google_gateway = gateway or BrowserModeClient(
                _required_environment(
                    "CAREEROS_WEB_APP_URL",
                    "harvest-retrospective",
                )
            )
            google_connector = GoogleConnector(google_gateway, consent=consent)
        return handle_harvest_retrospective(
            payload,
            store=EncryptedRecordStore.from_encrypted_store(store),
            github_connector=github_connector,
            google_connector=google_connector,
        )
    finally:
        store.close()


def _run_validate_command(payload: Mapping[str, object]) -> CommandResult:
    blocked = privacy_result("validate-bragsheet-integrity", payload)
    if blocked is not None:
        return blocked
    raw_records = payload.get("records")
    if raw_records is not None:
        if not isinstance(raw_records, list):
            raise ValueError("records must be a list")
        if not all(isinstance(record, Mapping) for record in raw_records):
            raise ValueError("records must contain objects")
        return handle_validate_bragsheet_integrity(raw_records)

    store = _open_configured_store()
    try:
        records = EncryptedRecordStore.from_encrypted_store(store).load_records()
        return handle_validate_bragsheet_integrity(records)
    finally:
        store.close()


def _run_foreground_sync_command(
    payload: Mapping[str, object],
    *,
    command: str,
    gateway: SyncGateway | None,
) -> CommandResult:
    blocked = privacy_result(command, payload)
    if blocked is not None:
        return blocked
    destination_id = _required_environment("CAREEROS_BRAGSHEET_ID", command)
    web_app_url = (
        ""
        if gateway is not None
        else _required_environment("CAREEROS_WEB_APP_URL", command)
    )
    sheet_name = os.environ.get("CAREEROS_BRAGSHEET_NAME", "Brag Sheet")
    start_row = _configured_start_row(command)

    store = _open_configured_store()
    try:
        records = records_from_payload(payload)
        if records is None:
            records = EncryptedRecordStore.from_encrypted_store(store).load_records()
        consent = ConsentService(store)
        sync = SyncService(
            consent=consent,
            run_store=EncryptedSyncRunStore(store.connection()),
        )
        return handle_write_bragsheet_safe(
            records,
            destination_id=destination_id,
            sheet_name=sheet_name,
            start_row=start_row,
            sync=sync,
            gateway=gateway or BrowserModeClient(web_app_url),
            command=command,
        )
    finally:
        store.close()


def _run_deploy_command(
    *,
    deploy_service: DeployService | None,
) -> CommandResult:
    if deploy_service is not None:
        return handle_deploy_careeros_timeline(deploy_service)

    command = "deploy-careeros-timeline"
    resource_id = _required_environment("CAREEROS_DEPLOY_RESOURCE_ID", command)
    registry_path = Path(
        os.environ.get(
            "CAREEROS_DEPLOY_REGISTRY_PATH",
            "~/.local/share/careeros/deployment.json",
        )
    ).expanduser()
    apps_script_directory = Path(
        os.environ.get("CAREEROS_APPS_SCRIPT_DIR", "apps-script")
    ).expanduser()
    raw_clasp_command = os.environ.get(
        "CAREEROS_CLASP_COMMAND",
        "npx --yes @google/clasp",
    )
    clasp_command = tuple(shlex.split(raw_clasp_command))
    if not clasp_command:
        raise CommandRuntimeConfigurationError(
            "CAREEROS_CLASP_COMMAND must contain an executable"
        )

    store = _open_configured_store()
    try:
        ConsentService(store).require(
            "destination",
            resource_id,
            "deploy:timeline",
        )
        service = DeployService(
            clasp=SubprocessClaspAdapter(
                command=clasp_command,
                cwd=apps_script_directory,
            ),
            registry=FileDeploymentRegistry(registry_path),
        )
        return handle_deploy_careeros_timeline(service)
    except ConsentDenied:
        return _command_error(
            command,
            "deploy.consent_denied",
            "Deployment consent is missing or revoked",
        )
    finally:
        store.close()


def _run_promo_command(payload: Mapping[str, object]) -> CommandResult:
    blocked = privacy_result("build-promo-packet", payload)
    if blocked is not None:
        return blocked
    records = records_from_payload(payload)
    if records is not None:
        return handle_build_promo_packet(records)

    store = _open_configured_store()
    try:
        records = EncryptedRecordStore.from_encrypted_store(store).load_records()
        return handle_build_promo_packet(records)
    finally:
        store.close()


def _run_sync_command(
    payload: Mapping[str, object],
    *,
    run_job: Callable[[str], JobResult] | None,
    gateway: SyncGateway | None,
) -> CommandResult:
    background_value = payload.get("background")
    if background_value is not None and not isinstance(background_value, bool):
        raise ValueError("background must be a boolean")
    configured_job_id = os.environ.get("CAREEROS_JOB_ID", "").strip()
    if background_value is True or configured_job_id:
        requested_job_id = payload.get("job_id", configured_job_id or DEFAULT_JOB_ID)
        if not isinstance(requested_job_id, str):
            raise ValueError("job_id must be text")
        return handle_sync_careeros_background(
            requested_job_id,
            run_job=run_job or _run_configured_job,
        )
    return _run_foreground_sync_command(
        payload,
        command="sync-careeros",
        gateway=gateway,
    )


class _NoopRecordStore:
    def persist_records(self, records: object) -> None:
        raise AssertionError("invalid harvest input must not persist")


def _command_error(
    command: str,
    code: str,
    message: str,
) -> CommandResult:
    return CommandResult(
        ok=False,
        command=command,
        data={},
        errors=({"code": code, "message": message},),
    )


def _open_configured_store():
    database_path = Path(
        os.environ.get(
            "CAREEROS_DB_PATH",
            "~/.local/share/careeros/careeros.db",
        )
    ).expanduser()
    return open_encrypted_store(StoreConfig(database_path), keyring)


def _run_configured_job(job_id: str) -> JobResult:
    web_app_url = _required_environment("CAREEROS_WEB_APP_URL", "run-job")
    destination_id = _required_environment("CAREEROS_BRAGSHEET_ID", "run-job")
    configured_job_id = os.environ.get("CAREEROS_JOB_ID", DEFAULT_JOB_ID)
    sheet_name = os.environ.get("CAREEROS_BRAGSHEET_NAME", "Brag Sheet")
    lock_directory = Path(
        os.environ.get(
            "CAREEROS_LOCK_DIR",
            "~/.local/state/careeros/locks",
        )
    ).expanduser()
    start_row = _configured_start_row("run-job")

    store = _open_configured_store()
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


def _required_environment(name: str, command: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        error_type = (
            JobRuntimeConfigurationError
            if command == "run-job"
            else CommandRuntimeConfigurationError
        )
        raise error_type(f"{name} is required for {command}")
    return value


def _configured_start_row(command: str) -> int:
    raw_value = os.environ.get("CAREEROS_BRAGSHEET_START_ROW", "2")
    try:
        return int(raw_value)
    except ValueError as exc:
        error_type = (
            JobRuntimeConfigurationError
            if command == "run-job"
            else CommandRuntimeConfigurationError
        )
        raise error_type("CAREEROS_BRAGSHEET_START_ROW must be an integer") from exc
