from __future__ import annotations

import os
import platform
import plistlib
import re
import shlex
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_INTERVAL_MINUTES = 525_600


@dataclass(frozen=True)
class Schedule:
    job_id: str
    command: tuple[str, ...]
    interval_minutes: int = 60

    def __post_init__(self) -> None:
        object.__setattr__(self, "job_id", _validate_job_id(self.job_id))
        object.__setattr__(self, "command", tuple(self.command))
        if not self.command or any(not part for part in self.command):
            raise ValueError("Schedule command must contain nonempty argv values")
        if isinstance(self.interval_minutes, bool) or not isinstance(
            self.interval_minutes,
            int,
        ):
            raise ValueError("Schedule interval must be an integer number of minutes")
        if (
            self.interval_minutes < 1
            or self.interval_minutes > MAX_INTERVAL_MINUTES
        ):
            raise ValueError(
                f"Schedule interval must be between 1 and {MAX_INTERVAL_MINUTES} minutes"
            )


@dataclass(frozen=True)
class SchedulerError:
    code: str
    message: str
    platform: str


@dataclass(frozen=True)
class SchedulerResult:
    ok: bool
    status: str
    job_id: str
    error: SchedulerError | None = None


class _CommandFailed(RuntimeError):
    pass


class _InvalidSchedule(ValueError):
    pass


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_command_runner(
    command: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


class Scheduler:
    def __init__(
        self,
        *,
        system_name: str | None = None,
        home: Path | None = None,
        command_runner: CommandRunner | None = None,
        user_id: int | None = None,
    ) -> None:
        self._system_name = system_name or platform.system()
        self._home = (home or Path.home()).expanduser()
        self._command_runner = command_runner or _default_command_runner
        self._user_id = user_id if user_id is not None else _current_user_id()

    def install(self, schedule: Schedule) -> SchedulerResult:
        adapter = self._adapter()
        if adapter is None:
            return self._unsupported(schedule.job_id)
        try:
            adapter.install(schedule)
        except _InvalidSchedule:
            return self._failure(
                schedule.job_id,
                "scheduler.invalid_schedule",
                "Native scheduler cannot represent this schedule",
            )
        except _CommandFailed:
            return self._failure(
                schedule.job_id,
                "scheduler.command_failed",
                "Native scheduler command failed",
            )
        except OSError:
            return self._failure(
                schedule.job_id,
                "scheduler.install_failed",
                "Native scheduler files could not be installed",
            )
        return SchedulerResult(
            ok=True,
            status="installed",
            job_id=schedule.job_id,
        )

    def remove(self, job_id: str) -> SchedulerResult:
        normalized_job_id = _validate_job_id(job_id)
        adapter = self._adapter()
        if adapter is None:
            return self._unsupported(normalized_job_id)
        try:
            removed = adapter.remove(normalized_job_id)
        except _CommandFailed:
            return self._failure(
                normalized_job_id,
                "scheduler.command_failed",
                "Native scheduler command failed",
            )
        except OSError:
            return self._failure(
                normalized_job_id,
                "scheduler.remove_failed",
                "Native scheduler files could not be removed",
            )
        return SchedulerResult(
            ok=True,
            status="removed" if removed else "not_found",
            job_id=normalized_job_id,
        )

    def _adapter(self) -> _SchedulerAdapter | None:
        normalized = self._system_name.casefold()
        if normalized == "linux":
            return _SystemdUserAdapter(self._home, self._run_command)
        if normalized == "darwin":
            return _LaunchdUserAdapter(
                self._home,
                self._run_command,
                self._user_id,
            )
        if normalized == "windows":
            return _TaskSchedulerAdapter(self._run_command)
        return None

    def _run_command(self, command: Sequence[str]) -> None:
        try:
            completed = self._command_runner(command)
        except OSError as exc:
            raise _CommandFailed from exc
        if completed.returncode != 0:
            raise _CommandFailed

    def _unsupported(self, job_id: str) -> SchedulerResult:
        return self._failure(
            job_id,
            "scheduler.unsupported",
            "No supported native user scheduler is available",
            status="unsupported",
        )

    def _failure(
        self,
        job_id: str,
        code: str,
        message: str,
        *,
        status: str = "error",
    ) -> SchedulerResult:
        return SchedulerResult(
            ok=False,
            status=status,
            job_id=job_id,
            error=SchedulerError(
                code=code,
                message=message,
                platform=self._system_name,
            ),
        )


class _SchedulerAdapter:
    def install(self, schedule: Schedule) -> None:
        raise NotImplementedError

    def remove(self, job_id: str) -> bool:
        raise NotImplementedError


class _SystemdUserAdapter(_SchedulerAdapter):
    def __init__(self, home: Path, run_command: Callable[[Sequence[str]], None]) -> None:
        self._unit_directory = home / ".config" / "systemd" / "user"
        self._run_command = run_command

    def install(self, schedule: Schedule) -> None:
        self._unit_directory.mkdir(parents=True, exist_ok=True)
        service_path, timer_path = self._paths(schedule.job_id)
        service_path.write_text(
            "\n".join(
                (
                    "[Unit]",
                    f"Description=CareerOS background job {schedule.job_id}",
                    "",
                    "[Service]",
                    "Type=oneshot",
                    f"ExecStart={_systemd_command(schedule.command)}",
                    "",
                )
            ),
            encoding="utf-8",
        )
        timer_path.write_text(
            "\n".join(
                (
                    "[Unit]",
                    f"Description=CareerOS timer for {schedule.job_id}",
                    "",
                    "[Timer]",
                    f"OnStartupSec={schedule.interval_minutes}m",
                    f"OnUnitActiveSec={schedule.interval_minutes}m",
                    f"Unit={service_path.name}",
                    "",
                    "[Install]",
                    "WantedBy=timers.target",
                    "",
                )
            ),
            encoding="utf-8",
        )
        os.chmod(service_path, 0o600)
        os.chmod(timer_path, 0o600)
        self._run_command(("systemctl", "--user", "daemon-reload"))
        self._run_command(
            ("systemctl", "--user", "enable", "--now", timer_path.name)
        )

    def remove(self, job_id: str) -> bool:
        service_path, timer_path = self._paths(job_id)
        existed = service_path.exists() or timer_path.exists()
        self._run_command(
            ("systemctl", "--user", "disable", "--now", timer_path.name)
        )
        service_path.unlink(missing_ok=True)
        timer_path.unlink(missing_ok=True)
        self._run_command(("systemctl", "--user", "daemon-reload"))
        return existed

    def _paths(self, job_id: str) -> tuple[Path, Path]:
        stem = f"careeros-{job_id}"
        return (
            self._unit_directory / f"{stem}.service",
            self._unit_directory / f"{stem}.timer",
        )


class _LaunchdUserAdapter(_SchedulerAdapter):
    def __init__(
        self,
        home: Path,
        run_command: Callable[[Sequence[str]], None],
        user_id: int,
    ) -> None:
        self._launch_agents = home / "Library" / "LaunchAgents"
        self._run_command = run_command
        self._domain = f"gui/{user_id}"

    def install(self, schedule: Schedule) -> None:
        self._launch_agents.mkdir(parents=True, exist_ok=True)
        path = self._path(schedule.job_id)
        path.write_bytes(
            plistlib.dumps(
                {
                    "Label": _launchd_label(schedule.job_id),
                    "ProgramArguments": list(schedule.command),
                    "RunAtLoad": False,
                    "StartInterval": schedule.interval_minutes * 60,
                },
                sort_keys=True,
            )
        )
        os.chmod(path, 0o600)
        self._run_command(("launchctl", "bootstrap", self._domain, str(path)))

    def remove(self, job_id: str) -> bool:
        path = self._path(job_id)
        existed = path.exists()
        self._run_command(
            ("launchctl", "bootout", self._domain, str(path))
        )
        path.unlink(missing_ok=True)
        return existed

    def _path(self, job_id: str) -> Path:
        return self._launch_agents / f"{_launchd_label(job_id)}.plist"


class _TaskSchedulerAdapter(_SchedulerAdapter):
    def __init__(self, run_command: Callable[[Sequence[str]], None]) -> None:
        self._run_command = run_command

    def install(self, schedule: Schedule) -> None:
        cadence = _windows_cadence(schedule.interval_minutes)
        self._run_command(
            (
                "schtasks",
                "/Create",
                "/F",
                "/TN",
                _windows_task_name(schedule.job_id),
                "/TR",
                subprocess.list2cmdline(list(schedule.command)),
                *cadence,
            )
        )

    def remove(self, job_id: str) -> bool:
        self._run_command(
            (
                "schtasks",
                "/Delete",
                "/F",
                "/TN",
                _windows_task_name(job_id),
            )
        )
        return True


def _validate_job_id(job_id: str) -> str:
    normalized = job_id.strip()
    if not JOB_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Job ID must contain only letters, digits, underscores, or hyphens"
        )
    return normalized


def _current_user_id() -> int:
    getuid = getattr(os, "getuid", None)
    return int(getuid()) if getuid is not None else 0


def _systemd_command(command: tuple[str, ...]) -> str:
    return shlex.join(command).replace("%", "%%")


def _launchd_label(job_id: str) -> str:
    return f"dev.careeros.job.{job_id}"


def _windows_task_name(job_id: str) -> str:
    return f"CareerOS\\{job_id}"


def _windows_cadence(interval_minutes: int) -> tuple[str, ...]:
    if interval_minutes <= 1_439:
        return ("/SC", "MINUTE", "/MO", str(interval_minutes))
    if interval_minutes % 1_440 == 0:
        return ("/SC", "DAILY", "/MO", str(interval_minutes // 1_440))
    raise _InvalidSchedule("Windows Task Scheduler cannot represent this interval")
