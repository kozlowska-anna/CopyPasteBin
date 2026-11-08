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
        cls._build_directory = tempfile.TemporaryDirectory()
        environment = os.environ.copy()
        environment["CPB_BUNDLE_DIST_DIR"] = cls._build_directory.name
        subprocess.run(
            [str(ARCHIVE_BUILDER)], check=True, capture_output=True, text=True,
            env=environment,
        )
        cls.archive = Path(cls._build_directory.name) / "CopyPasteBin-linux-1.2.1.tar.gz"
        environment["CPB_DEB_DIST_DIR"] = cls._build_directory.name
        completed = subprocess.run(
            [str(DEB_BUILDER)], check=True, capture_output=True, text=True,
            env=environment,
        )
        cls.debs = [
            Path(line) for line in completed.stdout.splitlines()
            if line.strip().endswith(".deb")
        ]
        if len(cls.debs) != 3:
            raise AssertionError("split Debian build did not return three packages")

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

            with tarfile.open(self.archive, "r:gz") as archive:
                archive.extractall(root / "archive", filter="data")
            bundle = root / "archive" / "CopyPasteBin-linux-1.2.1"
            isolated_runtime = root / "run"
            isolated_runtime.mkdir(mode=0o700)
            environment = os.environ.copy()
            environment.update({
                "HOME": str(home),
                "XDG_RUNTIME_DIR": str(isolated_runtime),
                "DBUS_SESSION_BUS_ADDRESS": f"unix:path={isolated_runtime / 'bus'}",
                "XDG_SESSION_TYPE": "wayland",
            })
            environment.pop("DBUS_STARTER_ADDRESS", None)
            environment.pop("DBUS_STARTER_BUS_TYPE", None)
            self.assertFalse((isolated_runtime / "bus").exists())

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
            for package in self.debs:
                subprocess.run(
                    ["dpkg-deb", "--extract", str(package), str(system_root)],
                    check=True, capture_output=True,
                )
            system_extension = system_root / "usr/share/gnome-shell/extensions" / UUID
            self.assertTrue((system_extension / "image-redactor.js").is_file())
            self.assertFalse(local_extension.exists())

            shutil.rmtree(system_root / "usr")
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())

            for package in self.debs:
                subprocess.run(
                    ["dpkg-deb", "--extract", str(package), str(system_root)],
                    check=True, capture_output=True,
                )
            self.assertTrue((system_extension / "extension.js").is_file())


if __name__ == "__main__":
    unittest.main()
