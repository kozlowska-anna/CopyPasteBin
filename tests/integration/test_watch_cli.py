import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from copypastebin import cli
from copypastebin.lifecycle import LifecycleFailureReason
from copypastebin.service import AutostartStatus, ServiceError, ServiceStatus
from copypastebin.watcher import (
    ClipboardSample,
    ClipboardSampleKind,
    ClipboardWatcher,
    WatcherBackendError,
    WatcherError,
)


class _Runtime:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return None


class _FastWatcher(ClipboardWatcher):
    def run_forever(self, **kwargs):
        return super().run_forever(sleep=lambda _: None, **kwargs)


class WatchCliTests(unittest.TestCase):
    def run_cli(self, extra):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            argv = ["--state-dir", str(Path(directory) / "state"), "--config", str(Path(directory) / "missing.toml"), *extra]
            code = cli.main(argv, stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_foreground_start_and_ctrl_c_stop_are_explicit(self):
        with patch("copypastebin.cli.ClipboardWatcher.run_forever", side_effect=KeyboardInterrupt):
            code, stdout, stderr = self.run_cli(["watch", "start"])
        self.assertEqual(0, code)
        self.assertIn("pierwszoplanowym", stdout)
        self.assertIn("Watcher zatrzymany", stdout)
        self.assertEqual("", stderr)

    def test_backend_failure_has_fixed_error_and_no_traceback_or_canary(self):
        with patch("copypastebin.cli.ClipboardWatcher.run_forever", side_effect=WatcherError("private-canary\x1b")):
            code, stdout, stderr = self.run_cli(["watch", "start"])
        self.assertEqual(1, code)
        self.assertIn("pierwszoplanowym", stdout)
        self.assertEqual("Operacja nie powiodła się bez ujawniania danych wejściowych.\n", stderr)
        self.assertNotIn("private-canary", stdout + stderr)
        self.assertNotIn("Traceback", stdout + stderr)

    def test_each_lifecycle_reason_has_one_safe_journal_code(self):
        marker_canary = "journal-private-canary\x1b"
        environment = {
            "INVOCATION_ID": marker_canary,
            "JOURNAL_STREAM": marker_canary,
        }
        for reason in LifecycleFailureReason:
            error = WatcherError(
                "exception-private-canary\x1b", lifecycle_reason=reason
            )
            with self.subTest(reason=reason), patch.dict(
                os.environ, environment, clear=True
            ), patch(
                "copypastebin.cli.ClipboardWatcher.run_forever",
                side_effect=error,
            ):
                code, stdout, stderr = self.run_cli(["watch", "start"])
            self.assertEqual(1, code)
            self.assertIn("pierwszoplanowym", stdout)
            self.assertEqual(
                "CopyPasteBin diagnostic code: "
                f"LIFECYCLE_{reason.value}\n"
                "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
                stderr,
            )
            self.assertEqual(1, stderr.count("CopyPasteBin diagnostic code:"))
            self.assertNotIn(marker_canary, stdout + stderr)
            self.assertNotIn("exception-private-canary", stdout + stderr)
            self.assertNotIn("Traceback", stdout + stderr)

    def test_lifecycle_code_requires_both_journal_markers(self):
        reason = LifecycleFailureReason.RUNTIME_DIR_INVALID
        marker_cases = (
            {},
            {"INVOCATION_ID": "present"},
            {"JOURNAL_STREAM": "present"},
            {"INVOCATION_ID": "", "JOURNAL_STREAM": "present"},
            {"INVOCATION_ID": "present", "JOURNAL_STREAM": ""},
        )
        for environment in marker_cases:
            with self.subTest(environment=tuple(environment)), patch.dict(
                os.environ, environment, clear=True
            ), patch(
                "copypastebin.cli.ClipboardWatcher.run_forever",
                side_effect=WatcherError(lifecycle_reason=reason),
            ):
                code, stdout, stderr = self.run_cli(["watch", "start"])
            self.assertEqual(1, code)
            self.assertIn("pierwszoplanowym", stdout)
            self.assertEqual(
                "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
                stderr,
            )

    def test_non_lifecycle_watcher_error_has_no_journal_code(self):
        with patch.dict(
            os.environ,
            {"INVOCATION_ID": "private-canary", "JOURNAL_STREAM": "private-canary"},
            clear=True,
        ), patch(
            "copypastebin.cli.ClipboardWatcher.run_forever",
            side_effect=WatcherError("exception-private-canary"),
        ):
            code, stdout, stderr = self.run_cli(["watch", "start"])
        self.assertEqual(1, code)
        self.assertIn("pierwszoplanowym", stdout)
        self.assertEqual(
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr,
        )
        self.assertNotIn("private-canary", stdout + stderr)

    def test_exhausted_startup_backend_failures_use_fixed_safe_cli_error(self):
        canary = "backend-private-canary\x1b"
        backend = Mock()
        backend.read.side_effect = [
            WatcherBackendError(canary),
            WatcherBackendError(canary),
            WatcherBackendError(canary),
            WatcherBackendError(canary),
            WatcherBackendError(canary),
        ]

        def watcher_factory(_backend, notifier, store, **kwargs):
            return _FastWatcher(
                backend,
                notifier,
                store,
                runtime=_Runtime(),
                **kwargs,
            )

        with patch.dict(
            os.environ,
            {"INVOCATION_ID": "marker-private-canary", "JOURNAL_STREAM": "marker-private-canary"},
            clear=True,
        ), patch("copypastebin.cli.ClipboardWatcher", side_effect=watcher_factory):
            code, stdout, stderr = self.run_cli(["watch", "start"])
        self.assertEqual(1, code)
        self.assertEqual(5, backend.read.call_count)
        self.assertIn("pierwszoplanowym", stdout)
        self.assertEqual(
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_ATTEMPT_1_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_ATTEMPT_2_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_ATTEMPT_3_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_LATE_ATTEMPT_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_LATE_ATTEMPT_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_GRACE_EXHAUSTED\n"
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr,
        )
        self.assertNotIn(canary, stdout + stderr)
        self.assertNotIn("marker-private-canary", stdout + stderr)
        self.assertNotIn("Traceback", stdout + stderr)

    def test_backend_attempt_codes_require_both_journal_markers(self):
        marker_cases = (
            {},
            {"INVOCATION_ID": "present"},
            {"JOURNAL_STREAM": "present"},
            {"INVOCATION_ID": "", "JOURNAL_STREAM": "present"},
            {"INVOCATION_ID": "present", "JOURNAL_STREAM": ""},
        )
        for environment in marker_cases:
            backend = Mock()
            backend.read.side_effect = [
                WatcherBackendError(),
                WatcherBackendError(),
                WatcherBackendError(),
                WatcherBackendError(),
                WatcherBackendError(),
            ]

            def watcher_factory(_backend, notifier, store, **kwargs):
                return _FastWatcher(
                    backend,
                    notifier,
                    store,
                    runtime=_Runtime(),
                    **kwargs,
                )

            with self.subTest(environment=tuple(environment)), patch.dict(
                os.environ, environment, clear=True
            ), patch(
                "copypastebin.cli.ClipboardWatcher", side_effect=watcher_factory
            ):
                code, stdout, stderr = self.run_cli(["watch", "start"])
            self.assertEqual(1, code)
            self.assertEqual(5, backend.read.call_count)
            self.assertIn("pierwszoplanowym", stdout)
            self.assertEqual(
                "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
                stderr,
            )
            self.assertNotIn("BACKEND_STARTUP_", stdout + stderr)

    def test_startup_recovery_preserves_foreground_ctrl_c_contract(self):
        canary = "backend-private-canary\x1b"
        backend = Mock()
        backend.read.side_effect = [
            WatcherBackendError(canary),
            ClipboardSample(ClipboardSampleKind.EMPTY),
            KeyboardInterrupt(),
        ]

        def watcher_factory(_backend, notifier, store, **kwargs):
            return _FastWatcher(
                backend,
                notifier,
                store,
                runtime=_Runtime(),
                **kwargs,
            )

        with patch.dict(os.environ, {}, clear=True), patch(
            "copypastebin.cli.ClipboardWatcher", side_effect=watcher_factory
        ):
            code, stdout, stderr = self.run_cli(["watch", "start"])
        self.assertEqual(0, code)
        self.assertEqual(3, backend.read.call_count)
        self.assertIn("pierwszoplanowym", stdout)
        self.assertIn("Watcher zatrzymany", stdout)
        self.assertEqual("", stderr)
        self.assertNotIn(canary, stdout + stderr)

    def test_background_style_commands_are_not_falsely_advertised(self):
        for action in ("stop", "status"):
            with self.subTest(action=action):
                code, stdout, stderr = self.run_cli(["watch", action])
                self.assertEqual(2, code)
                self.assertEqual("", stdout)
                self.assertNotIn("private", stderr)

    def test_service_commands_are_separate_from_foreground_watcher(self):
        controller = Mock()
        controller.start.return_value = ServiceStatus.RUNNING
        controller.stop.return_value = ServiceStatus.STOPPED
        with patch("copypastebin.cli.ServiceController", return_value=controller):
            code, stdout, stderr = self.run_cli(["service", "setup"])
            self.assertEqual((0, "CopyPasteBin service: CONFIGURED\n", ""), (code, stdout, stderr))
            controller.setup.assert_called_once_with()

            code, stdout, stderr = self.run_cli(["service", "start"])
            self.assertEqual((0, "CopyPasteBin service: RUNNING\n", ""), (code, stdout, stderr))
            controller.start.assert_called_once_with()

            code, stdout, stderr = self.run_cli(["service", "stop"])
            self.assertEqual((0, "CopyPasteBin service: STOPPED\n", ""), (code, stdout, stderr))
            controller.stop.assert_called_once_with()

            controller.enable.return_value = AutostartStatus.ENABLED
            code, stdout, stderr = self.run_cli(["service", "enable"])
            self.assertEqual(
                (0, "CopyPasteBin autostart: ENABLED\n", ""),
                (code, stdout, stderr),
            )
            controller.enable.assert_called_once_with()

            controller.disable.return_value = AutostartStatus.DISABLED
            code, stdout, stderr = self.run_cli(["service", "disable"])
            self.assertEqual(
                (0, "CopyPasteBin autostart: DISABLED\n", ""),
                (code, stdout, stderr),
            )
            controller.disable.assert_called_once_with()

    def test_service_status_has_closed_output_and_is_service_scoped(self):
        for status, expected_code in (
            (ServiceStatus.RUNNING, 0),
            (ServiceStatus.STOPPED, 1),
            (ServiceStatus.FAILED, 1),
            (ServiceStatus.NOT_CONFIGURED, 1),
            (ServiceStatus.UNKNOWN, 1),
        ):
            controller = Mock()
            controller.status.return_value = status
            with self.subTest(status=status), patch(
                "copypastebin.cli.ServiceController", return_value=controller
            ):
                code, stdout, stderr = self.run_cli(["service", "status"])
            self.assertEqual(expected_code, code)
            self.assertEqual(f"CopyPasteBin service: {status.value}\n", stdout)
            self.assertEqual("", stderr)
            self.assertNotIn("foreground", stdout.lower())

    def test_autostart_status_has_closed_output_and_exit_codes(self):
        for status, expected_code in (
            (AutostartStatus.ENABLED, 0),
            (AutostartStatus.DISABLED, 0),
            (AutostartStatus.UNKNOWN, 1),
        ):
            controller = Mock()
            controller.autostart.return_value = status
            with self.subTest(status=status), patch(
                "copypastebin.cli.ServiceController", return_value=controller
            ):
                code, stdout, stderr = self.run_cli(["service", "autostart"])
            self.assertEqual(expected_code, code)
            self.assertEqual(
                f"CopyPasteBin autostart: {status.value}\n", stdout
            )
            self.assertEqual("", stderr)
            self.assertNotIn("Traceback", stdout + stderr)

    def test_service_errors_have_one_public_redacted_cli_path(self):
        canary = "SERVICE_PRIVATE_CANARY\x1b\u202e"
        for action in (
            "setup",
            "start",
            "status",
            "enable",
            "disable",
            "autostart",
        ):
            controller = Mock()
            getattr(controller, action).side_effect = ServiceError(canary)
            with self.subTest(action=action), patch(
                "copypastebin.cli.ServiceController", return_value=controller
            ):
                code, stdout, stderr = self.run_cli(["service", action])
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
