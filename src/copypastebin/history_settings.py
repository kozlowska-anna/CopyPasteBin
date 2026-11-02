Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
from __future__ import annotations

import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from .filters import (
    FilterError,
    _ensure_private_directory,
    _private_umask,
    _validate_existing_state_file,
    default_filter_state_dir,
)


STATE_VERSION = 1
STATE_FILE_NAME = "history-settings.json"
MAX_STATE_BYTES = 128


class HistorySettingsError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć ustawienia historii."

    def __repr__(self) -> str:
        return "HistorySettingsError(redacted=True)"


@dataclass(frozen=True, slots=True)
class HistorySettingsStatus:
    enabled: bool = True


class HistorySettingsStore:
    __slots__ = ("_user_id", "state_dir", "state_path")

    def __init__(self, state_dir: Path | None = None, *, user_id: int | None = None) -> None:
        self.state_dir = state_dir or default_filter_state_dir()
        self.state_path = self.state_dir / STATE_FILE_NAME
        self._user_id = os.geteuid() if user_id is None else user_id

    def status(self) -> HistorySettingsStatus:
        document = self._read_document()
        if document is None:
            return HistorySettingsStatus()
        enabled = document.get("enabled")
        if (
            set(document) != {"version", "enabled"}
            or document.get("version") != STATE_VERSION
            or type(enabled) is not bool
        ):
            raise HistorySettingsError()
        return HistorySettingsStatus(enabled)

    def set_enabled(self, enabled: bool) -> HistorySettingsStatus:
        if type(enabled) is not bool:
            raise HistorySettingsError()
        self._write_document({"version": STATE_VERSION, "enabled": enabled})
        return HistorySettingsStatus(enabled)

    def _read_document(self) -> dict[str, object] | None:
        try:
            directory_info = os.lstat(self.state_dir)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise HistorySettingsError() from exc
        if (
            not stat.S_ISDIR(directory_info.st_mode)
            or stat.S_ISLNK(directory_info.st_mode)
            or directory_info.st_uid != self._user_id
            or stat.S_IMODE(directory_info.st_mode) != 0o700
        ):
            raise HistorySettingsError()
        try:
            descriptor = os.open(
                self.state_path,
                os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            )
        except FileNotFoundError:
            return None
        except (AttributeError, OSError) as exc:
            raise HistorySettingsError() from exc
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self._user_id
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > MAX_STATE_BYTES
            ):
                raise HistorySettingsError()
            payload = os.read(descriptor, MAX_STATE_BYTES + 1)
        except OSError as exc:
            raise HistorySettingsError() from exc
        finally:
            os.close(descriptor)
        try:
            document = json.loads(payload.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HistorySettingsError() from exc
        if type(document) is not dict:
            raise HistorySettingsError()
        return document

    def _write_document(self, document: dict[str, object]) -> None:
        try:
            _ensure_private_directory(self.state_dir, self._user_id)
            _validate_existing_state_file(self.state_path, self._user_id)
        except FilterError as exc:
            raise HistorySettingsError() from exc
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        temporary = self.state_dir / f".{STATE_FILE_NAME}.{secrets.token_hex(8)}.tmp"
        descriptor: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            with _private_umask():
                descriptor = os.open(temporary, flags, 0o600)
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise HistorySettingsError()
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, self.state_path)
            self.state_path.chmod(0o600)
        except (AttributeError, OSError) as exc:
            raise HistorySettingsError() from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
