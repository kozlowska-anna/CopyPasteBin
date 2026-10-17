from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import stat
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import AnalysisResult
from .application_id import normalize_application_id


VIEW_LIMIT = 8
RETENTION_DAYS = 90
RETENTION_ROWS = 1000


class HistoryError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć lokalnej historii."

    def __repr__(self) -> str:
        return "HistoryError(redacted=True)"


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    operation_id: str
    created_at: str
    source_kind: str
    purpose: str
    highest_risk: str
    category_counts: tuple[tuple[str, int], ...]
    status: str
    duplicate_of: str | None
    ruleset_version: str
    source_application: str
    destination_application: str


def default_state_dir() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    return Path(configured) / "copypastebin" if configured else Path.home() / ".local/state/copypastebin"


@contextmanager
def _private_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


def _ensure_private_dir(path: Path) -> None:
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        current = None
    except OSError as exc:
        raise HistoryError() from exc
    if current is not None and (stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode)):
        raise HistoryError()
    try:
        with _private_umask():
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    except OSError as exc:
        raise HistoryError() from exc


def _ensure_private_file(path: Path, data: bytes | None = None) -> None:
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        current = None
    except OSError as exc:
        raise HistoryError() from exc
    if current is not None:
        if not stat.S_ISREG(current.st_mode):
            raise HistoryError()
        try:
            path.chmod(0o600)
        except OSError as exc:
            raise HistoryError() from exc
        return
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0), 0o600)
    except OSError as exc:
        raise HistoryError() from exc
    try:
        if data is not None:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise HistoryError()
                view = view[written:]
    except OSError as exc:
        raise HistoryError() from exc
    finally:
        os.close(descriptor)


