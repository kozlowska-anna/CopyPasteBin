import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from copypastebin.detection import analyze_text
from copypastebin.history import HistoryError, HistoryStore


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temporary.name) / "state")

    def tearDown(self):
        self.temporary.cleanup()

    def record(self, text="person@example.com"):
        return self.store.record(text, "stdin", "chat", analyze_text(text), "warned")

    def test_permissions_hmac_and_no_plaintext(self):
        canary = "private-canary@example.com"
        self.record(canary)
        self.assertEqual(0o700, self.store.state_dir.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.store.database_path.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.store.key_path.stat().st_mode & 0o777)
        self.assertNotIn(canary.encode(), self.store.database_path.read_bytes())
        self.assertNotIn(canary.encode(), self.store.key_path.read_bytes())
        self.assertEqual(32, len(self.store.fingerprint(canary)))
        self.assertNotEqual(self.store.fingerprint(canary), __import__("hashlib").sha256(canary.encode()).digest())

    def test_duplicate_gets_new_id_and_relation(self):
        first = self.record()
        second = self.record()
        self.assertNotEqual(first, second)
        self.assertEqual(first, self.store.get(second).duplicate_of)

    def test_recent_view_is_limited_to_eight(self):
        ids = [self.record(f"person{number}@example.com") for number in range(10)]
        recent = self.store.recent()
        self.assertEqual(8, len(recent))
        self.assertEqual(ids[-1], recent[0].operation_id)
        self.assertNotIn(ids[0], {entry.operation_id for entry in recent})

    def test_bool_and_over_limit_are_invalid_limits(self):
        self.record()
        for limit in (True, -1, 9):
            with self.subTest(limit=limit), self.assertRaises(HistoryError):
                self.store.recent(limit)

    def test_history_schema_has_no_text_columns_for_content(self):
        self.record()
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(operations)")}
        self.assertFalse({"text", "original", "redacted", "preview"} & columns)

    def test_application_metadata_is_normalized_and_content_free(self):
        operation = self.store.record(
            "ordinary private canary",
            "clipboard_event",
            "other",
            analyze_text("ordinary private canary"),
            "warned",
            source_application="org.mozilla.firefox",
            destination_application="../unsafe",
        )
        entry = self.store.get(operation)
        self.assertEqual("org.mozilla.firefox", entry.source_application)
        self.assertEqual("unknown", entry.destination_application)
        self.assertNotIn(
            b"ordinary private canary", self.store.database_path.read_bytes()
        )

    def test_existing_schema_migrates_application_columns_to_unknown(self):
        self.store.initialize()
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            connection.execute("ALTER TABLE operations RENAME TO operations_new")
            connection.execute("""CREATE TABLE operations (
                operation_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                source_kind TEXT NOT NULL, purpose TEXT NOT NULL,
                ruleset_version TEXT NOT NULL, size_bucket TEXT NOT NULL,
                fingerprint BLOB NOT NULL, duplicate_of TEXT,
                highest_risk TEXT NOT NULL, category_counts TEXT NOT NULL,
                status TEXT NOT NULL,
                exception_used INTEGER NOT NULL CHECK(exception_used IN (0, 1)))""")
            connection.execute("DROP TABLE operations_new")
            connection.commit()
        self.store.initialize()
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(operations)")
            }
        self.assertTrue(
            {"source_application", "destination_application"} <= columns
        )

    def test_state_files_reject_symlinks(self):
        target = Path(self.temporary.name) / "target"
        target.mkdir()
        self.store.state_dir.symlink_to(target, target_is_directory=True)
        with self.assertRaises(HistoryError):
            self.store.initialize()
