from __future__ import annotations

import json
import os
import secrets
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable


PAUSE_30_MINUTES = 30 * 60
PAUSE_1_HOUR = 60 * 60
ALLOWED_TIMED_PAUSES = frozenset({PAUSE_30_MINUTES, PAUSE_1_HOUR})
STATE_VERSION = 1
STATE_FILE_NAME = "pause.json"


class PauseMode(StrEnum):
    ACTIVE = "active"
    TIMED = "timed"
    INDEFINITE = "indefinite"


class PauseError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć stanu pauzy."

    def __repr__(self) -> str:
        return "PauseError(redacted=True)"


@dataclass(frozen=True, slots=True)
class PauseStatus:
    mode: PauseMode
    resume_at: int | None = None
    remaining_seconds: int | None = None

    @property
    def paused(self) -> bool:
        return self.mode is not PauseMode.ACTIVE


def default_pause_state_dir() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    if configured:
        return Path(configured) / "copypastebin"
    return Path.home() / ".local" / "state" / "copypastebin"


class PauseStore:
    __slots__ = ("_clock", "_user_id", "state_dir", "state_path")

    def __init__(
        self,
        state_dir: Path | None = None,
        *,
        clock: Callable[[], float] = time.time,
        user_id: int | None = None,
    ) -> None:
        self.state_dir = state_dir or default_pause_state_dir()
        self.state_path = self.state_dir / STATE_FILE_NAME
        self._clock = clock
        self._user_id = os.geteuid() if user_id is None else user_id

    def status(self) -> PauseStatus:
        document = self._read_document()
        if document is None:
            return PauseStatus(PauseMode.ACTIVE)
        mode = _parse_mode(document)
        if mode is PauseMode.ACTIVE:
            return PauseStatus(mode)
        if mode is PauseMode.INDEFINITE:
            return PauseStatus(mode)
        resume_at = _parse_resume_at(document)
        now = self._now()
        if resume_at <= now:
            self._write_document({"version": STATE_VERSION, "mode": PauseMode.ACTIVE.value})
            return PauseStatus(PauseMode.ACTIVE)
        return PauseStatus(
            PauseMode.TIMED,
            resume_at=resume_at,
            remaining_seconds=resume_at - now,
        )

    def pause_for(self, seconds: int) -> PauseStatus:
        if type(seconds) is not int or seconds not in ALLOWED_TIMED_PAUSES:
            raise PauseError()
        resume_at = self._now() + seconds
        self._write_document(
            {
                "version": STATE_VERSION,
                "mode": PauseMode.TIMED.value,
                "resume_at": resume_at,
            }
        )
        return PauseStatus(
            PauseMode.TIMED,
            resume_at=resume_at,
            remaining_seconds=seconds,
        )

    def pause_indefinitely(self) -> PauseStatus:
        self._write_document(
            {"version": STATE_VERSION, "mode": PauseMode.INDEFINITE.value}
        )
        return PauseStatus(PauseMode.INDEFINITE)

    def resume(self) -> PauseStatus:
        self._write_document(
            {"version": STATE_VERSION, "mode": PauseMode.ACTIVE.value}
        )
        return PauseStatus(PauseMode.ACTIVE)

    def _read_document(self) -> dict[str, object] | None:
        try:
            directory_info = os.lstat(self.state_dir)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise PauseError() from exc
        if (
            not stat.S_ISDIR(directory_info.st_mode)
            or stat.S_ISLNK(directory_info.st_mode)
            or directory_info.st_uid != self._user_id
            or stat.S_IMODE(directory_info.st_mode) != 0o700
        ):
            raise PauseError()
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(self.state_path, flags)
        except FileNotFoundError:
            return None
        except (AttributeError, OSError) as exc:
            raise PauseError() from exc
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self._user_id
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 256
            ):
                raise PauseError()
            payload = os.read(descriptor, 257)
        except OSError as exc:
            raise PauseError() from exc
        finally:
            os.close(descriptor)
        if len(payload) > 256:
            raise PauseError()
        try:
            document = json.loads(payload.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PauseError() from exc
        if type(document) is not dict:
            raise PauseError()
        return document

    def _write_document(self, document: dict[str, object]) -> None:
        _ensure_private_directory(self.state_dir, self._user_id)
        _validate_existing_state_file(self.state_path, self._user_id)
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        temporary = self.state_dir / (
            f".{STATE_FILE_NAME}.{secrets.token_hex(8)}.tmp"
        )
        descriptor: int | None = None
        try:
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0)
            )
            with _private_umask():
                descriptor = os.open(temporary, flags, 0o600)
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise PauseError()
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, self.state_path)
            self.state_path.chmod(0o600)
        except (AttributeError, OSError) as exc:
            raise PauseError() from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _now(self) -> int:
        try:
            current = self._clock()
            if type(current) not in {int, float}:
                raise PauseError()
            converted = int(current)
        except (OverflowError, ValueError) as exc:
            raise PauseError() from exc
        if converted < 0:
            raise PauseError()
        return converted


def _parse_mode(document: dict[str, object]) -> PauseMode:
    if document.get("version") != STATE_VERSION:
        raise PauseError()
    try:
        mode = PauseMode(document.get("mode"))
    except (TypeError, ValueError) as exc:
        raise PauseError() from exc
    expected_keys = {"version", "mode", "resume_at"}
    if not set(document).issubset(expected_keys):
        raise PauseError()
    if mode is not PauseMode.TIMED and "resume_at" in document:
        raise PauseError()
    return mode


def _parse_resume_at(document: dict[str, object]) -> int:
    resume_at = document.get("resume_at")
    if type(resume_at) is not int or resume_at < 0:
        raise PauseError()
    return resume_at


def _ensure_private_directory(path: Path, user_id: int) -> None:
    if not path.is_absolute():
        raise PauseError()
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise PauseError() from exc
    if info is None:
        try:
            with _private_umask():
                path.mkdir(mode=0o700, parents=True, exist_ok=False)
        except FileExistsError:
            pass
        except OSError as exc:
            raise PauseError() from exc
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise PauseError() from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise PauseError()


def _validate_existing_state_file(path: Path, user_id: int) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise PauseError() from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_size > 256
    ):
        raise PauseError()


@contextmanager
def _private_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)
