import json
import os
import tempfile
import unittest
from pathlib import Path

from copypastebin.pause import (
    PAUSE_1_HOUR,
    PAUSE_30_MINUTES,
    PauseError,
    PauseMode,
    PauseStore,
)


class PauseStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_dir = self.root / "state"
        self.now = 2_000_000_000
        self.store = PauseStore(self.state_dir, clock=lambda: self.now)

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_state_is_active_without_creating_files(self):
        status = self.store.status()
        self.assertIs(PauseMode.ACTIVE, status.mode)
        self.assertFalse(status.paused)
        self.assertFalse(self.state_dir.exists())

    def test_only_approved_timed_pauses_are_accepted(self):
        for seconds in (PAUSE_30_MINUTES, PAUSE_1_HOUR):
            with self.subTest(seconds=seconds):
                status = self.store.pause_for(seconds)
                self.assertIs(PauseMode.TIMED, status.mode)
                self.assertEqual(seconds, status.remaining_seconds)
                self.assertEqual(self.now + seconds, status.resume_at)
        for invalid in (True, 0, 60, 1801, 7200, "1800", None):
            with self.subTest(invalid=invalid), self.assertRaises(PauseError):
                self.store.pause_for(invalid)

    def test_timed_pause_expires_using_wall_clock_and_persists_active(self):
        self.store.pause_for(PAUSE_30_MINUTES)
        self.now += PAUSE_30_MINUTES - 1
        self.assertEqual(1, self.store.status().remaining_seconds)
        self.now += 1
        self.assertIs(PauseMode.ACTIVE, self.store.status().mode)
        document = json.loads(self.store.state_path.read_text(encoding="ascii"))
        self.assertEqual({"mode": "active", "version": 1}, document)

    def test_indefinite_pause_and_manual_resume_survive_new_store(self):
        self.store.pause_indefinitely()
        other = PauseStore(self.state_dir, clock=lambda: self.now + 1_000_000)
        self.assertIs(PauseMode.INDEFINITE, other.status().mode)
        self.assertTrue(other.status().paused)
        other.resume()
        self.assertIs(PauseMode.ACTIVE, self.store.status().mode)

    def test_state_contains_only_mode_deadline_and_version_with_private_permissions(self):
        self.store.pause_for(PAUSE_1_HOUR)
        self.assertEqual(0o700, self.state_dir.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.store.state_path.stat().st_mode & 0o777)
        document = json.loads(self.store.state_path.read_text(encoding="ascii"))
        self.assertEqual({"mode", "resume_at", "version"}, set(document))
        self.assertNotIn("clipboard", self.store.state_path.read_text(encoding="ascii"))

    def test_corrupt_or_extended_documents_fail_closed(self):
        self.state_dir.mkdir(mode=0o700)
        cases = (
            b"not-json",
            b"[]",
            b'{"mode":"active","version":2}',
            b'{"extra":1,"mode":"active","version":1}',
            b'{"mode":"timed","version":1}',
            b'{"mode":"active","resume_at":1,"version":1}',
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.store.state_path.write_bytes(payload)
                self.store.state_path.chmod(0o600)
                with self.assertRaises(PauseError):
                    self.store.status()

    def test_symlink_and_non_private_state_are_rejected(self):
        target = self.root / "target"
        target.mkdir(mode=0o700)
        self.state_dir.symlink_to(target, target_is_directory=True)
        with self.assertRaises(PauseError):
            self.store.pause_indefinitely()

        self.state_dir.unlink()
        self.state_dir.mkdir(mode=0o700)
        target_file = self.root / "foreign"
        target_file.write_text('{"mode":"active","version":1}', encoding="ascii")
        self.store.state_path.symlink_to(target_file)
        with self.assertRaises(PauseError):
            self.store.status()
        with self.assertRaises(PauseError):
            self.store.pause_for(PAUSE_30_MINUTES)
        self.assertTrue(self.store.state_path.is_symlink())
        self.assertEqual(
            '{"mode":"active","version":1}',
            target_file.read_text(encoding="ascii"),
        )

    def test_wrong_file_permissions_and_oversized_state_are_rejected(self):
        self.store.pause_indefinitely()
        self.store.state_path.chmod(0o644)
        with self.assertRaises(PauseError):
            self.store.status()

        self.store.state_path.unlink()
        self.store.state_path.write_bytes(b"x" * 257)
        self.store.state_path.chmod(0o600)
        with self.assertRaises(PauseError):
            self.store.status()

    def test_error_text_and_repr_do_not_disclose_causes(self):
        error = PauseError("private-canary")
        self.assertEqual(
            "Nie udało się bezpiecznie obsłużyć stanu pauzy.", str(error)
        )
        self.assertEqual("PauseError(redacted=True)", repr(error))
        self.assertNotIn("private-canary", str(error) + repr(error))

    def test_invalid_clock_fails_closed(self):
        for value in (True, "2000000000", -1, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(PauseError):
                PauseStore(self.state_dir, clock=lambda value=value: value).pause_for(
                    PAUSE_30_MINUTES
                )


if __name__ == "__main__":
    unittest.main()
