from __future__ import annotations

import json
import os
import secrets
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .models import Category


STATE_VERSION = 2
STATE_FILE_NAME = "filters.json"
MAX_STATE_BYTES = 1024
ALL_CATEGORIES = tuple(Category)
AUTO_CLEAR_CHOICES = (0, 60, 300, 900)
DEFAULT_DISABLED_CATEGORIES = frozenset(
    {
        Category.HOME_PATH,
        Category.POSSIBLE_SEED_PHRASE,
        Category.TOKEN,
    }
)


class FilterError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć ustawień filtrów."

    def __repr__(self) -> str:
        return "FilterError(redacted=True)"


@dataclass(frozen=True, slots=True)
class FilterStatus:
    disabled: frozenset[Category]
    auto_clear_seconds: int = 0

    def enabled(self, category: Category) -> bool:
        if type(category) is not Category:
            raise FilterError()
        return category not in self.disabled


def default_filter_state_dir() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    if configured:
        return Path(configured) / "copypastebin"
    return Path.home() / ".local" / "state" / "copypastebin"


class FilterStore:
    __slots__ = ("_user_id", "state_dir", "state_path")

    def __init__(
        self,
        state_dir: Path | None = None,
        *,
        user_id: int | None = None,
    ) -> None:
        self.state_dir = state_dir or default_filter_state_dir()
        self.state_path = self.state_dir / STATE_FILE_NAME
        self._user_id = os.geteuid() if user_id is None else user_id

    def status(self) -> FilterStatus:
        document = self._read_document()
        if document is None:
            return FilterStatus(DEFAULT_DISABLED_CATEGORIES)
        version = document.get("version")
        if version == 1:
            if set(document) != {"version", "disabled"}:
                raise FilterError()
            auto_clear_seconds = 0
        elif version == STATE_VERSION:
            if set(document) != {"version", "disabled", "auto_clear_seconds"}:
                raise FilterError()
            auto_clear_seconds = document.get("auto_clear_seconds")
            if type(auto_clear_seconds) is not int or auto_clear_seconds not in AUTO_CLEAR_CHOICES:
                raise FilterError()
        else:
            raise FilterError()
        disabled = document.get("disabled")
        if type(disabled) is not list or len(disabled) > len(ALL_CATEGORIES):
            raise FilterError()
        if any(type(value) is not str for value in disabled):
            raise FilterError()
        if disabled != sorted(set(disabled)):
            raise FilterError()
        try:
            categories = frozenset(Category(value) for value in disabled)
        except ValueError as exc:
            raise FilterError() from exc
        return FilterStatus(categories, auto_clear_seconds)

    def set_enabled(self, category: Category, enabled: bool) -> FilterStatus:
        if type(category) is not Category or type(enabled) is not bool:
            raise FilterError()
        current = self.status()
        disabled = set(current.disabled)
        if enabled:
            disabled.discard(category)
        else:
            disabled.add(category)
        self._write_document(
            {
                "version": STATE_VERSION,
                "disabled": sorted(item.value for item in disabled),
                "auto_clear_seconds": current.auto_clear_seconds,
            }
        )
        return FilterStatus(frozenset(disabled), current.auto_clear_seconds)

    def set_auto_clear(self, seconds: int) -> FilterStatus:
        if type(seconds) is not int or seconds not in AUTO_CLEAR_CHOICES:
            raise FilterError()
        current = self.status()
        self._write_document(
            {
                "version": STATE_VERSION,
                "disabled": sorted(item.value for item in current.disabled),
                "auto_clear_seconds": seconds,
            }
        )
        return FilterStatus(current.disabled, seconds)

    def _read_document(self) -> dict[str, object] | None:
        try:
            directory_info = os.lstat(self.state_dir)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise FilterError() from exc
        if (
            not stat.S_ISDIR(directory_info.st_mode)
            or stat.S_ISLNK(directory_info.st_mode)
            or directory_info.st_uid != self._user_id
            or stat.S_IMODE(directory_info.st_mode) != 0o700
        ):
            raise FilterError()
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(self.state_path, flags)
        except FileNotFoundError:
            return None
        except (AttributeError, OSError) as exc:
            raise FilterError() from exc
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self._user_id
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > MAX_STATE_BYTES
            ):
                raise FilterError()
            payload = os.read(descriptor, MAX_STATE_BYTES + 1)
        except OSError as exc:
            raise FilterError() from exc
        finally:
            os.close(descriptor)
        if len(payload) > MAX_STATE_BYTES:
            raise FilterError()
        try:
            document = json.loads(payload.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FilterError() from exc
        if type(document) is not dict:
            raise FilterError()
        return document

    def _write_document(self, document: dict[str, object]) -> None:
        _ensure_private_directory(self.state_dir, self._user_id)
        _validate_existing_state_file(self.state_path, self._user_id)
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        if len(payload) > MAX_STATE_BYTES:
            raise FilterError()
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
                    raise FilterError()
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, self.state_path)
            self.state_path.chmod(0o600)
        except (AttributeError, OSError) as exc:
            raise FilterError() from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _ensure_private_directory(path: Path, user_id: int) -> None:
    if not path.is_absolute():
        raise FilterError()
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    except OSError as exc:
        raise FilterError() from exc
    if info is None:
        try:
            with _private_umask():
                path.mkdir(mode=0o700, parents=True, exist_ok=False)
        except FileExistsError:
            pass
        except OSError as exc:
            raise FilterError() from exc
        try:
            info = os.lstat(path)
        except OSError as exc:
            raise FilterError() from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise FilterError()


def _validate_existing_state_file(path: Path, user_id: int) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise FilterError() from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_size > MAX_STATE_BYTES
    ):
        raise FilterError()


@contextmanager
def _private_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)
