import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_BUILDER = ROOT / "packaging" / "build-offline-bundle.sh"
DEB_BUILDER = ROOT / "packaging" / "deb" / "build-deb.sh"
ARCHIVE = ROOT / "dist" / "CopyPasteBin-linux-1.1.tar.gz"
UUID = "copypastebin@kozlowska-anna.github.io"


@unittest.skipUnless(
    all(Path(path).is_file() for path in (
        "/usr/bin/gnome-shell", "/usr/bin/gnome-extensions", "/usr/bin/gjs"
    )),
    "GNOME 50 build dependencies are required",
)
class InstallationMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(ARCHIVE_BUILDER)], check=True, capture_output=True, text=True)
        cls._build_directory = tempfile.TemporaryDirectory()
        environment = os.environ.copy()
        environment["CPB_DEB_DIST_DIR"] = cls._build_directory.name
        completed = subprocess.run(
            [str(DEB_BUILDER)], check=True, capture_output=True, text=True,
            env=environment,
        )
        cls.deb = Path(completed.stdout.strip().splitlines()[-1])

    @classmethod
    def tearDownClass(cls):
        cls._build_directory.cleanup()

    def test_clean_reinstall_remove_and_tar_to_deb_preserve_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            config = home / ".config/copypastebin"
            state = home / ".local/state/copypastebin"
            config.mkdir(parents=True)
            state.mkdir(parents=True)
            (config / "synthetic.toml").write_text("synthetic=true\n", encoding="utf-8")
            (state / "synthetic.state").write_text("synthetic\n", encoding="utf-8")

            with tarfile.open(ARCHIVE, "r:gz") as archive:
                archive.extractall(root / "archive", filter="data")
            bundle = root / "archive" / "CopyPasteBin-linux-1.1"
            environment = os.environ.copy()
            environment.update({"HOME": str(home), "XDG_SESSION_TYPE": "wayland"})
            environment.pop("DBUS_SESSION_BUS_ADDRESS", None)

            for _ in range(2):
                subprocess.run(
                    [str(bundle / "install.sh"), "--no-enable"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
            local_extension = home / ".local/share/gnome-shell/extensions" / UUID
            self.assertTrue(local_extension.is_dir())
            self.assertTrue((local_extension / "image-redactor.js").is_file())

            subprocess.run(
                [str(bundle / "uninstall.sh")], check=True,
                capture_output=True, text=True, env=environment,
            )
            self.assertFalse(local_extension.exists())
            self.assertFalse((home / ".local/share/copypastebin").exists())
            self.assertFalse((home / ".local/share/applications/copypastebin.desktop").exists())
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())

            subprocess.run(
                [str(bundle / "install.sh"), "--no-enable"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertTrue((local_extension / "extension.js").is_file())
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())
            subprocess.run(
                [str(bundle / "uninstall.sh")], check=True,
                capture_output=True, text=True, env=environment,
            )
            self.assertFalse(local_extension.exists())

            system_root = root / "system"
            subprocess.run(
                ["dpkg-deb", "--extract", str(self.deb), str(system_root)],
                check=True, capture_output=True,
            )
            system_extension = system_root / "usr/share/gnome-shell/extensions" / UUID
            self.assertTrue((system_extension / "image-redactor.js").is_file())
            self.assertFalse(local_extension.exists())

            shutil.rmtree(system_root / "usr")
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())

            subprocess.run(
                ["dpkg-deb", "--extract", str(self.deb), str(system_root)],
                check=True, capture_output=True,
            )
            self.assertTrue((system_extension / "extension.js").is_file())


if __name__ == "__main__":
    unittest.main()
