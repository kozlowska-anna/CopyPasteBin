Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import json
import tempfile
import unittest
from pathlib import Path

from copypastebin.history_settings import (
    HistorySettingsError,
    HistorySettingsStore,
)
from copypastebin.pause import PauseStore


class HistorySettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_is_enabled_and_choice_persists_without_content(self):
        self.assertTrue(HistorySettingsStore(self.state).status().enabled)
        HistorySettingsStore(self.state).set_enabled(False)
        self.assertFalse(HistorySettingsStore(self.state).status().enabled)
        path = self.state / "history-settings.json"
        self.assertEqual(
            {"version": 1, "enabled": False},
            json.loads(path.read_text(encoding="ascii")),
        )
        self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_malformed_or_symlinked_state_fails_closed(self):
        self.state.mkdir(mode=0o700)
        target = Path(self.temporary.name) / "outside"
        target.write_text('{"version":1,"enabled":true}', encoding="ascii")
        (self.state / "history-settings.json").symlink_to(target)
        with self.assertRaises(HistorySettingsError):
            HistorySettingsStore(self.state).status()

    def test_pause_state_does_not_change_history_choice(self):
        HistorySettingsStore(self.state).set_enabled(False)
        PauseStore(self.state).pause_indefinitely()
        self.assertFalse(HistorySettingsStore(self.state).status().enabled)
        PauseStore(self.state).resume()
        self.assertFalse(HistorySettingsStore(self.state).status().enabled)


if __name__ == "__main__":
    unittest.main()
