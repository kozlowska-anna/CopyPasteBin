import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin.history import HistoryStore
from copypastebin.lifecycle import (
    LifecycleError,
    LifecycleFailureReason,
    WatcherInstanceLock,
    WatcherRuntime,
    validate_watcher_environment,
)
from copypastebin.watcher import ClipboardWatcher, WatcherError


class _Backend:
    def __init__(self):
        self.read_count = 0

    def read(self):
        self.read_count += 1
        raise WatcherError()


class _Notifier:
    def notify(self, notification):
        raise AssertionError("notification is not expected")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(mode=0o700)
        self.runtime.chmod(0o700)
        self.environment = {
            "XDG_SESSION_TYPE": "wayland",
            "WAYLAND_DISPLAY": "wayland-test",
            "XDG_RUNTIME_DIR": str(self.runtime),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=synthetic",
        }
        self.lookups = []

    def tearDown(self):
        self.temporary.cleanup()

    def which(self, name):
        self.lookups.append(name)
        return "/usr/bin/" + name

    def runtime_guard(self):
        return WatcherRuntime(environ=self.environment, which=self.which)

    def assert_reason(self, expected, callable):
        with self.assertRaises(LifecycleError) as caught:
            callable()
        self.assertIs(expected, caught.exception.reason)
        return caught.exception

    def test_reason_taxonomy_is_exact_and_closed(self):
        self.assertEqual(
            {
                "RUNTIME_REENTRY",
                "SESSION_NOT_WAYLAND",
                "WAYLAND_DISPLAY_INVALID",
                "XDG_RUNTIME_DIR_ENV_INVALID",
                "DBUS_SESSION_BUS_ADDRESS_INVALID",
                "WL_PASTE_UNAVAILABLE",
                "NOTIFY_SEND_UNAVAILABLE",
                "RUNTIME_DIR_INVALID",
                "LOCK_REENTRY",
                "LOCK_DIR_CREATE_FAILURE",
                "LOCK_DIR_INVALID",
                "LOCK_FILE_OPEN_FAILURE",
                "LOCK_FILE_METADATA_FAILURE",
                "LOCK_FILE_INVALID",
                "LOCK_BUSY",
                "LOCK_ACQUIRE_FAILURE",
                "LOCK_RELEASE_FAILURE",
            },
            {reason.value for reason in LifecycleFailureReason},
        )
        self.assertEqual(17, len(LifecycleFailureReason))

    def test_lifecycle_error_requires_typed_reason_and_stays_redacted(self):
        for invalid in (None, "SESSION_NOT_WAYLAND", object()):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(
                TypeError
            ):
                LifecycleError(invalid)
        error = LifecycleError(LifecycleFailureReason.SESSION_NOT_WAYLAND)
        self.assertEqual(
            "Nie udało się bezpiecznie uruchomić watchera.", str(error)
        )
        self.assertEqual("LifecycleError(redacted=True)", repr(error))
        with self.assertRaises(AttributeError):
            error.reason = LifecycleFailureReason.LOCK_BUSY

    def test_wayland_preflight_is_metadata_only(self):
        with patch("copypastebin.clipboard.read_clipboard") as read_clipboard:
            selected = validate_watcher_environment(
                environ=self.environment, which=self.which
            )
        self.assertEqual(self.runtime, selected)
        self.assertEqual(["wl-paste", "notify-send"], self.lookups)
        read_clipboard.assert_not_called()

    def test_session_predicates_have_exact_reasons(self):
        cases = (
            ("XDG_SESSION_TYPE", LifecycleFailureReason.SESSION_NOT_WAYLAND),
            ("WAYLAND_DISPLAY", LifecycleFailureReason.WAYLAND_DISPLAY_INVALID),
            (
                "XDG_RUNTIME_DIR",
                LifecycleFailureReason.XDG_RUNTIME_DIR_ENV_INVALID,
            ),
            (
                "DBUS_SESSION_BUS_ADDRESS",
                LifecycleFailureReason.DBUS_SESSION_BUS_ADDRESS_INVALID,
            ),
        )
        for name, expected in cases:
            for invalid in (None, "", "invalid\x00value"):
                with self.subTest(name=name, invalid=invalid):
                    environment = dict(self.environment)
                    if invalid is None:
                        environment.pop(name)
                    else:
                        environment[name] = invalid
                    self.assert_reason(
                        expected,
                        lambda environment=environment: validate_watcher_environment(
                            environ=environment, which=self.which
                        ),
                    )
        environment = dict(self.environment)
        environment["XDG_SESSION_TYPE"] = "x11"
        self.assert_reason(
            LifecycleFailureReason.SESSION_NOT_WAYLAND,
            lambda: validate_watcher_environment(
                environ=environment, which=self.which
            ),
        )

    def test_executable_lookup_predicates_have_exact_reasons(self):
        cases = (
            ("wl-paste", LifecycleFailureReason.WL_PASTE_UNAVAILABLE),
            ("notify-send", LifecycleFailureReason.NOTIFY_SEND_UNAVAILABLE),
        )
        for missing, expected in cases:
            calls = []

            def which(name):
                calls.append(name)
                return None if name == missing else "/usr/bin/" + name

            with self.subTest(missing=missing):
                self.assert_reason(
                    expected,
                    lambda: validate_watcher_environment(
                        environ=self.environment, which=which
                    ),
                )
            self.assertLessEqual(len(calls), 2)

    def test_runtime_directory_invalid_variants_have_one_safe_reason(self):
        relative = dict(self.environment)
        relative["XDG_RUNTIME_DIR"] = "relative-private-canary"
        self.assert_reason(
            LifecycleFailureReason.RUNTIME_DIR_INVALID,
            lambda: validate_watcher_environment(environ=relative, which=self.which),
        )

        missing = dict(self.environment)
        missing["XDG_RUNTIME_DIR"] = str(self.root / "private-canary-missing")
        error = self.assert_reason(
            LifecycleFailureReason.RUNTIME_DIR_INVALID,
            lambda: validate_watcher_environment(environ=missing, which=self.which),
        )
        self.assertNotIn("private-canary", str(error) + repr(error))

        self.runtime.chmod(0o755)
        self.assert_reason(
            LifecycleFailureReason.RUNTIME_DIR_INVALID,
            lambda: validate_watcher_environment(
                environ=self.environment, which=self.which
            ),
        )
        self.runtime.rmdir()
        target = self.root / "target"
        target.mkdir(mode=0o700)
        self.runtime.symlink_to(target, target_is_directory=True)
        self.assert_reason(
            LifecycleFailureReason.RUNTIME_DIR_INVALID,
            lambda: validate_watcher_environment(
                environ=self.environment, which=self.which
            ),
        )

    def test_runtime_and_lock_reentry_have_distinct_reasons(self):
        runtime = self.runtime_guard()
        runtime.__enter__()
        try:
            self.assert_reason(
                LifecycleFailureReason.RUNTIME_REENTRY, runtime.__enter__
            )
        finally:
            runtime.__exit__(None, None, None)

        lock = WatcherInstanceLock(self.runtime)
        lock.acquire()
        try:
            self.assert_reason(LifecycleFailureReason.LOCK_REENTRY, lock.acquire)
        finally:
            lock.release()

    def test_lock_directory_create_and_validation_reasons(self):
        with patch(
            "copypastebin.lifecycle.os.mkdir",
            side_effect=OSError("private-canary-path"),
        ):
            error = self.assert_reason(
                LifecycleFailureReason.LOCK_DIR_CREATE_FAILURE,
                WatcherInstanceLock(self.runtime).acquire,
            )
        self.assertNotIn("private-canary", str(error) + repr(error))

        lock_dir = self.runtime / "copypastebin"
        lock_dir.mkdir(mode=0o700)
        lock_dir.chmod(0o755)
        self.assert_reason(
            LifecycleFailureReason.LOCK_DIR_INVALID,
            WatcherInstanceLock(self.runtime).acquire,
        )

    def test_lock_file_open_metadata_and_validation_reasons(self):
        real_open = os.open

        def fail_lock_open(path, *args, **kwargs):
            if path == "watcher.lock":
                raise OSError("private-canary-open")
            return real_open(path, *args, **kwargs)

        with patch("copypastebin.lifecycle.os.open", side_effect=fail_lock_open):
            error = self.assert_reason(
                LifecycleFailureReason.LOCK_FILE_OPEN_FAILURE,
                WatcherInstanceLock(self.runtime).acquire,
            )
        self.assertNotIn("private-canary", str(error) + repr(error))

        real_fstat = os.fstat
        call_count = 0

        def fail_lock_fstat(descriptor):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise OSError("private-canary-stat")
            return real_fstat(descriptor)

        with patch("copypastebin.lifecycle.os.fstat", side_effect=fail_lock_fstat):
            error = self.assert_reason(
                LifecycleFailureReason.LOCK_FILE_METADATA_FAILURE,
                WatcherInstanceLock(self.runtime).acquire,
            )
        self.assertNotIn("private-canary", str(error) + repr(error))

        lock_path = self.runtime / "copypastebin" / "watcher.lock"
        lock_path.write_bytes(b"private-canary")
        lock_path.chmod(0o600)
        self.assert_reason(
            LifecycleFailureReason.LOCK_FILE_INVALID,
            WatcherInstanceLock(self.runtime).acquire,
        )

    def test_lock_busy_acquire_and_release_reasons(self):
        first = WatcherInstanceLock(self.runtime)
        second = WatcherInstanceLock(self.runtime)
        first.acquire()
        try:
            self.assert_reason(LifecycleFailureReason.LOCK_BUSY, second.acquire)
        finally:
            first.release()

        with patch(
            "copypastebin.lifecycle.fcntl.flock",
            side_effect=OSError("private-canary-flock"),
        ):
            error = self.assert_reason(
                LifecycleFailureReason.LOCK_ACQUIRE_FAILURE,
                WatcherInstanceLock(self.runtime).acquire,
            )
        self.assertNotIn("private-canary", str(error) + repr(error))

        lock = WatcherInstanceLock(self.runtime)
        lock.acquire()
        with patch(
            "copypastebin.lifecycle.fcntl.flock",
            side_effect=OSError("private-canary-unlock"),
        ):
            error = self.assert_reason(
                LifecycleFailureReason.LOCK_RELEASE_FAILURE, lock.release
            )
        self.assertNotIn("private-canary", str(error) + repr(error))

    def test_lock_is_empty_private_and_kernel_released(self):
        first = WatcherInstanceLock(self.runtime)
        second = WatcherInstanceLock(self.runtime)
        first.acquire()
        try:
            lock_path = self.runtime / "copypastebin" / "watcher.lock"
            self.assertEqual(b"", lock_path.read_bytes())
            self.assertEqual(0o600, lock_path.stat().st_mode & 0o777)
            self.assert_reason(LifecycleFailureReason.LOCK_BUSY, second.acquire)
            rendered = repr(first) + repr(second)
            self.assertNotIn(str(self.runtime), rendered)
            self.assertNotIn("pid", rendered.lower())
        finally:
            first.release()
        second.acquire()
        second.release()

    def test_lock_is_kernel_released_and_has_no_stale_pid_problem(self):
        read_descriptor, write_descriptor = os.pipe()
        child = os.fork()
        if child == 0:
            try:
                os.close(read_descriptor)
                lock = WatcherInstanceLock(self.runtime)
                lock.acquire()
                os.write(write_descriptor, b"locked")
            finally:
                os._exit(0)
        os.close(write_descriptor)
        try:
            self.assertEqual(b"locked", os.read(read_descriptor, 6))
        finally:
            os.close(read_descriptor)
            _, status = os.waitpid(child, 0)
        self.assertEqual(0, status)
        second = WatcherInstanceLock(self.runtime)
        second.acquire()
        second.release()

    def test_lock_rejects_symlink_without_changing_target(self):
        lock_dir = self.runtime / "copypastebin"
        lock_dir.mkdir(mode=0o700)
        target = self.root / "target"
        target.write_bytes(b"must-not-change")
        (lock_dir / "watcher.lock").symlink_to(target)
        self.assert_reason(
            LifecycleFailureReason.LOCK_FILE_OPEN_FAILURE,
            WatcherInstanceLock(self.runtime).acquire,
        )
        self.assertEqual(b"must-not-change", target.read_bytes())

    def test_foreground_service_collision_fails_before_clipboard_read(self):
        backend = _Backend()
        watcher = ClipboardWatcher(
            backend,
            _Notifier(),
            HistoryStore(self.root / "state"),
            runtime=self.runtime_guard(),
        )
        with self.runtime_guard():
            with self.assertRaises(WatcherError) as caught:
                watcher.run_forever(poll_interval=0.01, sleep=lambda _: None)
        self.assertIs(LifecycleFailureReason.LOCK_BUSY, caught.exception.lifecycle_reason)
        self.assertEqual(0, backend.read_count)

    def test_watcher_releases_lock_after_termination(self):
        first_backend = _Backend()
        first = ClipboardWatcher(
            first_backend,
            _Notifier(),
            HistoryStore(self.root / "state-one"),
            runtime=self.runtime_guard(),
        )
        with self.assertRaises(WatcherError):
            first.run_forever(poll_interval=0.01, sleep=lambda _: None)
        second_backend = _Backend()
        second = ClipboardWatcher(
            second_backend,
            _Notifier(),
            HistoryStore(self.root / "state-two"),
            runtime=self.runtime_guard(),
        )
        with self.assertRaises(WatcherError):
            second.run_forever(poll_interval=0.01, sleep=lambda _: None)
        self.assertEqual(1, first_backend.read_count)
        self.assertEqual(1, second_backend.read_count)


if __name__ == "__main__":
    unittest.main()
