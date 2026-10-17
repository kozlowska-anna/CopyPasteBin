import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin.launcher import (
    LAUNCHER_NAME,
    MANAGED_MARKER,
    LauncherController,
    LauncherError,
    _desktop_exec_quote,
    _launcher_content,
    default_user_application_dir,
)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.application_dir = self.root / "share" / "applications"
        self.entry_point = self.root / "bin" / "cpb"
        self.entry_point.parent.mkdir()
        self.entry_point.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.entry_point.chmod(0o700)
        self.controller = LauncherController(
            application_dir=self.application_dir,
            entry_point=self.entry_point,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_setup_writes_one_safe_start_launcher(self):
        self.controller.setup()
        content = self.controller.launcher_path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith(MANAGED_MARKER))
        self.assertEqual(
            1,
            content.count(
                f'Exec="{self.entry_point.resolve()}" "service" "start"\n'
            ),
        )
        self.assertIn("Name=Start CopyPasteBin\n", content)
        self.assertIn("Icon=edit-paste\n", content)
        self.assertIn("Terminal=false\n", content)
        self.assertIn("StartupNotify=false\n", content)
        self.assertIn("DBusActivatable=false\n", content)
        self.assertNotIn("watch", content)
        self.assertNotIn("enable", content)
        self.assertNotIn("--now", content)
        self.assertNotIn("sh -c", content)
        self.assertNotIn("bash", content)
        self.assertEqual(0o600, self.controller.launcher_path.stat().st_mode & 0o777)
        self.assertTrue(self.application_dir.is_dir())

    def test_setup_is_idempotent_and_updates_only_managed_launcher(self):
        self.controller.setup()
        first_inode = self.controller.launcher_path.stat().st_ino
        self.controller.setup()
        self.assertEqual(first_inode, self.controller.launcher_path.stat().st_ino)

        self.controller.launcher_path.write_text(
            MANAGED_MARKER + "[Desktop Entry]\nName=Old\n", encoding="utf-8"
        )
        self.controller.launcher_path.chmod(0o600)
        old_inode = self.controller.launcher_path.stat().st_ino
        self.controller.setup()
        self.assertNotEqual(old_inode, self.controller.launcher_path.stat().st_ino)
        self.assertIn(
            "Name=Start CopyPasteBin\n",
            self.controller.launcher_path.read_text(encoding="utf-8"),
        )

    def test_setup_rejects_foreign_symlinked_and_wrong_mode_launchers(self):
        self.application_dir.mkdir(parents=True, mode=0o700)
        foreign_target = self.root / "foreign.desktop"
        foreign_target.write_text("foreign", encoding="utf-8")
        cases = ("foreign", "symlink", "wrong-mode")
        for case in cases:
            with self.subTest(case=case):
                path = self.controller.launcher_path
                if path.exists() or path.is_symlink():
                    path.unlink()
                if case == "symlink":
                    path.symlink_to(foreign_target)
                else:
                    content = "foreign" if case == "foreign" else MANAGED_MARKER
                    path.write_text(content, encoding="utf-8")
                    path.chmod(0o644 if case == "wrong-mode" else 0o600)
                before = foreign_target.read_bytes()
                with self.assertRaises(LauncherError):
                    self.controller.setup()
                self.assertEqual(before, foreign_target.read_bytes())

    def test_setup_rejects_relative_or_symlinked_application_directory(self):
        relative = LauncherController(
            application_dir=Path("relative/applications"),
            entry_point=self.entry_point,
        )
        with self.assertRaises(LauncherError):
            relative.setup()

        target = self.root / "real-applications"
        target.mkdir()
        linked = self.root / "linked-applications"
        linked.symlink_to(target, target_is_directory=True)
        symlinked = LauncherController(
            application_dir=linked,
            entry_point=self.entry_point,
        )
        with self.assertRaises(LauncherError):
            symlinked.setup()
        self.assertEqual([], list(target.iterdir()))

    def test_setup_rejects_invalid_entry_points_without_writing(self):
        directory = self.root / "entry-directory"
        directory.mkdir()
        non_executable = self.root / "not-executable"
        non_executable.write_text("x", encoding="utf-8")
        non_executable.chmod(0o600)
        missing = self.root / "missing"
        cases = (
            Path("relative-cpb"),
            directory,
            non_executable,
            missing,
        )
        for entry_point in cases:
            with self.subTest(entry_point=entry_point):
                controller = LauncherController(
                    application_dir=self.application_dir,
                    entry_point=entry_point,
                )
                with self.assertRaises(LauncherError):
                    controller.setup()
        self.assertFalse(self.controller.launcher_path.exists())

    def test_entry_point_discovery_requires_absolute_executable(self):
        discovered = LauncherController(
            application_dir=self.application_dir,
            entry_point_which=lambda name: (
                str(self.entry_point) if name == "cpb" else None
            ),
        )
        discovered.setup()
        self.assertIn(
            f'Exec="{self.entry_point.resolve()}" "service" "start"\n',
            discovered.launcher_path.read_text(encoding="utf-8"),
        )
        for result in (None, "cpb", "private-canary\n"):
            with self.subTest(result=result):
                controller = LauncherController(
                    application_dir=self.root / "other-applications",
                    entry_point_which=lambda _name, value=result: value,
                )
                with self.assertRaises(LauncherError) as caught:
                    controller.setup()
                self.assertNotIn(
                    "private-canary", str(caught.exception) + repr(caught.exception)
                )

    def test_desktop_exec_escapes_percent_and_quoted_special_characters(self):
        value = '/opt/cpb% test/bin/cpb$`"\\tail'
        quoted = _desktop_exec_quote(value)
        self.assertEqual(
            '"/opt/cpb%% test/bin/cpb\\\\$\\\\`\\\\"\\\\\\\\tail"', quoted
        )
        content = _launcher_content(Path("/opt/cpb% test/bin/cpb"))
        self.assertIn(
            'Exec="/opt/cpb%% test/bin/cpb" "service" "start"\n', content
        )
        self.assertNotIn("/opt/cpb% test/bin", content)

    def test_desktop_exec_rejects_invalid_string_values(self):
        for value in ("", "relative=cpb", "/opt/cpb\n", "/opt/żółw/cpb"):
            with self.subTest(value=value), self.assertRaises(LauncherError):
                _desktop_exec_quote(value)

    def test_default_application_directory_obeys_absolute_xdg_data_home(self):
        self.assertEqual(
            Path("/safe/data/applications"),
            default_user_application_dir({"XDG_DATA_HOME": "/safe/data"}),
        )
        with self.assertRaises(LauncherError):
            default_user_application_dir({"XDG_DATA_HOME": "relative"})

    def test_atomic_write_failure_leaves_no_launcher_or_temporary_file(self):
        with patch("copypastebin.launcher.os.replace", side_effect=OSError("private")):
            with self.assertRaises(LauncherError) as caught:
                self.controller.setup()
        self.assertFalse(self.controller.launcher_path.exists())
        self.assertEqual([], list(self.application_dir.iterdir()))
        self.assertNotIn("private", str(caught.exception) + repr(caught.exception))

    def test_generated_launcher_passes_desktop_file_validate(self):
        validator = shutil.which("desktop-file-validate")
        if validator is None:
            self.skipTest("desktop-file-validate is not installed")
        self.controller.setup()
        result = subprocess.run(
            [validator, str(self.controller.launcher_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            check=False,
            timeout=5,
        )
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(0, result.returncode)

    def test_launcher_name_and_repr_are_closed(self):
        self.assertEqual("copypastebin-start.desktop", LAUNCHER_NAME)
        rendered = repr(self.controller)
        self.assertEqual("LauncherController(content_redacted=True)", rendered)
        self.assertNotIn(str(self.root), rendered)


if __name__ == "__main__":
    unittest.main()
