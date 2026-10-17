import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from copypastebin.service import (
    AutostartStatus,
    MANAGED_MARKER,
    SERVICE_NAME,
    SERVICE_OUTPUT_LIMIT_BYTES,
    ServiceController,
    ServiceError,
    ServiceStatus,
    _close_process,
    _read_limited_process_output,
    _systemd_quote,
    _unit_content,
)


RUNNING = (
    b"LoadState=loaded\nActiveState=active\nSubState=running\n"
)
STOPPED = (
    b"LoadState=loaded\nActiveState=inactive\nSubState=dead\n"
)
FAILED = (
    b"LoadState=loaded\nActiveState=failed\nSubState=failed\n"
)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.unit_dir = self.root / "config" / "systemd" / "user"
        self.entry_point = self.root / "bin" / "cpb"
        self.entry_point.parent.mkdir()
        self.entry_point.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.entry_point.chmod(0o700)
        self.controller = ServiceController(
            unit_dir=self.unit_dir,
            entry_point=self.entry_point,
            systemctl_which=lambda _: "/usr/bin/systemctl",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def setup_unit(self):
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ):
            self.controller.setup()

    def test_setup_writes_safe_unit_and_only_daemon_reload(self):
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ) as run:
            self.controller.setup()
        run.assert_called_once_with(("daemon-reload",), capture=False)
        unit = self.controller.unit_path.read_text(encoding="utf-8")
        self.assertTrue(unit.startswith(MANAGED_MARKER))
        self.assertIn(
            f'ExecStart="{self.entry_point}" "watch" "start"', unit
        )
        self.assertNotIn("PYTHONPATH", unit)
        self.assertNotIn('"-I"', unit)
        self.assertNotIn("copypastebin.cli", unit)
        self.assertIn("Restart=no", unit)
        self.assertIn("KillMode=control-group", unit)
        self.assertIn("UMask=0077", unit)
        self.assertIn("[Install]\nWantedBy=graphical-session.target\n", unit)
        self.assertEqual(
            1, unit.count("After=gnome-session-initialized.target\n")
        )
        self.assertIn("PartOf=graphical-session.target", unit)
        self.assertNotIn("After=graphical-session.target", unit)
        self.assertNotIn("Requires=gnome-session-initialized.target", unit)
        self.assertNotIn("Requisite=gnome-session-initialized.target", unit)
        self.assertNotIn("Environment=", unit)
        self.assertNotIn("EnvironmentFile=", unit)
        self.assertNotIn("enable", unit)
        self.assertEqual(0o600, self.controller.unit_path.stat().st_mode & 0o777)
        self.assertEqual(0o700, self.unit_dir.stat().st_mode & 0o777)

    def test_systemd_quote_escapes_percent_space_backslash_and_quote_exactly(self):
        value = '/opt/cpb%test/bin/cpb path\\with"quote'
        self.assertEqual(
            '"/opt/cpb%%test/bin/cpb path\\\\with\\"quote"',
            _systemd_quote(value),
        )
        unit = _unit_content(Path("/opt/cpb%test/bin/cpb"))
        self.assertIn(
            'ExecStart="/opt/cpb%%test/bin/cpb" "watch" "start"\n', unit
        )
        self.assertNotIn('/opt/cpb%test/bin/cpb', unit)

    def test_setup_escapes_combined_special_characters_in_execstart(self):
        entry_point = self.root / 'bin space%test\\quote"' / "cpb"
        entry_point.parent.mkdir()
        entry_point.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        entry_point.chmod(0o700)
        controller = ServiceController(
            unit_dir=self.root / "special-unit",
            entry_point=entry_point,
            systemctl_which=lambda _: "/usr/bin/systemctl",
        )
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ):
            controller.setup()
        escaped = (
            str(entry_point.resolve())
            .replace("%", "%%")
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )
        self.assertIn(
            f'ExecStart="{escaped}" "watch" "start"\n',
            controller.unit_path.read_text(encoding="utf-8"),
        )

    def test_entry_point_is_discovered_as_absolute_executable(self):
        controller = ServiceController(
            unit_dir=self.root / "discovered-unit",
            entry_point_which=lambda name: (
                str(self.entry_point) if name == "cpb" else None
            ),
            systemctl_which=lambda _: "/usr/bin/systemctl",
        )
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ):
            controller.setup()
        self.assertIn(
            f'ExecStart="{self.entry_point.resolve()}" "watch" "start"',
            controller.unit_path.read_text(encoding="utf-8"),
        )

    def test_setup_rejects_missing_invalid_and_unsafe_entry_points(self):
        missing = self.root / "missing-cpb"
        non_executable = self.root / "non-executable-cpb"
        non_executable.write_text("#!/bin/sh\n", encoding="utf-8")
        non_executable.chmod(0o600)
        directory = self.root / "cpb-directory"
        directory.mkdir()
        cases = (
            (None, lambda _: None),
            (missing, None),
            (non_executable, None),
            (directory, None),
            (Path("relative/cpb"), None),
            (Path("/tmp/cpb\x00unsafe"), None),
            (Path("/tmp/cpb\nunsafe"), None),
            (Path("/tmp/cpb\runsafe"), None),
        )
        for index, (entry_point, which) in enumerate(cases):
            with self.subTest(entry_point=repr(entry_point)):
                controller = ServiceController(
                    unit_dir=self.root / f"invalid-{index}",
                    entry_point=entry_point,
                    entry_point_which=which,
                    systemctl_which=lambda _: "/usr/bin/systemctl",
                )
                with self.assertRaises(ServiceError) as caught:
                    controller.setup()
                rendered = str(caught.exception) + repr(caught.exception)
                self.assertNotIn("cpb", rendered.lower())

    def test_entry_point_symlink_is_resolved_to_stable_target(self):
        link = self.root / "cpb-link"
        link.symlink_to(self.entry_point)
        controller = ServiceController(
            unit_dir=self.root / "symlink-unit",
            entry_point=link,
            systemctl_which=lambda _: "/usr/bin/systemctl",
        )
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ):
            controller.setup()
        unit = controller.unit_path.read_text(encoding="utf-8")
        self.assertIn(f'ExecStart="{self.entry_point.resolve()}"', unit)
        self.assertNotIn(str(link), unit)

    def test_setup_is_idempotent(self):
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ) as run:
            self.controller.setup()
            inode = self.controller.unit_path.stat().st_ino
            self.controller.setup()
        self.assertEqual(inode, self.controller.unit_path.stat().st_ino)
        self.assertEqual(2, run.call_count)

    def test_setup_updates_only_previously_managed_unit_atomically(self):
        self.unit_dir.mkdir(parents=True, mode=0o700)
        self.controller.unit_path.write_text(
            MANAGED_MARKER + "[Service]\nRestart=old\n", encoding="utf-8"
        )
        self.controller.unit_path.chmod(0o600)
        old_inode = self.controller.unit_path.stat().st_ino
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ):
            self.controller.setup()
        self.assertNotEqual(old_inode, self.controller.unit_path.stat().st_ino)
        self.assertIn(
            "Restart=no", self.controller.unit_path.read_text(encoding="utf-8")
        )
        self.assertEqual([], list(self.unit_dir.glob("*.tmp")))

    def test_setup_preserves_existing_enablement_symlink(self):
        self.unit_dir.mkdir(parents=True, mode=0o700)
        self.controller.unit_path.write_text(
            MANAGED_MARKER + "[Service]\nRestart=old\n", encoding="utf-8"
        )
        self.controller.unit_path.chmod(0o600)
        wants = self.unit_dir / "graphical-session.target.wants"
        wants.mkdir()
        enabled_link = wants / SERVICE_NAME
        enabled_link.symlink_to(self.controller.unit_path)
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, b"")
        ) as run:
            self.controller.setup()
        self.assertTrue(enabled_link.is_symlink())
        self.assertEqual(self.controller.unit_path, enabled_link.resolve())
        run.assert_called_once_with(("daemon-reload",), capture=False)

    def test_setup_rejects_symlink_and_unknown_existing_file(self):
        self.unit_dir.mkdir(parents=True, mode=0o700)
        target = self.root / "foreign"
        target.write_text("foreign", encoding="utf-8")
        self.controller.unit_path.symlink_to(target)
        with self.assertRaises(ServiceError):
            self.controller.setup()
        self.assertEqual("foreign", target.read_text(encoding="utf-8"))

        self.controller.unit_path.unlink()
        self.controller.unit_path.write_text("foreign", encoding="utf-8")
        self.controller.unit_path.chmod(0o600)
        with self.assertRaises(ServiceError):
            self.controller.setup()
        self.assertEqual("foreign", self.controller.unit_path.read_text(encoding="utf-8"))

    def test_status_maps_only_closed_states(self):
        self.setup_unit()
        cases = (
            (RUNNING, ServiceStatus.RUNNING),
            (STOPPED, ServiceStatus.STOPPED),
            (FAILED, ServiceStatus.FAILED),
            (
                b"LoadState=not-found\nActiveState=inactive\nSubState=dead\n",
                ServiceStatus.NOT_CONFIGURED,
            ),
            (
                b"LoadState=loaded\nActiveState=activating\nSubState=start\n",
                ServiceStatus.UNKNOWN,
            ),
        )
        for output, expected in cases:
            with self.subTest(expected=expected), patch.object(
                ServiceController, "_run_systemctl", return_value=(0, output)
            ):
                self.assertEqual(expected, self.controller.status())

    def test_status_uses_only_whitelisted_show_properties(self):
        self.setup_unit()
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(0, RUNNING)
        ) as run:
            self.assertEqual(ServiceStatus.RUNNING, self.controller.status())
        run.assert_called_once_with(
            (
                "show",
                SERVICE_NAME,
                "--property=LoadState",
                "--property=ActiveState",
                "--property=SubState",
                "--no-pager",
            ),
            capture=True,
        )

    def test_missing_unit_and_query_failure_are_not_false_stopped(self):
        self.assertEqual(ServiceStatus.NOT_CONFIGURED, self.controller.status())
        self.setup_unit()
        with patch.object(
            ServiceController, "_run_systemctl", return_value=(7, b"private-canary")
        ):
            self.assertEqual(ServiceStatus.UNKNOWN, self.controller.status())
        with patch.object(
            ServiceController,
            "_run_systemctl",
            side_effect=ServiceError("private-canary"),
        ):
            self.assertEqual(ServiceStatus.UNKNOWN, self.controller.status())

    def test_start_uses_fixed_command_and_requires_running(self):
        self.setup_unit()
        with patch.object(
            ServiceController,
            "_run_systemctl",
            side_effect=((0, b""), (0, RUNNING)),
        ) as run:
            self.assertEqual(ServiceStatus.RUNNING, self.controller.start())
        self.assertEqual(
            (("start", SERVICE_NAME),), run.call_args_list[0].args
        )
        self.assertFalse(run.call_args_list[0].kwargs["capture"])

        with patch.object(
            ServiceController,
            "_run_systemctl",
            side_effect=((0, b""), (0, FAILED)),
        ):
            with self.assertRaises(ServiceError):
                self.controller.start()
        with patch.object(
            ServiceController,
            "_run_systemctl",
            return_value=(7, b"private-canary\x1b"),
        ):
            with self.assertRaises(ServiceError) as caught:
                self.controller.start()
        self.assertNotIn("private-canary", str(caught.exception) + repr(caught.exception))

    def test_stop_is_idempotent_and_controls_only_known_service(self):
        self.assertEqual(ServiceStatus.STOPPED, self.controller.stop())
        self.setup_unit()
        with patch.object(
            ServiceController,
            "_run_systemctl",
            side_effect=((0, b""), (0, STOPPED)),
        ) as run:
            self.assertEqual(ServiceStatus.STOPPED, self.controller.stop())
        self.assertEqual(
            (("stop", SERVICE_NAME),), run.call_args_list[0].args
        )

    def test_enable_and_disable_use_fixed_commands_without_now(self):
        self.setup_unit()
        for method_name, verb, expected in (
            ("enable", "enable", AutostartStatus.ENABLED),
            ("disable", "disable", AutostartStatus.DISABLED),
        ):
            with self.subTest(method=method_name), patch.object(
                ServiceController, "_run_systemctl", return_value=(0, b"")
            ) as run:
                self.assertEqual(expected, getattr(self.controller, method_name)())
            run.assert_called_once_with((verb, SERVICE_NAME), capture=False)
            flattened = run.call_args.args[0]
            self.assertNotIn("--now", flattened)
            self.assertNotIn("start", flattened)
            self.assertNotIn("stop", flattened)

    def test_enable_and_disable_are_idempotent(self):
        self.setup_unit()
        for method_name, expected in (
            ("enable", AutostartStatus.ENABLED),
            ("disable", AutostartStatus.DISABLED),
        ):
            with self.subTest(method=method_name), patch.object(
                ServiceController, "_run_systemctl", return_value=(0, b"")
            ) as run:
                self.assertEqual(expected, getattr(self.controller, method_name)())
                self.assertEqual(expected, getattr(self.controller, method_name)())
            self.assertEqual(2, run.call_count)

    def test_autostart_maps_only_enabled_and_disabled(self):
        self.setup_unit()
        cases = (
            (0, b"enabled\n", AutostartStatus.ENABLED),
            (0, b"disabled\n", AutostartStatus.DISABLED),
            (0, b"static\n", AutostartStatus.UNKNOWN),
            (0, b"enabled-runtime\n", AutostartStatus.UNKNOWN),
            (0, b"indirect\n", AutostartStatus.UNKNOWN),
            (0, b"", AutostartStatus.UNKNOWN),
            (4, b"not-found\n", AutostartStatus.UNKNOWN),
            (1, b"private-canary\n", AutostartStatus.UNKNOWN),
            (1, b"enabled\n", AutostartStatus.UNKNOWN),
            (1, b"disabled\n", AutostartStatus.UNKNOWN),
        )
        for return_code, output, expected in cases:
            with self.subTest(output=output), patch.object(
                ServiceController,
                "_run_systemctl",
                return_value=(return_code, output),
            ) as run:
                self.assertEqual(expected, self.controller.autostart())
            run.assert_called_once_with(
                ("is-enabled", SERVICE_NAME), capture=True
            )

    def test_autostart_query_failure_and_missing_unit_are_unknown(self):
        self.assertEqual(AutostartStatus.UNKNOWN, self.controller.autostart())
        self.setup_unit()
        with patch.object(
            ServiceController,
            "_run_systemctl",
            side_effect=ServiceError("private-canary"),
        ):
            self.assertEqual(AutostartStatus.UNKNOWN, self.controller.autostart())

    def test_enable_and_disable_reject_foreign_or_symlinked_unit(self):
        self.unit_dir.mkdir(parents=True, mode=0o700)
        foreign = self.root / "foreign"
        foreign.write_text("foreign", encoding="utf-8")
        for symlinked in (False, True):
            with self.subTest(symlinked=symlinked):
                if self.controller.unit_path.exists() or self.controller.unit_path.is_symlink():
                    self.controller.unit_path.unlink()
                if symlinked:
                    self.controller.unit_path.symlink_to(foreign)
                else:
                    self.controller.unit_path.write_text("foreign", encoding="utf-8")
                    self.controller.unit_path.chmod(0o600)
                for method_name in ("enable", "disable"):
                    with self.assertRaises(ServiceError) as caught, patch.object(
                        ServiceController, "_run_systemctl"
                    ) as run:
                        getattr(self.controller, method_name)()
                    run.assert_not_called()
                    self.assertNotIn(
                        "foreign", str(caught.exception) + repr(caught.exception)
                    )

    def test_autostart_unit_keeps_fail_closed_policy_and_has_no_desktop(self):
        unit = _unit_content(self.entry_point)
        self.assertIn("Restart=no", unit)
        self.assertNotIn("Restart=on-", unit)
        self.assertNotIn("StartLimit", unit)
        self.assertNotIn(".desktop", unit)

    def test_systemctl_process_has_fixed_safe_shape(self):
        process = SimpleNamespace(returncode=0)
        with patch(
            "copypastebin.service.subprocess.Popen", return_value=process
        ) as popen, patch(
            "copypastebin.service._read_limited_process_output",
            return_value=RUNNING,
        ), patch("copypastebin.service._close_process"):
            code, output = self.controller._run_systemctl(
                ("show", SERVICE_NAME), capture=True
            )
        self.assertEqual(0, code)
        self.assertEqual(RUNNING, output)
        self.assertEqual(
            ["/usr/bin/systemctl", "--user", "show", SERVICE_NAME],
            popen.call_args.args[0],
        )
        kwargs = popen.call_args.kwargs
        self.assertIs(subprocess.DEVNULL, kwargs["stdin"])
        self.assertIs(subprocess.PIPE, kwargs["stdout"])
        self.assertIs(subprocess.DEVNULL, kwargs["stderr"])
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["close_fds"])

    def test_timeout_cleanup_and_public_errors_are_redacted(self):
        class Process:
            stdout = None
            returncode = None

            def wait(self, timeout):
                raise subprocess.TimeoutExpired(
                    ["systemctl", "private-canary"], timeout, stderr=b"private-canary"
                )

        process = Process()
        with patch("copypastebin.service.subprocess.Popen", return_value=process), patch(
            "copypastebin.service._close_process"
        ) as close:
            with self.assertRaises(ServiceError) as caught:
                self.controller._run_systemctl(("start", SERVICE_NAME), capture=False)
        close.assert_called_once_with(process)
        rendered = str(caught.exception) + repr(caught.exception)
        self.assertNotIn("private-canary", rendered)

    def test_stdout_limit_terminates_synthetic_subprocess(self):
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"import os; os.write(1, b'x' * {SERVICE_OUTPUT_LIMIT_BYTES + 1})",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            bufsize=0,
        )
        try:
            with self.assertRaises(ServiceError):
                _read_limited_process_output(
                    process, 2.0, SERVICE_OUTPUT_LIMIT_BYTES
                )
        finally:
            _close_process(process)

    def test_status_parser_rejects_unbounded_invalid_and_raw_output(self):
        self.setup_unit()
        outputs = (
            b"private-canary\x1b",
            b"LoadState=loaded\nActiveState=active\n",
            b"LoadState=loaded\nActiveState=active\nSubState=private-canary\x1b\n",
        )
        for output in outputs:
            with self.subTest(output=output), patch.object(
                ServiceController, "_run_systemctl", return_value=(0, output)
            ):
                self.assertEqual(ServiceStatus.UNKNOWN, self.controller.status())
        self.assertNotIn("private-canary", repr(self.controller))


if __name__ == "__main__":
    unittest.main()
