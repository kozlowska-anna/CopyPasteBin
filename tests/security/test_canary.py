import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin import cli
from copypastebin.application import inspect_and_record
from copypastebin.bridge import observe_framed_event
from copypastebin.clipboard import ClipboardError
from copypastebin.filters import FilterError, FilterStore
from copypastebin.history import HistoryStore
from copypastebin.models import Category
from copypastebin.lifecycle import LifecycleError, LifecycleFailureReason
from copypastebin.launcher import LauncherController, LauncherError
from copypastebin.models import AnalysisResult, Detection
from copypastebin.pause import PAUSE_30_MINUTES, PauseError, PauseStore
from copypastebin.service import ServiceController, ServiceStatus
from copypastebin.detection import analyze_text
from copypastebin.ui import UiError, detections_json, history_json, redacted_suggestion
from copypastebin.watcher import (
    ClipboardSample,
    ClipboardSampleKind,
    ClipboardWatcher,
    WatcherError,
)


class CanaryTests(unittest.TestCase):
    def test_editor_canary_absent_from_suggestion_history_and_errors(self):
        canary = "EDITOR_PRIVATE_CANARY\x1b\u202e"
        text = "password=" + canary
        with tempfile.TemporaryDirectory() as directory:
            history = HistoryStore(Path(directory) / "state")
            inspect_and_record(
                text,
                source_kind="clipboard_event",
                purpose="other",
                history=history,
            )
            rendered = (
                history_json(history)
                + redacted_suggestion(text)
                + detections_json(analyze_text(text))
            )
            error = UiError()
            rendered += str(error) + repr(error)
            self.assertNotIn(canary, rendered)
            for path in history.state_dir.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_event_bridge_canary_absent_from_history_result_and_repr(self):
        canary = "EVENT_BRIDGE_PRIVATE_CANARY\x1b\u202e"
        app = b"org.mozilla.firefox"
        payload = len(app).to_bytes(4, "big") + app + ("password=" + canary).encode()

        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            history = HistoryStore(state)
            result = observe_framed_event(
                io.BytesIO(payload),
                history=history,
                pause=PauseStore(state),
            )
            rendered = repr(history.recent()) + repr(result)
            self.assertNotIn(canary, rendered)
            for path in state.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_pause_state_contains_no_clipboard_canary_and_errors_are_redacted(self):
        canary = "PAUSE_CLIPBOARD_PRIVATE_CANARY\x1b\u202e"
        with tempfile.TemporaryDirectory() as directory:
            store = PauseStore(Path(directory) / "state", clock=lambda: 2_000_000_000)
            store.pause_for(PAUSE_30_MINUTES)
            self.assertNotIn(canary.encode(), store.state_path.read_bytes())
            store.state_path.write_text(canary, encoding="utf-8")
            store.state_path.chmod(0o600)
            with self.assertRaises(PauseError) as caught:
                store.status()
            self.assertNotIn(canary, str(caught.exception) + repr(caught.exception))

    def test_filter_state_contains_no_clipboard_canary_and_errors_are_redacted(self):
        canary = "FILTER_CLIPBOARD_PRIVATE_CANARY\x1b\u202e"
        with tempfile.TemporaryDirectory() as directory:
            store = FilterStore(Path(directory) / "state")
            store.set_enabled(Category.HOME_PATH, False)
            store.set_auto_clear(60)
            self.assertNotIn(canary.encode(), store.state_path.read_bytes())
            store.state_path.write_text(canary, encoding="utf-8")
            store.state_path.chmod(0o600)
            with self.assertRaises(FilterError) as caught:
                store.status()
            self.assertNotIn(canary, str(caught.exception) + repr(caught.exception))

    def test_canary_absent_from_history_repr_and_files(self):
        canary = "SYNTHETIC_PRIVATE_CANARY\x1b\u202e"
        text = "password=" + canary
        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "state")
            operation = inspect_and_record(text, source_kind="stdin", purpose="chat", history=store)
            entry = store.get(operation.operation_id)
            combined = repr(operation) + repr(operation.analysis) + repr(operation.analysis.detections) + repr(entry)
            self.assertNotIn(canary, combined)
            for path in store.state_dir.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_detection_repr_does_not_expose_positions_or_input(self):
        canary = "SYNTHETIC_PRIVATE_CANARY"
        operation_text = "password=" + canary
        with tempfile.TemporaryDirectory() as directory:
            result = inspect_and_record(operation_text, source_kind="stdin", purpose="chat", history=HistoryStore(Path(directory) / "state"))
        self.assertNotIn(canary, repr(result.analysis.detections[0]))
        self.assertNotIn("start=", repr(result.analysis.detections[0]))

    def test_watcher_canary_absent_from_notification_history_and_repr(self):
        canary = "WATCHER_PRIVATE_CANARY\x1b\u202e"

        class Backend:
            def read(self):
                return ClipboardSample(ClipboardSampleKind.TEXT, "password=" + canary)

        class Notifier:
            def __init__(self):
                self.received = []

            def notify(self, notification):
                self.received.append(notification)

        with tempfile.TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "state")
            notifier = Notifier()
            watcher = ClipboardWatcher(Backend(), notifier, store, deduplication_key=b"c" * 32)
            watcher.start()
            watcher.poll_once()
            combined = repr(notifier.received) + repr(store.recent()) + repr(watcher)
            self.assertNotIn(canary, combined)
            for path in store.state_dir.iterdir():
                if path.is_file():
                    self.assertNotIn(canary.encode(), path.read_bytes())

    def test_lifecycle_canary_absent_from_unit_status_errors_and_repr(self):
        canary = "LIFECYCLE_PRIVATE_CANARY\x1b\u202e"
        with tempfile.TemporaryDirectory() as directory:
            entry_point = Path(directory) / "cpb"
            entry_point.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            entry_point.chmod(0o700)
            controller = ServiceController(
                unit_dir=Path(directory) / "systemd/user",
                entry_point=entry_point,
            )
            with patch.object(
                ServiceController, "_run_systemctl", return_value=(0, b"")
            ):
                controller.setup()
            self.assertNotIn(canary, controller.unit_path.read_text(encoding="utf-8"))
            unsafe_status = (
                "LoadState=loaded\nActiveState=active\nSubState="
                + canary
                + "\n"
            ).encode("utf-8")
            with patch.object(
                ServiceController,
                "_run_systemctl",
                return_value=(0, unsafe_status),
            ):
                status = controller.status()
            combined = repr(controller) + repr(status) + status.value
            self.assertEqual(ServiceStatus.UNKNOWN, status)
            self.assertNotIn(canary, combined)

    def test_launcher_canary_absent_from_file_errors_and_repr(self):
        canary = "LAUNCHER_PRIVATE_CANARY\x1b\u202e"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry_point = root / "bin" / "cpb"
            entry_point.parent.mkdir()
            entry_point.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            entry_point.chmod(0o700)
            controller = LauncherController(
                application_dir=root / "share" / "applications",
                entry_point=entry_point,
            )
            controller.setup()
            content = controller.launcher_path.read_text(encoding="utf-8")
            self.assertNotIn(canary, content)
            self.assertNotIn(canary, repr(controller))

            foreign = controller.launcher_path
            foreign.write_text(canary, encoding="utf-8")
            foreign.chmod(0o600)
            with self.assertRaises(LauncherError) as caught:
                controller.setup()
            rendered = str(caught.exception) + repr(caught.exception)
            self.assertNotIn(canary, rendered)
            self.assertEqual(canary, foreign.read_text(encoding="utf-8"))

    def test_lifecycle_reason_journal_code_contains_no_canary_or_clipboard_read(self):
        canary = "LIFECYCLE_JOURNAL_PRIVATE_CANARY\x1b\u202e"
        reason = LifecycleFailureReason.RUNTIME_DIR_INVALID
        try:
            raise OSError(canary)
        except OSError as cause:
            lifecycle_error = LifecycleError(reason)
            lifecycle_error.__cause__ = cause
        watcher_error = WatcherError(canary, lifecycle_reason=reason)
        watcher_error.__cause__ = lifecycle_error
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"INVOCATION_ID": canary, "JOURNAL_STREAM": canary},
            clear=True,
        ), patch(
            "copypastebin.cli.ClipboardWatcher.run_forever",
            side_effect=watcher_error,
        ), patch(
            "copypastebin.clipboard.read_clipboard"
        ) as read_clipboard:
            code = cli.main(
                [
                    "--state-dir",
                    str(Path(directory) / "state"),
                    "--config",
                    str(Path(directory) / "private-canary-missing.toml"),
                    "watch",
                    "start",
                ],
                stdout=stdout,
                stderr=stderr,
            )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(1, code)
        self.assertEqual(
            "CopyPasteBin diagnostic code: LIFECYCLE_RUNTIME_DIR_INVALID\n"
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr.getvalue(),
        )
        self.assertNotIn(canary, combined)
        self.assertNotIn("private-canary", combined)
        self.assertNotIn("Traceback", combined)
        read_clipboard.assert_not_called()

    def test_backend_attempt_codes_publish_no_exception_marker_or_stderr_canary(self):
        clipboard_canary = "CLIPBOARD_ERROR_PRIVATE_CANARY\x1b\u202e"
        cause_canary = "CHAINED_CAUSE_PRIVATE_CANARY\x1b\u202e"
        marker_canary = "JOURNAL_MARKER_PRIVATE_CANARY\x1b\u202e"
        backend_stderr_canary = "BACKEND_STDERR_PRIVATE_CANARY\x1b\u202e"
        mime_canary = "MIME_PRIVATE_CANARY/type"
        path_canary = "/private/path/canary"
        errno_canary = 12345

        def backend_error():
            cause = subprocess.CalledProcessError(
                7,
                ["fake-backend-private-argv"],
                stderr=backend_stderr_canary.encode(),
            )
            error = ClipboardError(clipboard_canary)
            error.__cause__ = OSError(
                errno_canary, cause_canary + mime_canary, path_canary
            )
            error.__context__ = cause
            return error

        class Runtime:
            def __enter__(self):
                return self

            def __exit__(self, exception_type, exception, traceback):
                return None

        class FastWatcher(ClipboardWatcher):
            def run_forever(self, **kwargs):
                return super().run_forever(sleep=lambda _: None, **kwargs)

        def watcher_factory(backend, notifier, store, **kwargs):
            return FastWatcher(
                backend,
                notifier,
                store,
                runtime=Runtime(),
                **kwargs,
            )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"INVOCATION_ID": marker_canary, "JOURNAL_STREAM": marker_canary},
            clear=True,
        ), patch(
            "copypastebin.cli.ClipboardWatcher", side_effect=watcher_factory
        ), patch(
            "copypastebin.watcher.read_clipboard",
            side_effect=[backend_error() for _ in range(5)],
        ) as read_clipboard:
            code = cli.main(
                [
                    "--state-dir",
                    str(Path(directory) / "state"),
                    "--config",
                    str(Path(directory) / "private-canary-missing.toml"),
                    "watch",
                    "start",
                ],
                stdout=stdout,
                stderr=stderr,
            )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(1, code)
        self.assertEqual(5, read_clipboard.call_count)
        self.assertEqual(
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_ATTEMPT_1_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_ATTEMPT_2_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_ATTEMPT_3_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_LATE_ATTEMPT_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_LATE_ATTEMPT_FAILED\n"
            "CopyPasteBin diagnostic code: BACKEND_STARTUP_GRACE_EXHAUSTED\n"
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr.getvalue(),
        )
        for private_value in (
            clipboard_canary,
            cause_canary,
            marker_canary,
            backend_stderr_canary,
            "fake-backend-private-argv",
            mime_canary,
            path_canary,
            str(errno_canary),
        ):
            self.assertNotIn(private_value, combined)
        self.assertNotIn("Traceback", combined)
