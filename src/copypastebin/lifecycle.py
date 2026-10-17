from __future__ import annotations

import fcntl
import os
import shutil
import stat
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from types import TracebackType


class LifecycleFailureReason(StrEnum):
    RUNTIME_REENTRY = "RUNTIME_REENTRY"
    SESSION_NOT_WAYLAND = "SESSION_NOT_WAYLAND"
    WAYLAND_DISPLAY_INVALID = "WAYLAND_DISPLAY_INVALID"
    XDG_RUNTIME_DIR_ENV_INVALID = "XDG_RUNTIME_DIR_ENV_INVALID"
    DBUS_SESSION_BUS_ADDRESS_INVALID = "DBUS_SESSION_BUS_ADDRESS_INVALID"
    WL_PASTE_UNAVAILABLE = "WL_PASTE_UNAVAILABLE"
    NOTIFY_SEND_UNAVAILABLE = "NOTIFY_SEND_UNAVAILABLE"
    RUNTIME_DIR_INVALID = "RUNTIME_DIR_INVALID"
    LOCK_REENTRY = "LOCK_REENTRY"
    LOCK_DIR_CREATE_FAILURE = "LOCK_DIR_CREATE_FAILURE"
    LOCK_DIR_INVALID = "LOCK_DIR_INVALID"
    LOCK_FILE_OPEN_FAILURE = "LOCK_FILE_OPEN_FAILURE"
    LOCK_FILE_METADATA_FAILURE = "LOCK_FILE_METADATA_FAILURE"
    LOCK_FILE_INVALID = "LOCK_FILE_INVALID"
    LOCK_BUSY = "LOCK_BUSY"
    LOCK_ACQUIRE_FAILURE = "LOCK_ACQUIRE_FAILURE"
    LOCK_RELEASE_FAILURE = "LOCK_RELEASE_FAILURE"


class LifecycleError(Exception):
    __slots__ = ("_reason",)

    def __init__(self, reason: LifecycleFailureReason) -> None:
        if type(reason) is not LifecycleFailureReason:
            raise TypeError("reason must be LifecycleFailureReason")
        super().__init__()
        self._reason = reason

    @property
    def reason(self) -> LifecycleFailureReason:
        return self._reason

    def __str__(self) -> str:
        return "Nie udało się bezpiecznie uruchomić watchera."

    def __repr__(self) -> str:
        return "LifecycleError(redacted=True)"


def validate_watcher_environment(
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    user_id: int | None = None,
) -> Path:
    selected_environment = os.environ if environ is None else environ
    selected_which = shutil.which if which is None else which
    selected_user_id = os.geteuid() if user_id is None else user_id

    if selected_environment.get("XDG_SESSION_TYPE") != "wayland":
        raise LifecycleError(LifecycleFailureReason.SESSION_NOT_WAYLAND)
    required_environment = (
        ("WAYLAND_DISPLAY", LifecycleFailureReason.WAYLAND_DISPLAY_INVALID),
        ("XDG_RUNTIME_DIR", LifecycleFailureReason.XDG_RUNTIME_DIR_ENV_INVALID),
        (
            "DBUS_SESSION_BUS_ADDRESS",
            LifecycleFailureReason.DBUS_SESSION_BUS_ADDRESS_INVALID,
        ),
    )
    for name, reason in required_environment:
        value = selected_environment.get(name)
        if type(value) is not str or not value or "\x00" in value:
            raise LifecycleError(reason)
    required_executables = (
        ("wl-paste", LifecycleFailureReason.WL_PASTE_UNAVAILABLE),
        ("notify-send", LifecycleFailureReason.NOTIFY_SEND_UNAVAILABLE),
    )
    for executable, reason in required_executables:
        resolved = selected_which(executable)
        if type(resolved) is not str or not resolved or not Path(resolved).is_absolute():
            raise LifecycleError(reason)

    runtime_dir = Path(selected_environment["XDG_RUNTIME_DIR"])
    if not runtime_dir.is_absolute():
        raise LifecycleError(LifecycleFailureReason.RUNTIME_DIR_INVALID)
    descriptor = _open_private_directory(
        runtime_dir,
        selected_user_id,
        reason=LifecycleFailureReason.RUNTIME_DIR_INVALID,
    )
    os.close(descriptor)
    return runtime_dir


