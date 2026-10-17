import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from copypastebin import cli
from copypastebin.launcher import LauncherError
from copypastebin.service import ServiceController


class LauncherCliTests(unittest.TestCase):
    def run_cli(self, extra):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            code = cli.main(
                [
                    "--state-dir",
                    str(Path(directory) / "state"),
                    "--config",
                    str(Path(directory) / "missing.toml"),
                    *extra,
                ],
                stdout=stdout,
                stderr=stderr,
            )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_launcher_setup_has_one_closed_success_response(self):
        controller = Mock()
        with patch(
            "copypastebin.cli.LauncherController", return_value=controller
        ), patch(
            "copypastebin.cli.HistoryStore.initialize"
        ) as history_initialize, patch.object(
            ServiceController, "setup"
        ) as service_setup, patch.object(
            ServiceController, "start"
        ) as service_start, patch.object(
            ServiceController, "enable"
        ) as service_enable, patch.object(
            ServiceController, "disable"
        ) as service_disable:
            code, stdout, stderr = self.run_cli(["launcher", "setup"])
        self.assertEqual(0, code)
        self.assertEqual("CopyPasteBin launcher: CONFIGURED\n", stdout)
        self.assertEqual("", stderr)
        controller.setup.assert_called_once_with()
        history_initialize.assert_not_called()
        service_setup.assert_not_called()
        service_start.assert_not_called()
        service_enable.assert_not_called()
        service_disable.assert_not_called()

    def test_launcher_requires_explicit_supported_action(self):
        for argv in (["launcher"], ["launcher", "start"], ["launcher", "status"]):
            with self.subTest(argv=argv):
                code, stdout, stderr = self.run_cli(argv)
            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertIn("cpb: niepoprawne użycie.", stderr)

    def test_launcher_error_uses_existing_redacted_cli_path(self):
        canary = "LAUNCHER_PRIVATE_CANARY\x1b\u202e"
        controller = Mock()
        controller.setup.side_effect = LauncherError(canary)
        with patch(
            "copypastebin.cli.LauncherController", return_value=controller
        ):
            code, stdout, stderr = self.run_cli(["launcher", "setup"])
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertEqual(
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr,
        )
        self.assertNotIn(canary, stdout + stderr)
        self.assertNotIn("Traceback", stdout + stderr)


if __name__ == "__main__":
    unittest.main()
