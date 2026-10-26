import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "packaging" / "deb" / "build-deb.sh"
CONTROL = ROOT / "packaging" / "deb" / "control"
README = ROOT / "packaging" / "deb" / "README.Debian"
DEB_LAUNCHER = ROOT / "packaging" / "deb" / "copypastebin.desktop"
ENABLE_HELPER = ROOT / "packaging" / "deb" / "enable-extension.js"
METAINFO = ROOT / "packaging" / "deb" / "io.github.kozlowska_anna.CopyPasteBin.metainfo.xml"
UUID = "copypastebin@kozlowska-anna.github.io"
SOURCE_EXTENSION = ROOT / "gnome-extension" / UUID / "extension.js"
SOURCE_IMAGE_REDACTOR = ROOT / "gnome-extension" / UUID / "image-redactor.js"
SOURCE_IMAGE_CORE = ROOT / "gnome-extension" / UUID / "image-redaction-core.js"


class DebPackagingTests(unittest.TestCase):
    def _build(self, destination: Path) -> Path:
        environment = os.environ.copy()
        environment["CPB_DEB_DIST_DIR"] = str(destination)
        completed = subprocess.run(
            [str(BUILDER)],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        package = Path(completed.stdout.strip().splitlines()[-1])
        self.assertTrue(package.is_file())
        return package

    def test_builder_is_offline_bounded_and_has_no_maintainer_scripts(self):
        source = BUILDER.read_text(encoding="utf-8")
        control = CONTROL.read_text(encoding="utf-8")

        self.assertIn("dpkg-deb --build --root-owner-group", source)
        self.assertNotIn("system-entry-point.patch", source)
        self.assertNotIn("patch --", source)
        self.assertIn("/usr/share/gnome-shell/extensions/$UUID", source)
        self.assertIn("/usr/lib/python3/dist-packages/copypastebin", source)
        self.assertIn("/usr/share/metainfo", source)
        self.assertIn('readonly SOURCE_DATE_EPOCH="1792454400"', source)
        self.assertIn("export SOURCE_DATE_EPOCH", source)
        self.assertNotIn("postinst", source)
        self.assertNotIn("prerm", source)
        self.assertNotIn("postrm", source)
        self.assertNotIn("preinst", source)
        for forbidden in (
            "curl ",
            "wget ",
            "sudo ",
            "$HOME",
            ".config/copypastebin",
            ".local/state/copypastebin",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        self.assertIn("Architecture: all", control)
        self.assertIn("gnome-shell (>= 50~)", control)
        self.assertIn("gnome-shell (<< 51~)", control)
        self.assertIn("Version: 1.1-1", control)
        self.assertIn("gir1.2-gdkpixbuf-2.0", control)
        self.assertNotIn("Recommends:", control)

    def test_first_start_and_appstream_metadata_are_explicit_and_honest(self):
        launcher = DEB_LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("Name=Enable CopyPasteBin", launcher)
        self.assertIn("Name[pl]=Włącz CopyPasteBin", launcher)
        self.assertIn(
            "Exec=/usr/bin/gjs -m /usr/share/copypastebin/enable-extension.js",
            launcher,
        )
        self.assertNotIn("sudo", launcher)
        helper = ENABLE_HELPER.read_text(encoding="utf-8")
        self.assertIn("Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS", helper)
        self.assertIn("'/usr/bin/gnome-extensions', 'enable', UUID", helper)
        self.assertIn("'.local', 'share', 'gnome-shell', 'extensions', UUID", helper)
        self.assertNotIn("delete(", helper)
        self.assertNotIn("rm ", helper)
        component = ET.parse(METAINFO).getroot()
        self.assertEqual("desktop-application", component.attrib["type"])
        self.assertEqual("FSFAP", component.findtext("metadata_license"))
        self.assertEqual("GPL-3.0-or-later", component.findtext("project_license"))
        self.assertEqual("copypastebin.desktop", component.findtext("launchable"))
        self.assertEqual("copypastebin", component.find("icon").text)
        self.assertEqual("Anna Kozłowska", component.find("developer/name").text)
        self.assertEqual(
            "1.1",
            component.find("releases/release").attrib["version"],
        )
        self.assertEqual(
            {"Utility", "Security"},
            {item.text for item in component.findall("categories/category")},
        )
        descriptions = " ".join(
            " ".join((paragraph.text or "").split())
            for paragraph in component.findall("description/p")
        )
        self.assertIn("photos and screenshots", descriptions)
        self.assertIn("no data is sent to a cloud service", descriptions)
        self.assertIn("warns when sensitive content is detected", descriptions)
        self.assertNotIn("warns before", descriptions)

    def test_documentation_preserves_user_state_and_requires_explicit_activation(self):
        documentation = " ".join(README.read_text(encoding="utf-8").split())
        self.assertIn("does not enable the extension", documentation)
        self.assertIn("Enable CopyPasteBin", documentation)
        self.assertIn("preserves ~/.config/copypastebin", documentation)
        self.assertIn("~/.local/state/copypastebin", documentation)
        self.assertIn("user-local extension with the same UUID", documentation)
        self.assertIn("refuses activation", documentation)
        self.assertIn("untrusted", documentation)
        self.assertIn("not sandboxed", documentation)

    def test_package_is_reproducible_and_uses_system_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._build(root / "first")
            second = self._build(root / "second")
            self.assertEqual(first.read_bytes(), second.read_bytes())

            fields = subprocess.run(
                ["dpkg-deb", "--field", str(first)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            normalized_fields = " ".join(fields.split())
            self.assertIn("Package: copypastebin", fields)
            self.assertIn("Version: 1.1-1", fields)
            self.assertIn("Architecture: all", fields)
            self.assertIn("Maintainer: Anna Kozłowska <342168094+kozlowska-anna@users.noreply.github.com>", fields)
            self.assertIn("manual redaction", normalized_fields)
            self.assertIn("no data is sent to a cloud service", normalized_fields)
            self.assertIn("warns when sensitive content is detected", normalized_fields)
            self.assertNotIn("warns before", normalized_fields)
            subprocess.run(
                [
                    "dpkg", "--compare-versions",
                    "1.1-1", "gt", "1.0.0-1~prototype3",
                ],
                check=True,
            )

            control_dir = root / "control"
            subprocess.run(
                ["dpkg-deb", "--control", str(first), str(control_dir)],
                check=True,
                capture_output=True,
            )
            self.assertEqual(["control"], sorted(path.name for path in control_dir.iterdir()))

            synthetic_home = root / "installation" / "home" / "example"
            config = synthetic_home / ".config" / "copypastebin"
            state = synthetic_home / ".local" / "state" / "copypastebin"
            config.mkdir(parents=True)
            state.mkdir(parents=True)
            (config / "synthetic.toml").write_text("synthetic=true\n", encoding="utf-8")
            (state / "synthetic.state").write_text("synthetic\n", encoding="utf-8")

            installation = root / "installation"
            subprocess.run(
                ["dpkg-deb", "--extract", str(first), str(installation)],
                check=True,
                capture_output=True,
            )
            packaged_files = [path for path in (installation / "usr").rglob("*") if path.is_file()]
            self.assertFalse(any(path.suffix in {".so", ".a", ".o"} for path in packaged_files))
            self.assertTrue((installation / "usr/share/doc/copypastebin/copyright").is_file())
            self.assertTrue((installation / "usr/share/doc/copypastebin/LICENSE").is_file())
            for path in (installation / "usr").rglob("*"):
                with self.subTest(packaged_path=path.relative_to(installation)):
                    self.assertFalse(path.is_symlink())
                    mode = path.stat().st_mode
                    self.assertEqual(0, mode & (stat.S_ISUID | stat.S_ISGID))
                    self.assertEqual(0, mode & (stat.S_IWGRP | stat.S_IWOTH))
                    self.assertEqual(
                        0o755 if path.is_dir() or path.name == "cpb" else 0o644,
                        stat.S_IMODE(mode),
                    )
            extension = (
                installation
                / "usr"
                / "share"
                / "gnome-shell"
                / "extensions"
                / UUID
                / "extension.js"
            )
            packaged_source = extension.read_text(encoding="utf-8")
            resolver = extension.with_name("backend-path.js")
            self.assertIn("entryPoint: resolveBackendPath()", packaged_source)
            self.assertIn(
                "SYSTEM_BACKEND_PATH = '/usr/bin/cpb'",
                resolver.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                SOURCE_EXTENSION.read_text(encoding="utf-8"),
                packaged_source,
            )
            self.assertEqual(
                SOURCE_IMAGE_REDACTOR.read_text(encoding="utf-8"),
                extension.with_name("image-redactor.js").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                SOURCE_IMAGE_CORE.read_text(encoding="utf-8"),
                extension.with_name("image-redaction-core.js").read_text(encoding="utf-8"),
            )
            image_launcher = (
                installation / "usr" / "share" / "applications" /
                "io.github.copypastebin.ImageRedactor.desktop"
            )
            self.assertTrue(image_launcher.is_file())

            packaged_launcher = (
                installation / "usr" / "share" / "applications" /
                "copypastebin.desktop"
            ).read_text(encoding="utf-8")
            self.assertIn("Name=Enable CopyPasteBin", packaged_launcher)
            packaged_helper = (
                installation / "usr" / "share" / "copypastebin" /
                "enable-extension.js"
            )
            self.assertEqual(
                ENABLE_HELPER.read_text(encoding="utf-8"),
                packaged_helper.read_text(encoding="utf-8"),
            )
            packaged_metainfo = (
                installation / "usr" / "share" / "metainfo" /
                METAINFO.name
            )
            self.assertTrue(packaged_metainfo.is_file())

            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(
                installation / "usr" / "lib" / "python3" / "dist-packages"
            )
            help_result = subprocess.run(
                [str(installation / "usr" / "bin" / "cpb"), "--help"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("usage: cpb", help_result.stdout)

            packaged_state = root / "packaged-state"
            packaged_config = root / "packaged-config" / "custom-rules.toml"

            def run_packaged_ui(action, *, arguments=(), payload=""):
                completed = subprocess.run(
                    [
                        str(installation / "usr" / "bin" / "cpb"),
                        "--state-dir", str(packaged_state),
                        "--config", str(packaged_config),
                        "ui", action, *arguments,
                    ],
                    input=payload,
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
                self.assertEqual("", completed.stderr)
                return completed.stdout

            # Exercise every backend operation used by the three separate GTK
            # windows from the exact Python payload extracted from the package.
            filters = json.loads(run_packaged_ui("filters"))
            self.assertTrue(dict(filters["filters"])["EMAIL"])
            filters = json.loads(run_packaged_ui(
                "filter-set", arguments=("EMAIL", "on"),
            ))
            self.assertTrue(dict(filters["filters"])["EMAIL"])
            self.assertEqual([], json.loads(run_packaged_ui("history"))["entries"])

            self.assertEqual([], json.loads(run_packaged_ui("rules"))["rules"])
            rules_payload = json.dumps({
                "version": 3,
                "rules": [{
                    "literal": "SYNTHETIC-PACKAGED-MARKER",
                    "risk": "warning",
                    "enabled": True,
                }],
                "exclusions": [],
            })
            saved = json.loads(run_packaged_ui("rules-save", payload=rules_payload))
            self.assertEqual("SYNTHETIC-PACKAGED-MARKER", saved["rules"][0]["literal"])

            detections = json.loads(run_packaged_ui(
                "detections", payload="SYNTHETIC-PACKAGED-MARKER",
            ))
            self.assertEqual("CUSTOM_RULE", detections["detections"][0]["category"])
            self.assertNotIn("SYNTHETIC-PACKAGED-MARKER", json.dumps(detections))
            self.assertEqual(
                "[CUSTOM_RULE_1]",
                run_packaged_ui("redact", payload="SYNTHETIC-PACKAGED-MARKER"),
            )

            exclusion_request = json.dumps({
                "version": 1,
                "literal": "5.6 Sol",
                "category": "CRYPTO_AMOUNT_BTC_XRP",
            })
            exclusion = json.loads(run_packaged_ui(
                "exclusion-add", payload=exclusion_request,
            ))
            self.assertEqual("added", exclusion["status"])
            self.assertNotIn("5.6 Sol", json.dumps(exclusion))

            # A repeated extraction models package-file replacement on upgrade.
            subprocess.run(
                ["dpkg-deb", "--extract", str(second), str(installation)],
                check=True,
                capture_output=True,
            )
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())

            # The prototype owns only /usr; removing its payload cannot reach user state.
            shutil.rmtree(installation / "usr")
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())


if __name__ == "__main__":
    unittest.main()
