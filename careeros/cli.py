import argparse
import json
import sys
from collections.abc import Sequence

from careeros import __version__
from careeros.models import CommandResult

SCHEMA_VERSION = 1


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


def main(argv: Sequence[str] | None = None) -> int:
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

    if command == "version":
        result = handle_version()
    else:
        result = handle_unknown(command)

    return emit_result(result, as_json=as_json)
