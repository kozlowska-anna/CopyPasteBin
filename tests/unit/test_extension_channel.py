Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "gnome-extension" / "copypastebin@kozlowska-anna.github.io"
MODULE = EXTENSION / "extension-channel.js"
DRIVER = ROOT / "tests" / "helpers" / "extension_channel_driver.js"
GJS = Path("/usr/bin/gjs")


@unittest.skipUnless(GJS.exists(), "GJS is required by the GNOME extension")
class ExtensionChannelTests(unittest.TestCase):
    def state(self, system: Path, user: Path) -> str:
        completed = subprocess.run(
            [str(GJS), "-m", str(DRIVER), str(system), str(user)],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def test_zero_or_one_extension_channel_is_clear(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            system = root / "system" / "extension"
            user = root / "user" / "extension"
            self.assertEqual("clear", self.state(system, user))
            system.mkdir(parents=True)
            self.assertEqual("clear", self.state(system, user))
            system.rmdir()
            user.mkdir(parents=True)
            self.assertEqual("clear", self.state(system, user))

    def test_two_extension_channels_report_conflict_without_following_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            system = root / "system" / "extension"
            user = root / "user" / "extension"
            system.mkdir(parents=True)
            user.mkdir(parents=True)
            self.assertEqual("conflict", self.state(system, user))
            user.rmdir()
            user.symlink_to(root / "missing-target")
            self.assertEqual("conflict", self.state(system, user))

    def test_invalid_or_ambiguous_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "same"
            self.assertEqual("error", self.state(path, path))
            blocker = root / "not-a-directory"
            blocker.write_text("synthetic\n", encoding="utf-8")
            self.assertEqual(
                "error",
                self.state(root / "system", blocker / "extension"),
            )

    def test_detector_uses_only_fixed_local_paths_and_never_mutates_them(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn("/usr/share/gnome-shell/extensions/", source)
        self.assertIn("'.local', 'share', 'gnome-shell', 'extensions'", source)
        self.assertIn("Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS", source)
        for forbidden in (
            "Gio.Subprocess", "delete(", "trash(", "move(", "setenv(",
            "getenv('PATH')", "/bin/sh", "sudo", "pkexec", "apt ",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
