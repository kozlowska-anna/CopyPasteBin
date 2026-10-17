from __future__ import annotations

import json
import locale
import os
import secrets
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


STATE_VERSION = 1
STATE_FILE_NAME = "language.json"
MAX_STATE_BYTES = 128
LANGUAGE_CHOICES = ("system", "pl", "en")


class LanguageError(Exception):
    def __str__(self) -> str:
        return "Unable to safely handle the language setting."

    def __repr__(self) -> str:
        return "LanguageError(redacted=True)"


@dataclass(frozen=True, slots=True)
class LanguageStatus:
    choice: str
    effective: str


def default_language_state_dir() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    if configured:
        return Path(configured) / "copypastebin"
    return Path.home() / ".local" / "state" / "copypastebin"


def system_language() -> str:
    try:
        selected = locale.getlocale()[0]
    except (TypeError, ValueError):
        selected = None
    return "pl" if selected and selected.lower().startswith("pl") else "en"


class LanguageStore:
    __slots__ = ("_user_id", "state_dir", "state_path")

    def __init__(
        self,
        state_dir: Path | None = None,
        *,
        user_id: int | None = None,
    ) -> None:
        self.state_dir = state_dir or default_language_state_dir()
        self.state_path = self.state_dir / STATE_FILE_NAME
        self._user_id = os.geteuid() if user_id is None else user_id

    def status(self) -> LanguageStatus:
        document = self._read_document()
        choice = "system" if document is None else document.get("choice")
        if choice not in LANGUAGE_CHOICES:
            raise LanguageError()
        effective = system_language() if choice == "system" else choice
        return LanguageStatus(choice, effective)

    def set_choice(self, choice: str) -> LanguageStatus:
        if type(choice) is not str or choice not in LANGUAGE_CHOICES:
            raise LanguageError()
        self._write_document({"version": STATE_VERSION, "choice": choice})
        return self.status()

    def _read_document(self) -> dict[str, object] | None:
        try:
            directory_info = os.lstat(self.state_dir)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise LanguageError() from exc
        if (
            not stat.S_ISDIR(directory_info.st_mode)
            or stat.S_ISLNK(directory_info.st_mode)
            or directory_info.st_uid != self._user_id
            or stat.S_IMODE(directory_info.st_mode) != 0o700
        ):
            raise LanguageError()
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(self.state_path, flags)
        except FileNotFoundError:
            return None
        except (AttributeError, OSError) as exc:
            raise LanguageError() from exc
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self._user_id
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > MAX_STATE_BYTES
            ):
                raise LanguageError()
            payload = os.read(descriptor, MAX_STATE_BYTES + 1)
        except OSError as exc:
            raise LanguageError() from exc
        finally:
            os.close(descriptor)
        if len(payload) > MAX_STATE_BYTES:
            raise LanguageError()
        try:
            document = json.loads(payload.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LanguageError() from exc
        if (
            type(document) is not dict
            or set(document) != {"version", "choice"}
            or document.get("version") != STATE_VERSION
        ):
            raise LanguageError()
        return document

    def _write_document(self, document: dict[str, object]) -> None:
        _ensure_private_directory(self.state_dir, self._user_id)
        _validate_existing_state_file(self.state_path, self._user_id)
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        if len(payload) > MAX_STATE_BYTES:
            raise LanguageError()
        temporary = self.state_dir / f".{STATE_FILE_NAME}.{secrets.token_hex(8)}.tmp"
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
                    raise LanguageError()
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, self.state_path)
            self.state_path.chmod(0o600)
        except (AttributeError, OSError) as exc:
            raise LanguageError() from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _ensure_private_directory(path: Path, user_id: int) -> None:
    if not path.is_absolute():
        raise LanguageError()
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise LanguageError() from exc
    if info is None:
        try:
            with _private_umask():
                path.mkdir(mode=0o700, parents=True, exist_ok=False)
        except FileExistsError:
            pass
        except OSError as exc:
            raise LanguageError() from exc
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise LanguageError() from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise LanguageError()


def _validate_existing_state_file(path: Path, user_id: int) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise LanguageError() from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise LanguageError()


@contextmanager
def _private_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)
