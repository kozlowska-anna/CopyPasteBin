from __future__ import annotations

import os
import re
import secrets
import selectors
import shutil
import stat
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path

from .executables import ExecutableResolutionError, resolve_entry_point


SERVICE_NAME = "copypastebin-watcher.service"
SERVICE_TIMEOUT_SECONDS = 5.0
SERVICE_OUTPUT_LIMIT_BYTES = 16 * 1024
MANAGED_MARKER = "# Managed by CopyPasteBin V1.1a\n"
_STATUS_PROPERTIES = ("LoadState", "ActiveState", "SubState")
_SAFE_PROPERTY_VALUE = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")


class ServiceError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć usługi CopyPasteBin."

    def __repr__(self) -> str:
        return "ServiceError(redacted=True)"


class ServiceStatus(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


class AutostartStatus(StrEnum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


def default_user_unit_dir(environ: Mapping[str, str] | None = None) -> Path:
    selected_environment = os.environ if environ is None else environ
    configured = selected_environment.get("XDG_CONFIG_HOME")
    root = Path(configured) if configured else Path.home() / ".config"
    if not root.is_absolute():
        raise ServiceError()
    return root / "systemd" / "user"


class ServiceController:
    __slots__ = (
        "_entry_point",
        "_entry_point_which",
        "_systemctl_which",
        "_unit_dir",
        "_user_id",
    )

    def __init__(
        self,
        *,
        unit_dir: Path | None = None,
        entry_point: Path | None = None,
        entry_point_which: Callable[[str], str | None] | None = None,
        systemctl_which: Callable[[str], str | None] | None = None,
        user_id: int | None = None,
    ) -> None:
        self._unit_dir = unit_dir if unit_dir is not None else default_user_unit_dir()
        self._entry_point = entry_point
        self._entry_point_which = entry_point_which
        self._systemctl_which = systemctl_which
        self._user_id = os.geteuid() if user_id is None else user_id

    def __repr__(self) -> str:
        return "ServiceController(content_redacted=True)"

    @property
    def unit_path(self) -> Path:
        return self._unit_dir / SERVICE_NAME

    def setup(self) -> None:
        entry_point = self._resolve_entry_point()
        content = _unit_content(entry_point).encode("utf-8")
        _ensure_private_unit_directory(self._unit_dir, self._user_id)
        state, existing = _read_managed_unit(self.unit_path, self._user_id)
        if state == "foreign":
            raise ServiceError()
        if existing != content:
            _write_unit_atomically(self.unit_path, content)
        return_code, _ = self._run_systemctl(("daemon-reload",), capture=False)
        if return_code != 0:
            raise ServiceError()

    def start(self) -> ServiceStatus:
        if self._managed_state() != "managed":
            raise ServiceError()
        return_code, _ = self._run_systemctl(
            ("start", SERVICE_NAME), capture=False
        )
        if return_code != 0:
            raise ServiceError()
        status = self.status()
        if status is not ServiceStatus.RUNNING:
            raise ServiceError()
        return status

    def stop(self) -> ServiceStatus:
        state = self._managed_state()
        if state == "missing":
            return ServiceStatus.STOPPED
        if state != "managed":
            raise ServiceError()
        return_code, _ = self._run_systemctl(("stop", SERVICE_NAME), capture=False)
        if return_code != 0:
            raise ServiceError()
        status = self.status()
        if status in {ServiceStatus.STOPPED, ServiceStatus.NOT_CONFIGURED}:
            return ServiceStatus.STOPPED
        raise ServiceError()

    def enable(self) -> AutostartStatus:
        if self._managed_state() != "managed":
            raise ServiceError()
        return_code, _ = self._run_systemctl(
            ("enable", SERVICE_NAME), capture=False
        )
        if return_code != 0:
            raise ServiceError()
        return AutostartStatus.ENABLED

    def disable(self) -> AutostartStatus:
        if self._managed_state() != "managed":
            raise ServiceError()
        return_code, _ = self._run_systemctl(
            ("disable", SERVICE_NAME), capture=False
        )
        if return_code != 0:
            raise ServiceError()
        return AutostartStatus.DISABLED

    def autostart(self) -> AutostartStatus:
        if self._managed_state() != "managed":
            return AutostartStatus.UNKNOWN
        try:
            return_code, output = self._run_systemctl(
                ("is-enabled", SERVICE_NAME), capture=True
            )
        except ServiceError:
            return AutostartStatus.UNKNOWN
        if return_code != 0:
            return AutostartStatus.UNKNOWN
        if output == b"enabled\n":
            return AutostartStatus.ENABLED
        if output == b"disabled\n":
            return AutostartStatus.DISABLED
        return AutostartStatus.UNKNOWN

    def status(self) -> ServiceStatus:
        state = self._managed_state()
        if state == "missing":
            return ServiceStatus.NOT_CONFIGURED
        if state != "managed":
            return ServiceStatus.UNKNOWN
        try:
            return_code, output = self._run_systemctl(
                (
                    "show",
                    SERVICE_NAME,
                    "--property=LoadState",
                    "--property=ActiveState",
                    "--property=SubState",
                    "--no-pager",
                ),
                capture=True,
            )
            if return_code != 0:
                return ServiceStatus.UNKNOWN
            properties = _parse_status(output)
        except ServiceError:
            return ServiceStatus.UNKNOWN
        if properties["LoadState"] == "not-found":
            return ServiceStatus.NOT_CONFIGURED
        if properties["LoadState"] != "loaded":
            return ServiceStatus.UNKNOWN
        if (
            properties["ActiveState"] == "active"
            and properties["SubState"] == "running"
        ):
            return ServiceStatus.RUNNING
        if properties["ActiveState"] == "failed":
            return ServiceStatus.FAILED
        if (
            properties["ActiveState"] == "inactive"
            and properties["SubState"] == "dead"
        ):
            return ServiceStatus.STOPPED
        return ServiceStatus.UNKNOWN

    def _managed_state(self) -> str:
        try:
            state, _ = _read_managed_unit(self.unit_path, self._user_id)
        except ServiceError:
            return "foreign"
        return state

    def _resolve_entry_point(self) -> Path:
        try:
            return resolve_entry_point(
                entry_point=self._entry_point,
                entry_point_which=self._entry_point_which,
            )
        except ExecutableResolutionError as exc:
            raise ServiceError() from exc

    def _run_systemctl(
        self, arguments: Sequence[str], *, capture: bool
    ) -> tuple[int, bytes]:
        selected_which = shutil.which if self._systemctl_which is None else self._systemctl_which
        executable = selected_which("systemctl")
        if type(executable) is not str or not executable or not Path(executable).is_absolute():
            raise ServiceError()
        argv = [executable, "--user", *arguments]
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                bufsize=0,
            )
            if capture:
                output = _read_limited_process_output(
                    process, SERVICE_TIMEOUT_SECONDS, SERVICE_OUTPUT_LIMIT_BYTES
                )
            else:
                try:
                    return_code = process.wait(timeout=SERVICE_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired as exc:
                    raise ServiceError() from exc
                output = b""
            return process.returncode, output
        except (OSError, subprocess.SubprocessError, ServiceError) as exc:
            raise ServiceError() from exc
        finally:
            if process is not None:
                _close_process(process)


def _unit_content(entry_point: Path) -> str:
    command = " ".join(
        _systemd_quote(argument)
        for argument in (
            str(entry_point),
            "watch",
            "start",
        )
    )
    return (
        MANAGED_MARKER
        + "[Unit]\n"
        + "Description=CopyPasteBin Wayland clipboard watcher\n"
        + "After=gnome-session-initialized.target\n"
        + "PartOf=graphical-session.target\n\n"
        + "[Service]\n"
        + "Type=exec\n"
        + f"ExecStart={command}\n"
        + "Restart=no\n"
        + "KillMode=control-group\n"
        + "TimeoutStopSec=5s\n"
        + "UMask=0077\n"
        + "NoNewPrivileges=yes\n"
        + "StandardOutput=journal\n"
        + "StandardError=journal\n"
        + "\n[Install]\n"
        + "WantedBy=graphical-session.target\n"
    )


def _systemd_quote(value: str) -> str:
    if not value or any(character in value for character in ("\x00", "\n", "\r")):
        raise ServiceError()
    escaped = value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped + '"'


def _ensure_private_unit_directory(path: Path, user_id: int) -> None:
    if not path.is_absolute():
        raise ServiceError()
    missing: list[Path] = []
    current = path
    while True:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            missing.append(current)
            parent = current.parent
            if parent == current:
                raise ServiceError()
            current = parent
            continue
        except OSError as exc:
            raise ServiceError() from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ServiceError()
        break
    try:
        previous = os.umask(0o077)
        try:
            for directory in reversed(missing):
                directory.mkdir(mode=0o700)
        finally:
            os.umask(previous)
        info = os.lstat(path)
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != user_id
        ):
            raise ServiceError()
        path.chmod(0o700)
    except (OSError, ServiceError) as exc:
        raise ServiceError() from exc


def _read_managed_unit(path: Path, user_id: int) -> tuple[str, bytes | None]:
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return "missing", None
    except (AttributeError, OSError) as exc:
        raise ServiceError() from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != user_id
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > SERVICE_OUTPUT_LIMIT_BYTES
        ):
            return "foreign", None
        data = os.read(descriptor, SERVICE_OUTPUT_LIMIT_BYTES + 1)
    except OSError as exc:
        raise ServiceError() from exc
    finally:
        os.close(descriptor)
    if len(data) > SERVICE_OUTPUT_LIMIT_BYTES or not data.startswith(
        MANAGED_MARKER.encode("utf-8")
    ):
        return "foreign", None
    return "managed", data