class WatcherInstanceLock:
    __slots__ = ("_descriptor", "_runtime_dir", "_user_id")

    def __init__(self, runtime_dir: Path, *, user_id: int | None = None) -> None:
        self._runtime_dir = runtime_dir
        self._user_id = os.geteuid() if user_id is None else user_id
        self._descriptor: int | None = None

    def __repr__(self) -> str:
        return "WatcherInstanceLock(acquired=" + str(self._descriptor is not None) + ")"

    def acquire(self) -> None:
        if self._descriptor is not None:
            raise LifecycleError(LifecycleFailureReason.LOCK_REENTRY)
        runtime_descriptor = _open_private_directory(
            self._runtime_dir,
            self._user_id,
            reason=LifecycleFailureReason.RUNTIME_DIR_INVALID,
        )
        directory_descriptor: int | None = None
        lock_descriptor: int | None = None
        try:
            try:
                with _private_umask():
                    os.mkdir("copypastebin", mode=0o700, dir_fd=runtime_descriptor)
            except FileExistsError:
                pass
            except OSError as exc:
                raise LifecycleError(
                    LifecycleFailureReason.LOCK_DIR_CREATE_FAILURE
                ) from exc
            directory_descriptor = _open_private_directory_at(
                runtime_descriptor,
                "copypastebin",
                self._user_id,
                reason=LifecycleFailureReason.LOCK_DIR_INVALID,
            )
            flags = (
                os.O_RDWR
                | os.O_CREAT
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0)
            )
            with _private_umask():
                try:
                    lock_descriptor = os.open(
                        "watcher.lock", flags, 0o600, dir_fd=directory_descriptor
                    )
                except (AttributeError, OSError) as exc:
                    raise LifecycleError(
                        LifecycleFailureReason.LOCK_FILE_OPEN_FAILURE
                    ) from exc
            try:
                info = os.fstat(lock_descriptor)
            except OSError as exc:
                raise LifecycleError(
                    LifecycleFailureReason.LOCK_FILE_METADATA_FAILURE
                ) from exc
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self._user_id
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size != 0
            ):
                raise LifecycleError(LifecycleFailureReason.LOCK_FILE_INVALID)
            try:
                fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise LifecycleError(LifecycleFailureReason.LOCK_BUSY) from exc
            except OSError as exc:
                raise LifecycleError(
                    LifecycleFailureReason.LOCK_ACQUIRE_FAILURE
                ) from exc
            self._descriptor = lock_descriptor
            lock_descriptor = None
        finally:
            if lock_descriptor is not None:
                os.close(lock_descriptor)
            if directory_descriptor is not None:
                os.close(directory_descriptor)
            os.close(runtime_descriptor)

    def release(self) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is None:
            return
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError as exc:
            raise LifecycleError(LifecycleFailureReason.LOCK_RELEASE_FAILURE) from exc
        finally:
            os.close(descriptor)

    def __enter__(self) -> WatcherInstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


class WatcherRuntime:
    __slots__ = ("_environ", "_lock", "_user_id", "_which")

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        which: Callable[[str], str | None] | None = None,
        user_id: int | None = None,
    ) -> None:
        self._environ = environ
        self._which = which
        self._user_id = user_id
        self._lock: WatcherInstanceLock | None = None

    def __repr__(self) -> str:
        return "WatcherRuntime(content_redacted=True)"

    def __enter__(self) -> WatcherRuntime:
        if self._lock is not None:
            raise LifecycleError(LifecycleFailureReason.RUNTIME_REENTRY)
        runtime_dir = validate_watcher_environment(
            environ=self._environ, which=self._which, user_id=self._user_id
        )
        lock = WatcherInstanceLock(runtime_dir, user_id=self._user_id)
        lock.acquire()
        self._lock = lock
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        lock = self._lock
        self._lock = None
        if lock is not None:
            lock.release()


class _private_umask:
    def __enter__(self) -> None:
        self._previous = os.umask(0o077)

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        os.umask(self._previous)


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _open_private_directory(
    path: Path,
    user_id: int,
    *,
    reason: LifecycleFailureReason,
) -> int:
    try:
        descriptor = os.open(path, _directory_flags())
    except (AttributeError, OSError) as exc:
        raise LifecycleError(reason) from exc
    try:
        _validate_private_directory(descriptor, user_id, reason=reason)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _open_private_directory_at(
    parent: int,
    name: str,
    user_id: int,
    *,
    reason: LifecycleFailureReason,
) -> int:
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
    except (AttributeError, OSError) as exc:
        raise LifecycleError(reason) from exc
    try:
        _validate_private_directory(descriptor, user_id, reason=reason)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _validate_private_directory(
    descriptor: int,
    user_id: int,
    *,
    reason: LifecycleFailureReason,
) -> None:
    try:
        info = os.fstat(descriptor)
    except OSError as exc:
        raise LifecycleError(reason) from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise LifecycleError(reason)