class HistoryStore:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or default_state_dir()
        self.database_path = self.state_dir / "history.sqlite3"
        self.key_path = self.state_dir / "fingerprint.key"

    def initialize(self) -> None:
        _ensure_private_dir(self.state_dir)
        _ensure_private_file(self.key_path, os.urandom(32))
        _ensure_private_file(self.database_path)
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                with connection:
                    connection.execute("PRAGMA journal_mode=DELETE")
                    connection.execute("""CREATE TABLE IF NOT EXISTS operations (
                        operation_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                        source_kind TEXT NOT NULL, purpose TEXT NOT NULL,
                        ruleset_version TEXT NOT NULL, size_bucket TEXT NOT NULL,
                        fingerprint BLOB NOT NULL, duplicate_of TEXT,
                        highest_risk TEXT NOT NULL, category_counts TEXT NOT NULL,
                        status TEXT NOT NULL,
                        exception_used INTEGER NOT NULL CHECK(exception_used IN (0, 1)),
                        source_application TEXT NOT NULL DEFAULT 'unknown',
                        destination_application TEXT NOT NULL DEFAULT 'unknown')""")
                    columns = {
                        str(row[1])
                        for row in connection.execute("PRAGMA table_info(operations)")
                    }
                    if "source_application" not in columns:
                        connection.execute(
                            "ALTER TABLE operations ADD COLUMN source_application "
                            "TEXT NOT NULL DEFAULT 'unknown'"
                        )
                    if "destination_application" not in columns:
                        connection.execute(
                            "ALTER TABLE operations ADD COLUMN destination_application "
                            "TEXT NOT NULL DEFAULT 'unknown'"
                        )
            self.database_path.chmod(0o600)
        except (OSError, sqlite3.Error) as exc:
            raise HistoryError() from exc

    def _key(self) -> bytes:
        if not hasattr(os, "O_NOFOLLOW"):
            raise HistoryError()
        try:
            descriptor = os.open(self.key_path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        except OSError as exc:
            raise HistoryError() from exc
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise HistoryError()
            key = os.read(descriptor, 33)
        except OSError as exc:
            raise HistoryError() from exc
        finally:
            os.close(descriptor)
        if len(key) != 32:
            raise HistoryError()
        return key

    def fingerprint(self, text: str) -> bytes:
        return hmac.new(self._key(), text.encode("utf-8"), hashlib.sha256).digest()

    def record(self, text: str, source_kind: str, purpose: str, result: AnalysisResult, status: str, *, exception_used: bool = False, ruleset_version: str = "1", source_application: str = "unknown", destination_application: str = "unknown") -> str:
        self.initialize()
        operation_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        fingerprint = self.fingerprint(text)
        encoded_counts = json.dumps(result.category_counts, separators=(",", ":"))
        bucket = _size_bucket(len(text.encode("utf-8")))
        source_application = normalize_application_id(source_application)
        destination_application = normalize_application_id(destination_application)
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                with connection:
                    duplicate_row = connection.execute("SELECT operation_id FROM operations WHERE fingerprint=? ORDER BY created_at DESC, operation_id DESC LIMIT 1", (fingerprint,)).fetchone()
                    duplicate_of = duplicate_row[0] if duplicate_row else None
                    connection.execute("""INSERT INTO operations (
                        operation_id, created_at, source_kind, purpose,
                        ruleset_version, size_bucket, fingerprint, duplicate_of,
                        highest_risk, category_counts, status, exception_used,
                        source_application, destination_application
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (operation_id, now, source_kind, purpose, ruleset_version, bucket, fingerprint, duplicate_of, result.highest_risk.value, encoded_counts, status, int(exception_used), source_application, destination_application))
                    cutoff = (datetime.now(UTC) - timedelta(days=RETENTION_DAYS)).isoformat()
                    connection.execute("DELETE FROM operations WHERE created_at < ?", (cutoff,))
                    connection.execute("DELETE FROM operations WHERE operation_id IN (SELECT operation_id FROM operations ORDER BY created_at DESC, operation_id DESC LIMIT -1 OFFSET ?)", (RETENTION_ROWS,))
        except sqlite3.Error as exc:
            raise HistoryError() from exc
        return operation_id

    def recent(self, limit: int = VIEW_LIMIT) -> tuple[HistoryEntry, ...]:
        if type(limit) is not int or not 0 <= limit <= VIEW_LIMIT:
            raise HistoryError()
        self.initialize()
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                rows = connection.execute("SELECT operation_id, created_at, source_kind, purpose, highest_risk, category_counts, status, duplicate_of, ruleset_version, source_application, destination_application FROM operations ORDER BY created_at DESC, operation_id DESC LIMIT ?", (limit,)).fetchall()
        except sqlite3.Error as exc:
            raise HistoryError() from exc
        return tuple(_entry(row) for row in rows)

    def get(self, operation_id: str) -> HistoryEntry | None:
        self.initialize()
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                row = connection.execute("SELECT operation_id, created_at, source_kind, purpose, highest_risk, category_counts, status, duplicate_of, ruleset_version, source_application, destination_application FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        except sqlite3.Error as exc:
            raise HistoryError() from exc
        return _entry(row) if row else None

    def set_outcome(self, operation_id: str, status: str, *, exception_used: bool = False) -> None:
        if status not in {"copied_original", "copied_redacted", "warned", "blocked", "cancelled", "failed"}:
            raise HistoryError()
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                with connection:
                    cursor = connection.execute(
                        "UPDATE operations SET status=?, exception_used=? WHERE operation_id=?",
                        (status, int(exception_used), operation_id),
                    )
                    if cursor.rowcount != 1:
                        raise HistoryError()
        except sqlite3.Error as exc:
            raise HistoryError() from exc


def _entry(row: tuple[object, ...]) -> HistoryEntry:
    counts = tuple((str(name), int(count)) for name, count in json.loads(str(row[5])))
    return HistoryEntry(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), counts, str(row[6]), str(row[7]) if row[7] else None, str(row[8]), str(row[9]), str(row[10]))


def _size_bucket(size: int) -> str:
    if size == 0:
        return "empty"
    if size <= 1024:
        return "small"
    if size <= 1024 * 1024:
        return "medium"
    return "large"
