import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin import cli


class PauseCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temporary.name) / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, action):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(
            ["--state-dir", str(self.state_dir), "pause", action],
            stdin=io.StringIO(),
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_pause_actions_have_closed_safe_output(self):
        cases = (
            ("30m", "CopyPasteBin pause: PAUSED_TIMED remaining_seconds=1800\n"),
            ("1h", "CopyPasteBin pause: PAUSED_TIMED remaining_seconds=3600\n"),
            ("until-resumed", "CopyPasteBin pause: PAUSED_INDEFINITE\n"),
            ("resume", "CopyPasteBin pause: ACTIVE\n"),
        )
        with patch("copypastebin.pause.time.time", return_value=2_000_000_000):
            for action, expected in cases:
                with self.subTest(action=action):
                    code, stdout, stderr = self.run_cli(action)
                    self.assertEqual(0, code)
                    self.assertEqual(expected, stdout)
                    self.assertEqual("", stderr)

    def test_status_reads_persistent_state(self):
        code, _, _ = self.run_cli("until-resumed")
        self.assertEqual(0, code)
        code, stdout, stderr = self.run_cli("status")
        self.assertEqual(0, code)
        self.assertEqual("CopyPasteBin pause: PAUSED_INDEFINITE\n", stdout)
        self.assertEqual("", stderr)

    def test_pause_error_uses_existing_redacted_error_path(self):
        self.state_dir.mkdir(mode=0o700)
        state = self.state_dir / "pause.json"
        state.write_text("private-canary", encoding="utf-8")
        state.chmod(0o600)
        code, stdout, stderr = self.run_cli("status")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertEqual(
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr,
        )
        self.assertNotIn("private-canary", stderr)

    def test_pause_requires_one_supported_action(self):
        for argv in (("pause",), ("pause", "15m")):
            with self.subTest(argv=argv):
                stdout = io.StringIO()
                stderr = io.StringIO()
                code = cli.main(argv, stdout=stdout, stderr=stderr)
                self.assertEqual(2, code)
                self.assertEqual("", stdout.getvalue())
                self.assertNotIn("15m", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
