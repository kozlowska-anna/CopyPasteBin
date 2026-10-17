import ast
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin.history import HistoryStore
from copypastebin.lifecycle import LifecycleError, LifecycleFailureReason
from copypastebin.models import RiskLevel
from copypastebin.notifications import DesktopNotifier, NotificationError, SafeNotification
from copypastebin.watcher import (
    BackendStartupFailureCode,
    ClipboardSample,
    ClipboardSampleKind,
    ClipboardWatcher,
    WatchCycleOutcome,
    WatcherBackendError,
    WatcherError,
    WatcherState,
    WlPastePollingBackend,
)


class _Backend:
    def __init__(self, *samples):
        self.samples = list(samples)
        self.read_count = 0

    def read(self):
        self.read_count += 1
        value = self.samples.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class _Notifier:
    def __init__(self):
        self.notifications = []

    def notify(self, notification):
        self.notifications.append(notification)


class _Runtime:
    def __init__(self, failure=None):
        self.failure = failure

    def __enter__(self):
        if self.failure is not None:
            raise self.failure
        return self

    def __exit__(self, exception_type, exception, traceback):
        return None


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def watcher(self, backend, notifier=None, runtime=None):
        return ClipboardWatcher(
            backend,
            notifier or _Notifier(),
            HistoryStore(self.state),
            deduplication_key=b"d" * 32,
            runtime=runtime or _Runtime(),
        )

    def test_safe_warning_and_high_use_core_and_notify_only_when_required(self):
        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.TEXT, "ordinary text"),
            ClipboardSample(ClipboardSampleKind.TEXT, "1234 PLN"),
            ClipboardSample(ClipboardSampleKind.TEXT, "password=synthetic-only"),
        )
        notifier = _Notifier()
        watcher = self.watcher(backend, notifier)
        watcher.start()
        self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        self.assertEqual([], notifier.notifications)
        self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        self.assertEqual(RiskLevel.LOW, notifier.notifications[-1].risk)
        self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        self.assertEqual(RiskLevel.HIGH, notifier.notifications[-1].risk)
        entries = HistoryStore(self.state).recent()
        self.assertEqual(3, len(entries))
        self.assertEqual("clipboard_watcher", entries[0].source_kind)

    def test_consecutive_duplicate_is_skipped_but_changed_text_is_analyzed(self):
        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.TEXT, "person@example.com"),
            ClipboardSample(ClipboardSampleKind.TEXT, "person@example.com"),
            ClipboardSample(ClipboardSampleKind.TEXT, "other@example.com"),
        )
        watcher = self.watcher(backend)
        watcher.start()
        self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        self.assertEqual(WatchCycleOutcome.DUPLICATE, watcher.poll_once())
        self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        self.assertEqual(2, len(HistoryStore(self.state).recent()))

    def test_nonconsecutive_duplicate_uses_existing_history_hmac_relation(self):
        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.TEXT, "person@example.com"),
            ClipboardSample(ClipboardSampleKind.TEXT, "other@example.com"),
            ClipboardSample(ClipboardSampleKind.TEXT, "person@example.com"),
        )
        watcher = self.watcher(backend)
        watcher.start()
        for _ in range(3):
            self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        entries = HistoryStore(self.state).recent()
        self.assertEqual(entries[2].operation_id, entries[0].duplicate_of)

    def test_empty_and_non_text_are_skipped_without_history(self):
        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.EMPTY),
            ClipboardSample(ClipboardSampleKind.NON_TEXT),
        )
        watcher = self.watcher(backend)
        watcher.start()
        self.assertEqual(WatchCycleOutcome.EMPTY, watcher.poll_once())
        self.assertEqual(WatchCycleOutcome.NON_TEXT, watcher.poll_once())
        self.assertFalse(self.state.exists())

    def test_empty_marker_cannot_hide_text_with_the_same_word(self):
        watcher = self.watcher(
            _Backend(
                ClipboardSample(ClipboardSampleKind.EMPTY),
                ClipboardSample(ClipboardSampleKind.TEXT, "empty"),
            )
        )
        watcher.start()
        self.assertEqual(WatchCycleOutcome.EMPTY, watcher.poll_once())
        self.assertEqual(WatchCycleOutcome.ANALYZED, watcher.poll_once())
        self.assertEqual(1, len(HistoryStore(self.state).recent()))

    def test_backend_error_is_redacted_and_does_not_publish_partial_result(self):
        watcher = self.watcher(_Backend(WatcherError("private-canary\x1b")))
        watcher.start()
        with self.assertRaises(WatcherError) as caught:
            watcher.poll_once()
        rendered = str(caught.exception) + repr(caught.exception)
        self.assertNotIn("private-canary", rendered)
        self.assertNotIn("\x1b", rendered)
        self.assertFalse(self.state.exists())

    def test_lifecycle_is_explicit_and_run_forever_stops_on_error(self):
        watcher = self.watcher(_Backend(WatcherError()))
        self.assertEqual(WatcherState.STOPPED, watcher.state)
        with self.assertRaises(WatcherError):
            watcher.poll_once()
        with self.assertRaises(WatcherError):
            watcher.run_forever(poll_interval=0.01, sleep=lambda _: None)
        self.assertEqual(WatcherState.STOPPED, watcher.state)

    def test_each_startup_attempt_can_recover_with_exact_codes_and_backoff(self):
        cases = (
            (1, [], []),
            (
                2,
                [1.0],
                [BackendStartupFailureCode.ATTEMPT_1_FAILED],
            ),
            (
                3,
                [1.0, 2.0],
                [
                    BackendStartupFailureCode.ATTEMPT_1_FAILED,
                    BackendStartupFailureCode.ATTEMPT_2_FAILED,
                ],
            ),
            (
                4,
                [1.0, 2.0, 4.0],
                [
                    BackendStartupFailureCode.ATTEMPT_1_FAILED,
                    BackendStartupFailureCode.ATTEMPT_2_FAILED,
                    BackendStartupFailureCode.ATTEMPT_3_FAILED,
                ],
            ),
            (
                5,
                [1.0, 2.0, 4.0, 8.0],
                [
                    BackendStartupFailureCode.ATTEMPT_1_FAILED,
                    BackendStartupFailureCode.ATTEMPT_2_FAILED,
                    BackendStartupFailureCode.ATTEMPT_3_FAILED,
                    BackendStartupFailureCode.LATE_ATTEMPT_FAILED,
                ],
            ),
        )
        for attempt, expected_sleeps, expected_codes in cases:
            with self.subTest(attempt=attempt):
                backend = _Backend(
                    *([WatcherBackendError()] * (attempt - 1)),
                    ClipboardSample(
                        ClipboardSampleKind.TEXT, "synthetic recovery"
                    ),
                )
                watcher = self.watcher(backend)
                sleeps = []
                codes = []
                with patch(
                    "copypastebin.watcher.inspect_and_record",
                    side_effect=RuntimeError("synthetic application stop"),
                ) as inspect:
                    with self.assertRaises(RuntimeError):
                        watcher.run_forever(
                            poll_interval=0.25,
                            sleep=sleeps.append,
                            startup_backend_failure=codes.append,
                        )
                self.assertEqual(expected_sleeps, sleeps)
                self.assertEqual(expected_codes, codes)
                self.assertEqual(attempt, backend.read_count)
                inspect.assert_called_once()
                self.assertEqual(WatcherState.STOPPED, watcher.state)

    def test_only_startup_backend_error_is_retried(self):
        backend = _Backend(
            WatcherBackendError(),
            ClipboardSample(ClipboardSampleKind.EMPTY),
            WatcherBackendError(),
        )
        watcher = self.watcher(backend)
        sleeps = []
        codes = []
        with self.assertRaises(WatcherBackendError):
            watcher.run_forever(
                poll_interval=0.25,
                sleep=sleeps.append,
                startup_backend_failure=codes.append,
            )
        self.assertEqual([1.0, 0.25], sleeps)
        self.assertEqual(
            [BackendStartupFailureCode.ATTEMPT_1_FAILED], codes
        )
        self.assertEqual(3, backend.read_count)
        self.assertEqual(WatcherState.STOPPED, watcher.state)

    def test_five_startup_backend_errors_exhaust_bounded_grace(self):
        backend = _Backend(
            WatcherBackendError(),
            WatcherBackendError(),
            WatcherBackendError(),
            WatcherBackendError(),
            WatcherBackendError(),
            ClipboardSample(ClipboardSampleKind.EMPTY),
        )
        watcher = self.watcher(backend)
        sleeps = []
        codes = []
        with self.assertRaises(WatcherBackendError):
            watcher.run_forever(
                poll_interval=0.25,
                sleep=sleeps.append,
                startup_backend_failure=codes.append,
            )
        self.assertEqual([1.0, 2.0, 4.0, 8.0], sleeps)
        self.assertEqual(
            [
                BackendStartupFailureCode.ATTEMPT_1_FAILED,
                BackendStartupFailureCode.ATTEMPT_2_FAILED,
                BackendStartupFailureCode.ATTEMPT_3_FAILED,
                BackendStartupFailureCode.LATE_ATTEMPT_FAILED,
                BackendStartupFailureCode.LATE_ATTEMPT_FAILED,
                BackendStartupFailureCode.GRACE_EXHAUSTED,
            ],
            codes,
        )
        self.assertEqual(5, backend.read_count)
        self.assertEqual(WatcherState.STOPPED, watcher.state)
        self.assertFalse(self.state.exists())

    def test_generic_watcher_error_is_not_retried_during_startup(self):
        backend = _Backend(WatcherError("private-canary"))
        watcher = self.watcher(backend)
        sleeps = []
        codes = []
        with self.assertRaises(WatcherError):
            watcher.run_forever(
                poll_interval=0.25,
                sleep=sleeps.append,
                startup_backend_failure=codes.append,
            )
        self.assertEqual([], sleeps)
        self.assertEqual([], codes)
        self.assertEqual(1, backend.read_count)

    def test_lifecycle_failure_is_not_retried_or_read(self):
        backend = _Backend(ClipboardSample(ClipboardSampleKind.EMPTY))
        reason = LifecycleFailureReason.WAYLAND_DISPLAY_INVALID
        watcher = self.watcher(
            backend, runtime=_Runtime(LifecycleError(reason))
        )
        sleeps = []
        codes = []
        with self.assertRaises(WatcherError) as caught:
            watcher.run_forever(
                poll_interval=0.25,
                sleep=sleeps.append,
                startup_backend_failure=codes.append,
            )
        self.assertIs(reason, caught.exception.lifecycle_reason)
        self.assertEqual([], sleeps)
        self.assertEqual([], codes)
        self.assertEqual(0, backend.read_count)
        self.assertEqual(WatcherState.STOPPED, watcher.state)

    def test_first_poll_success_emits_no_startup_failure_code(self):
        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.EMPTY), KeyboardInterrupt()
        )
        watcher = self.watcher(backend)
        sleeps = []
        codes = []
        with self.assertRaises(KeyboardInterrupt):
            watcher.run_forever(
                poll_interval=0.25,
                sleep=sleeps.append,
                startup_backend_failure=codes.append,
            )
        self.assertEqual([0.25], sleeps)
        self.assertEqual([], codes)
        self.assertEqual(2, backend.read_count)

    def test_steady_state_backend_error_emits_no_startup_failure_code(self):
        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.EMPTY), WatcherBackendError()
        )
        watcher = self.watcher(backend)
        sleeps = []
        codes = []
        with self.assertRaises(WatcherBackendError):
            watcher.run_forever(
                poll_interval=0.25,
                sleep=sleeps.append,
                startup_backend_failure=codes.append,
            )
        self.assertEqual([0.25], sleeps)
        self.assertEqual([], codes)
        self.assertEqual(2, backend.read_count)

    def test_backend_startup_failure_codes_are_closed_allowlist(self):
        self.assertEqual(
            {
                "BACKEND_STARTUP_ATTEMPT_1_FAILED",
                "BACKEND_STARTUP_ATTEMPT_2_FAILED",
                "BACKEND_STARTUP_ATTEMPT_3_FAILED",
                "BACKEND_STARTUP_LATE_ATTEMPT_FAILED",
                "BACKEND_STARTUP_GRACE_EXHAUSTED",
            },
            {code.value for code in BackendStartupFailureCode},
        )

    def test_watcher_error_reason_is_typed_read_only_and_redacted(self):
        reason = LifecycleFailureReason.LOCK_BUSY
        error = WatcherError("private-canary", lifecycle_reason=reason)
        self.assertIs(reason, error.lifecycle_reason)
        self.assertEqual(
            "Watcher schowka zatrzymał się bez ujawniania danych.", str(error)
        )
        self.assertEqual("WatcherError(redacted=True)", repr(error))
        self.assertNotIn("private-canary", str(error) + repr(error))
        with self.assertRaises(AttributeError):
            error.lifecycle_reason = LifecycleFailureReason.RUNTIME_DIR_INVALID
        with self.assertRaises(TypeError):
            WatcherError(lifecycle_reason="LOCK_BUSY")

    def test_non_lifecycle_watcher_errors_have_no_lifecycle_reason(self):
        self.assertIsNone(WatcherError().lifecycle_reason)
        self.assertIsNone(WatcherBackendError().lifecycle_reason)

    def test_notification_failure_is_not_retried_during_startup(self):
        class FailingNotifier:
            def notify(self, notification):
                raise NotificationError("private-canary")

        backend = _Backend(
            ClipboardSample(ClipboardSampleKind.TEXT, "1234 PLN")
        )
        watcher = self.watcher(backend, FailingNotifier())
        sleeps = []
        with self.assertRaises(NotificationError):
            watcher.run_forever(poll_interval=0.25, sleep=sleeps.append)
        self.assertEqual([], sleeps)
        self.assertEqual(1, backend.read_count)
        self.assertEqual(WatcherState.STOPPED, watcher.state)

    def test_empty_and_non_text_end_startup_grace(self):
        for kind in (ClipboardSampleKind.EMPTY, ClipboardSampleKind.NON_TEXT):
            with self.subTest(kind=kind):
                backend = _Backend(
                    ClipboardSample(kind),
                    WatcherBackendError(),
                )
                watcher = self.watcher(backend)
                sleeps = []
                with self.assertRaises(WatcherBackendError):
                    watcher.run_forever(poll_interval=0.25, sleep=sleeps.append)
                self.assertEqual([0.25], sleeps)
                self.assertEqual(2, backend.read_count)

    def test_keyboard_interrupt_during_startup_backoff_cleans_up(self):
        backend = _Backend(WatcherBackendError())
        watcher = self.watcher(backend)

        def interrupt(delay):
            self.assertEqual(1.0, delay)
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            watcher.run_forever(poll_interval=0.25, sleep=interrupt)
        self.assertEqual(1, backend.read_count)
        self.assertEqual(WatcherState.STOPPED, watcher.state)

    def test_wl_backend_uses_one_text_read_for_text_and_empty(self):
        backend = WlPastePollingBackend()
        with patch("copypastebin.watcher.read_clipboard", return_value="") as reader:
            self.assertEqual(ClipboardSample(ClipboardSampleKind.EMPTY), backend.read())
            reader.assert_called_once_with()
        with patch("copypastebin.watcher.read_clipboard", return_value="hello") as reader:
            self.assertEqual(ClipboardSample(ClipboardSampleKind.TEXT, "hello"), backend.read())
            reader.assert_called_once_with()

    def test_wl_backend_cannot_guess_non_text_and_fails_closed(self):
        from copypastebin.clipboard import ClipboardError

        with patch(
            "copypastebin.watcher.read_clipboard",
            side_effect=ClipboardError("private-canary\x1b"),
        ) as reader:
            with self.assertRaises(WatcherBackendError) as caught:
                WlPastePollingBackend().read()
        reader.assert_called_once_with()
        rendered = str(caught.exception) + repr(caught.exception)
        self.assertNotIn("private-canary", rendered)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("stderr", rendered)

    def test_notification_contains_only_safe_metadata_and_fixed_command_shape(self):
        notification = SafeNotification(RiskLevel.WARNING, (("EMAIL", 1),))
        self.assertNotIn("person@example.com", repr(notification))
        with patch("copypastebin.notifications.shutil.which", return_value="/usr/bin/notify-send"), patch("copypastebin.notifications.subprocess.run") as run:
            run.return_value.returncode = 0
            DesktopNotifier().notify(notification)
        argv = run.call_args.args[0]
        self.assertEqual(
            [
                "/usr/bin/notify-send",
                "--app-name",
                "CopyPasteBin",
                "CopyPasteBin: ryzyko medium",
                "Wykryte kategorie: 1; trafienia: 1. "
                "Sprawdź bieżący schowek jawnie w CopyPasteBin.",
            ],
            argv,
        )
        self.assertNotIn("person@example.com", " ".join(argv))
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertNotIn("input", run.call_args.kwargs)
        self.assertIs(subprocess.DEVNULL, run.call_args.kwargs["stdin"])
        self.assertIs(subprocess.DEVNULL, run.call_args.kwargs["stdout"])
        self.assertIs(subprocess.DEVNULL, run.call_args.kwargs["stderr"])
        with self.assertRaises(NotificationError):
            SafeNotification(RiskLevel.WARNING, [("EMAIL", 1)])

    def test_notification_timeout_and_nonzero_exit_are_redacted(self):
        notification = SafeNotification(RiskLevel.HIGH, (("TOKEN", 1),))
        failures = (
            subprocess.TimeoutExpired(
                ["notify-send", "private-canary"], 0.01, stderr=b"private-canary"
            ),
            subprocess.SubprocessError("private-canary\x1b"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch(
                "copypastebin.notifications.shutil.which",
                return_value="/usr/bin/notify-send",
            ), patch(
                "copypastebin.notifications.subprocess.run", side_effect=failure
            ):
                with self.assertRaises(NotificationError) as caught:
                    DesktopNotifier().notify(notification)
            rendered = str(caught.exception) + repr(caught.exception)
            self.assertNotIn("private-canary", rendered)
            self.assertNotIn("\x1b", rendered)

        with patch(
            "copypastebin.notifications.shutil.which",
            return_value="/usr/bin/notify-send",
        ), patch("copypastebin.notifications.subprocess.run") as run:
            run.return_value.returncode = 7
            with self.assertRaises(NotificationError):
                DesktopNotifier().notify(notification)

    def test_notification_failure_is_redacted(self):
        with patch("copypastebin.notifications.shutil.which", return_value=None):
            with self.assertRaises(NotificationError) as caught:
                DesktopNotifier().notify(SafeNotification(RiskLevel.HIGH, (("TOKEN", 1),)))
        self.assertEqual("Nie udało się bezpiecznie wyświetlić powiadomienia.", str(caught.exception))

    def test_notification_failure_stops_watcher_and_marks_history_failed(self):
        class FailingNotifier:
            def notify(self, notification):
                raise NotificationError("private-canary")

        watcher = self.watcher(
            _Backend(ClipboardSample(ClipboardSampleKind.TEXT, "1234 PLN")),
            FailingNotifier(),
        )
        watcher.start()
        with self.assertRaises(NotificationError):
            watcher.poll_once()
        self.assertEqual("failed", HistoryStore(self.state).recent()[0].status)
        self.assertEqual(WatcherState.STOPPED, watcher.state)
        with self.assertRaises(WatcherError):
            watcher.poll_once()
        watcher.start()
        self.assertEqual(WatcherState.RUNNING, watcher.state)
        watcher.stop()

    def test_watcher_hmac_context_is_random_per_instance_and_not_exposed(self):
        first = ClipboardWatcher(_Backend(), _Notifier(), HistoryStore(self.state))
        second = ClipboardWatcher(_Backend(), _Notifier(), HistoryStore(self.state))

        self.assertNotEqual(first._deduplication_key, second._deduplication_key)
        for watcher in (first, second):
            rendered = repr(watcher) + str(watcher)
            self.assertNotIn(watcher._deduplication_key.hex(), rendered)
            self.assertNotIn(repr(watcher._deduplication_key), rendered)
            self.assertIsNone(watcher._last_fingerprint)

    def test_watcher_does_not_execute_input_or_import_network(self):
        source_paths = (
            Path(__file__).parents[2] / "src/copypastebin/watcher.py",
            Path(__file__).parents[2] / "src/copypastebin/notifications.py",
            Path(__file__).parents[2] / "src/copypastebin/lifecycle.py",
            Path(__file__).parents[2] / "src/copypastebin/service.py",
        )
        forbidden_imports = {"socket", "urllib", "http", "requests"}
        for path in source_paths:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported = {
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            self.assertFalse(imported & forbidden_imports)
            if path.name == "watcher.py":
                self.assertNotIn("write_clipboard", source)
                self.assertNotIn("read_clipboard_types", source)
            self.assertNotIn("shell=True", source)
            self.assertNotIn("os.system", source)
            self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"} for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