def _write_unit_atomically(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{SERVICE_NAME}.{secrets.token_hex(8)}.tmp")
    descriptor: int | None = None
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        descriptor = os.open(temporary, flags, 0o600)
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ServiceError()
            view = view[written:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
    except (OSError, ServiceError) as exc:
        raise ServiceError() from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ServiceError() from exc


def _read_limited_process_output(
    process: subprocess.Popen[bytes], timeout: float, max_bytes: int
) -> bytes:
    if process.stdout is None:
        raise ServiceError()
    deadline = time.monotonic() + timeout
    output = bytearray()
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        reached_eof = False
        while not reached_eof:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ServiceError()
            events = selector.select(remaining)
            if not events:
                raise ServiceError()
            for key, _ in events:
                bytes_left = max_bytes + 1 - len(output)
                chunk = os.read(key.fileobj.fileno(), min(64 * 1024, bytes_left))
                if not chunk:
                    reached_eof = True
                    break
                output.extend(chunk)
                if len(output) > max_bytes:
                    raise ServiceError()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ServiceError()
        try:
            return_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise ServiceError() from exc
        if return_code is None:
            raise ServiceError()
        return bytes(output)
    finally:
        selector.close()


def _close_process(process: subprocess.Popen[bytes]) -> None:
    cleanup_failed = False
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
    except (OSError, subprocess.SubprocessError):
        cleanup_failed = True
    finally:
        if process.stdout is not None:
            process.stdout.close()
    if cleanup_failed:
        raise ServiceError()


def _parse_status(output: bytes) -> dict[str, str]:
    try:
        text = output.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ServiceError() from exc
    properties: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            raise ServiceError()
        name, value = line.split("=", 1)
        if (
            name not in _STATUS_PROPERTIES
            or name in properties
            or _SAFE_PROPERTY_VALUE.fullmatch(value) is None
        ):
            raise ServiceError()
        properties[name] = value
    if set(properties) != set(_STATUS_PROPERTIES):
        raise ServiceError()
    return properties
