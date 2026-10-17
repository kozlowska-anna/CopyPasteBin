from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Callable, Mapping
from pathlib import Path

from .executables import ExecutableResolutionError, resolve_entry_point


LAUNCHER_NAME = "copypastebin-start.desktop"
LAUNCHER_MAX_BYTES = 16 * 1024
MANAGED_MARKER = "# Managed by CopyPasteBin V1.1c\n"


class LauncherError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie skonfigurować launchera CopyPasteBin."

    def __repr__(self) -> str:
        return "LauncherError(redacted=True)"


def default_user_application_dir(
    environ: Mapping[str, str] | None = None,
) -> Path:
    selected_environment = os.environ if environ is None else environ
    configured = selected_environment.get("XDG_DATA_HOME")
    root = Path(configured) if configured else Path.home() / ".local" / "share"
    if not root.is_absolute():
        raise LauncherError()
    return root / "applications"


class LauncherController:
    __slots__ = (
        "_application_dir",
        "_entry_point",
        "_entry_point_which",
        "_user_id",
    )

    def __init__(
        self,
        *,
        application_dir: Path | None = None,
        entry_point: Path | None = None,
        entry_point_which: Callable[[str], str | None] | None = None,
        user_id: int | None = None,
    ) -> None:
        self._application_dir = (
            default_user_application_dir()
            if application_dir is None
            else application_dir
        )
        self._entry_point = entry_point
        self._entry_point_which = entry_point_which
        self._user_id = os.geteuid() if user_id is None else user_id

    def __repr__(self) -> str:
        return "LauncherController(content_redacted=True)"

    @property
    def launcher_path(self) -> Path:
        return self._application_dir / LAUNCHER_NAME

    def setup(self) -> None:
        try:
            entry_point = resolve_entry_point(
                entry_point=self._entry_point,
                entry_point_which=self._entry_point_which,
            )
        except ExecutableResolutionError as exc:
            raise LauncherError() from exc
        content = _launcher_content(entry_point).encode("utf-8")
        _ensure_application_directory(self._application_dir, self._user_id)
        state, existing = _read_managed_launcher(
            self.launcher_path, self._user_id
        )
        if state == "foreign":
            raise LauncherError()
        if existing != content:
            _write_launcher_atomically(self.launcher_path, content)


def _launcher_content(entry_point: Path) -> str:
    command = " ".join(
        _desktop_exec_quote(argument)
        for argument in (str(entry_point), "service", "start")
    )
    return (
        MANAGED_MARKER
        + "[Desktop Entry]\n"
        + "Type=Application\n"
        + "Version=1.0\n"
        + "Name=Start CopyPasteBin\n"
        + "Comment=Uruchom ochronę schowka CopyPasteBin\n"
        + f"Exec={command}\n"
        + "Icon=edit-paste\n"
        + "Terminal=false\n"
        + "Categories=System;Security;\n"
        + "StartupNotify=false\n"
        + "DBusActivatable=false\n"
    )


def _desktop_exec_quote(value: str) -> str:
    if (
        not value
        or not value.isascii()
        or "=" in value
        or any(character in value for character in ("\x00", "\n", "\r"))
    ):
        raise LauncherError()
    escaped = (
        value.replace("\\", "\\\\\\\\")
        .replace('"', '\\\\"')
        .replace("`", "\\\\`")
        .replace("$", "\\\\$")
        .replace("%", "%%")
    )
    return '"' + escaped + '"'


def _ensure_application_directory(path: Path, user_id: int) -> None:
    if not path.is_absolute():
        raise LauncherError()
    missing: list[Path] = []
    current = path
    while True:
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            missing.append(current)
            parent = current.parent
            if parent == current:
                raise LauncherError()
            current = parent
            continue
        except OSError as exc:
            raise LauncherError() from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise LauncherError()
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
            raise LauncherError()
    except (OSError, LauncherError) as exc:
        raise LauncherError() from exc


def _read_managed_launcher(
    path: Path, user_id: int
) -> tuple[str, bytes | None]:
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return "missing", None
    except (AttributeError, OSError) as exc:
        raise LauncherError() from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != user_id
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > LAUNCHER_MAX_BYTES
        ):
            return "foreign", None
        data = os.read(descriptor, LAUNCHER_MAX_BYTES + 1)
    except OSError as exc:
        raise LauncherError() from exc
    finally:
        os.close(descriptor)
    if len(data) > LAUNCHER_MAX_BYTES or not data.startswith(
        MANAGED_MARKER.encode("utf-8")
    ):
        return "foreign", None
    return "managed", data


def _write_launcher_atomically(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{LAUNCHER_NAME}.{secrets.token_hex(8)}.tmp")
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
                raise LauncherError()
            view = view[written:]
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
    except (OSError, LauncherError) as exc:
        raise LauncherError() from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise LauncherError() from exc
