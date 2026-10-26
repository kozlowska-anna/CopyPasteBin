import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
PACKAGE_INIT = ROOT / "src" / "copypastebin" / "__init__.py"
ABOUT_WINDOW = (
    ROOT
    / "gnome-extension"
    / "copypastebin@kozlowska-anna.github.io"
    / "about.js"
)
OFFLINE_DOCUMENTATION = ROOT / "docs" / "offline-installation.md"
README = ROOT / "README.md"
LICENSE = ROOT / "LICENSE"
NOTICE = ROOT / "NOTICE"
INSTALLER = ROOT / "packaging" / "offline" / "install.sh"
UNINSTALLER = ROOT / "packaging" / "offline" / "uninstall.sh"
BUILDER = ROOT / "packaging" / "build-offline-bundle.sh"
INSTRUCTIONS = ROOT / "packaging" / "offline" / "README-INSTALL.txt"
FIRST_ACTIVATION_DIAGNOSTIC = (
    ROOT / "packaging" / "offline" / "diagnose-first-activation.sh"
)
WINDOW_LAUNCHER = ROOT / "packaging" / "copypastebin-window.desktop"
APP_ICON = ROOT / "packaging" / "copypastebin-app.svg"
ENABLEMENT_HELPER = ROOT / "packaging" / "persist-extension-enablement.js"
WINDOW_APPLICATION_IDS = (
    "io.github.copypastebin.Editor",
    "io.github.copypastebin.ImageRedactor",
    "io.github.copypastebin.FilterEditor",
    "io.github.copypastebin.RulesEditor",
    "io.github.copypastebin.RecentClipboard",
    "io.github.copypastebin.About",
)


class OfflineInstallerTests(unittest.TestCase):
    def test_bundle_documentation_is_bilingual_and_self_contained(self):
        import re
        source = BUILDER.read_text(encoding="utf-8")
        self.assertNotIn('"$STAGE_DIR/README-INSTALL.txt"', source)
        self.assertNotIn("README", INSTALLER.read_text(encoding="utf-8"))
        files = {name: (ROOT / "packaging/offline" / name).read_text(encoding="utf-8")
                 for name in ("README.md", "README.pl.md", "INSTALL.md", "INSTALL.pl.md")}
        targets = set(files) | {"SECURITY.md", "SECURITY.pl.md", "LICENSE", "NOTICE", "IMAGE-REDACTION.md", "IMAGE-REDACTION.pl.md"}
        for name, text in files.items():
            for target in re.findall(r'\]\(([^)]+)\)', text):
                self.assertIn(target, targets, (name, target))
        for name in ("INSTALL.md", "INSTALL.pl.md"):
            for command in ("./install.sh --check-only", "./install.sh",
                            "./uninstall.sh", "./diagnose-first-activation.sh"):
                self.assertIn(command, files[name])
            for private_path in ("~/.config/copypastebin", "~/.local/state/copypastebin"):
                self.assertIn(private_path, files[name])
        for language, filename, readme, install in (
            ("en", "website/en/index.html", "README.md", "INSTALL.md"),
            ("pl", "website/index.html", "README.pl.md", "INSTALL.pl.md"),
        ):
            page = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(f"<code>{readme}</code>", page)
            self.assertIn(f"<code>{install}</code>", page)
            self.assertIn("https://github.com/kozlowska-anna/CopyPasteBin/releases/download/v1.1/", page)


    def test_installer_is_user_local_offline_and_fail_closed(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('REQUIRED_SHELL_MAJOR="50"', source)
        self.assertIn('[[ ${EUID:', source)
        self.assertIn("--check-only", source)
        self.assertIn("sha256sum --check --strict", source)
        self.assertIn("payload nie może zawierać dowiązań symbolicznych", source)
        self.assertIn("lista sum nie obejmuje całego payloadu", source)
        self.assertIn("pip install --no-index --no-deps", source)
        self.assertIn("python3 -m venv", source)
        self.assertIn("$HOME/.local/share/copypastebin", source)
        self.assertIn("schemas/gschemas.compiled", source)
        self.assertIn("$HOME/.local/share/gnome-shell/extensions", source)
        self.assertIn("XDG_SESSION_TYPE", source)
        self.assertIn("trap rollback EXIT", source)
        self.assertIn("VENV_INSTALL_STARTED", source)
        self.assertIn("EXTENSION_INSTALL_STARTED", source)
        self.assertIn('UUID="copypastebin@kozlowska-anna.github.io"', source)
        self.assertIn('LEGACY_UUID="copypastebin@local"', source)
        self.assertIn('LEGACY_EXTENSION_BACKUP=""', source)
        self.assertIn('LEGACY_MIGRATED=false', source)
        self.assertIn('LEGACY_MIGRATED=true', source)
        self.assertIn('gnome-extensions disable "$LEGACY_UUID"', source)
        self.assertIn('mv -- "$LEGACY_EXTENSION_BACKUP" "$LEGACY_EXTENSION_DIR"', source)
        self.assertIn('safe_remove_tree "$LEGACY_EXTENSION_BACKUP"', source)
        self.assertIn('[[ ! -L "$LEGACY_EXTENSION_DIR" ]]', source)
        self.assertIn('if $LEGACY_MIGRATED; then', source)
        self.assertIn('persist-extension-enablement.js', source)
        self.assertIn('gnome-extensions enable "$UUID" >/dev/null 2>&1 || true', source)
        self.assertNotIn('chmod 700 -- "$APP_DIR" "$EXTENSIONS_DIR"', source)
        for forbidden in ("sudo apt", "sudo cp", "curl ", "wget ", "http://", "https://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_uninstaller_preserves_private_state(self):
        source = UNINSTALLER.read_text(encoding="utf-8")
        self.assertIn("Ustawienia i historia pozostały", source)
        self.assertNotIn("rm -rf -- \"$HOME/.config", source)
        self.assertNotIn("rm -rf -- \"$HOME/.local/state", source)
        self.assertIn('LEGACY_UUID="copypastebin@local"', source)
        self.assertIn('gnome-extensions disable "$LEGACY_UUID"', source)
        self.assertIn(
            'rm -rf -- "$APP_DIR" "$EXTENSION_DIR" "$LEGACY_EXTENSION_DIR"',
            source,
        )

    def test_bundle_builder_includes_only_product_payload(self):
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn("pip wheel --no-deps --no-build-isolation", source)
        self.assertIn('UUID="copypastebin@kozlowska-anna.github.io"', source)
        self.assertIn('gnome-extension/$UUID', source)
        self.assertIn("glib-compile-schemas", source)
        self.assertIn("SHA256SUMS", source)
        self.assertIn('cp -- "$ROOT/LICENSE" "$STAGE_DIR/LICENSE"', source)
        self.assertIn('cp -- "$ROOT/NOTICE" "$STAGE_DIR/NOTICE"', source)
        self.assertIn(
            '"$STAGE_DIR/diagnose-first-activation.sh"', source
        )
        self.assertIn(
            '"$PAYLOAD_DIR/persist-extension-enablement.js"', source
        )
        self.assertIn("GNU GENERAL PUBLIC LICENSE", LICENSE.read_text(encoding="utf-8"))
        self.assertIn("BSD-3-Clause", NOTICE.read_text(encoding="utf-8"))
        for forbidden in (".config/copypastebin", ".local/state/copypastebin"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_release_version_is_consistent(self):
        expected = "1.1"
        self.assertIn(f'version = "{expected}"', PYPROJECT.read_text(encoding="utf-8"))
        self.assertIn(
            f'__version__ = "{expected}"',
            PACKAGE_INIT.read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"const VERSION = '{expected}'",
            ABOUT_WINDOW.read_text(encoding="utf-8"),
        )
        self.assertIn(
            f'readonly VERSION="{expected}"',
            BUILDER.read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"COPYPASTEBIN {expected} - INSTALACJA OFFLINE",
            INSTRUCTIONS.read_text(encoding="utf-8"),
        )
        archive_name = f"CopyPasteBin-linux-{expected}.tar.gz"
        self.assertIn(archive_name, README.read_text(encoding="utf-8"))
        self.assertIn(
            archive_name,
            OFFLINE_DOCUMENTATION.read_text(encoding="utf-8"),
        )

    def test_release_archive_has_normalized_metadata_and_no_silent_overwrite(self):
        source = BUILDER.read_text(encoding="utf-8")

        for expected in (
            "umask 022",
            'readonly SOURCE_DATE_EPOCH="1792454400"',
            'readonly BUILD_SOURCE_DIR="$WORK_DIR/source"',
            'cp -a -- "$ROOT/src/." "$BUILD_SOURCE_DIR/src/"',
            'find "$BUILD_SOURCE_DIR" -type f -exec chmod 0644',
            '"$BUILD_SOURCE_DIR" >/dev/null',
            "find \"$STAGE_DIR\" -type f -exec chmod 0444",
            "chmod 0555 -- \"$STAGE_DIR/install.sh\"",
            "find \"$STAGE_DIR\" -type d -exec chmod 0555",
            "--sort=name",
            "--mtime=\"@$SOURCE_DATE_EPOCH\"",
            "--owner=0 --group=0 --numeric-owner",
            'cmp -s -- "$candidate_archive" "$archive"',
            "Zmień wersję zamiast go nadpisywać",
            'chmod 0444 -- "$archive"',
            'mv -f -- "$checksum_tmp" "$DIST_DIR/SHA256SUMS"',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, source)

    def test_enablement_helper_has_closed_preserving_update(self):
        source = ENABLEMENT_HELPER.read_text(encoding="utf-8")

        self.assertIn("settings.get_strv(KEY)", source)
        self.assertIn("value !== UUID && value !== LEGACY_UUID", source)
        self.assertIn("updated.push(UUID)", source)
        self.assertIn("settings.set_strv(KEY, updated)", source)
        self.assertIn("settings.is_writable(KEY)", source)
        self.assertIn("Gio.Settings.sync()", source)
        for forbidden in ("print(", "log(", "spawn", "Subprocess", "clipboard"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    @unittest.skipUnless(
        Path("/usr/bin/gjs").is_file() and Path("/usr/bin/gsettings").is_file(),
        "GJS and GSettings are required for the installer integration test",
    )
    def test_enablement_helper_updates_only_cpb_in_synthetic_gsettings(self):
        public_uuid = "copypastebin@kozlowska-anna.github.io"
        legacy_uuid = "copypastebin@local"
        other_uuid = "unrelated@example.invalid"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            config = root / "config"
            home.mkdir()
            config.mkdir()
            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "XDG_CONFIG_HOME": str(config),
                    "GSETTINGS_BACKEND": "keyfile",
                }
            )
            initial = f"['{other_uuid}', '{legacy_uuid}']"
            try:
                subprocess.run(
                    [
                        "/usr/bin/gsettings",
                        "set",
                        "org.gnome.shell",
                        "enabled-extensions",
                        initial,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
            except subprocess.CalledProcessError:
                self.skipTest("org.gnome.shell schema is unavailable")

            subprocess.run(
                ["/usr/bin/gjs", str(ENABLEMENT_HELPER)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            completed = subprocess.run(
                [
                    "/usr/bin/gsettings",
                    "get",
                    "org.gnome.shell",
                    "enabled-extensions",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

        self.assertEqual(
            f"['{other_uuid}', '{public_uuid}']",
            completed.stdout.strip(),
        )

    def test_window_application_ids_map_to_hidden_product_icon_launchers(self):
        builder = BUILDER.read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        uninstaller = UNINSTALLER.read_text(encoding="utf-8")
        launcher = WINDOW_LAUNCHER.read_text(encoding="utf-8")
        extension_dir = ROOT / "gnome-extension" / "copypastebin@kozlowska-anna.github.io"

        self.assertIn("Icon=copypastebin", launcher)
        self.assertIn("NoDisplay=true", launcher)
        self.assertNotIn("OnlyShowIn=", launcher)
        for application_id in WINDOW_APPLICATION_IDS:
            with self.subTest(application_id=application_id):
                self.assertIn(application_id, builder)
                self.assertIn(application_id, installer)
                self.assertIn(application_id, uninstaller)
                self.assertTrue(any(
                    f"application_id: '{application_id}'" in path.read_text(encoding="utf-8")
                    for path in extension_dir.glob("*.js")
                ))

    def test_application_icon_is_scalable_modern_and_separate_from_tray_icon(self):
        builder = BUILDER.read_text(encoding="utf-8")
        icon = APP_ICON.read_text(encoding="utf-8")

        self.assertIn('viewBox="0 0 128 128"', icon)
        self.assertIn('<linearGradient id="navy-paper"', icon)
        self.assertIn('<linearGradient id="blue-outline"', icon)
        self.assertIn('<linearGradient id="risk-low"', icon)
        self.assertIn('<linearGradient id="risk-medium"', icon)
        self.assertIn('<linearGradient id="risk-high"', icon)
        self.assertIn('<linearGradient id="risk-critical"', icon)
        self.assertIn('<filter id="document-shadow"', icon)
        self.assertIn('<filter id="outline-glow"', icon)
        self.assertIn('stroke-width="4"', icon)
        self.assertIn('#2e6da8', icon)
        self.assertIn('#986300', icon)
        self.assertIn('#b71931', icon)
        self.assertIn('#730a1b', icon)
        self.assertNotIn('id="tile"', icon)
        self.assertNotIn("http://", icon.replace("http://www.w3.org/2000/svg", ""))
        self.assertNotIn("https://", icon)
        self.assertIn(
            'cp -- "$ROOT/packaging/copypastebin-app.svg" "$PAYLOAD_DIR/copypastebin.svg"',
            builder,
        )
        self.assertNotIn(
            'cp -- "$ROOT/gnome-extension/$UUID/icon-active.svg" "$PAYLOAD_DIR/copypastebin.svg"',
            builder,
        )

    def test_user_instructions_explain_check_install_and_logout(self):
        text = INSTRUCTIONS.read_text(encoding="utf-8")
        self.assertIn("Autorka: Anna Kozłowska", text)
        self.assertIn("ChatGPT i Codex od OpenAI", text)
        self.assertIn("nie jest oficjalnym produktem", text)
        self.assertIn("./install.sh --check-only", text)
        self.assertIn("./install.sh", text)
        self.assertIn("Wyloguj się i zaloguj ponownie", text)
        self.assertIn("./diagnose-first-activation.sh", text)
        self.assertIn("./uninstall.sh", text)
        self.assertIn("nie przenosi ustawień, historii ani zawartości", text)

    def test_first_activation_diagnostic_is_read_only_and_redacted(self):
        source = FIRST_ACTIVATION_DIAGNOSTIC.read_text(encoding="utf-8")

        self.assertIn("COPYPASTEBIN_FIRST_ACTIVATION_DIAGNOSTIC=1", source)
        self.assertIn("capture_phase=after-login-before-launcher", source)
        self.assertIn('gnome-extensions}', source)
        self.assertIn("info \"$UUID\"", source)
        self.assertIn("list --enabled", source)
        self.assertIn("disable-user-extensions", source)
        self.assertIn("enabled-extensions", source)
        self.assertIn("contains_public_uuid", source)
        self.assertIn("contains_legacy_uuid", source)
        self.assertIn("report.contains_clipboard_or_private_cpb_data=false", source)
        self.assertIn("report.changed_system_state=false", source)
        self.assertIn("-eq 0", source)
        for forbidden in (
            "gsettings set",
            "gnome-extensions enable",
            "gnome-extensions disable",
            ".config/copypastebin",
            ".local/state/copypastebin",
            "wl-paste",
            "xclip",
            "xsel",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_first_activation_diagnostic_reports_only_scoped_state(self):
        public_uuid = "copypastebin@kozlowska-anna.github.io"
        other_uuid = "private-other-extension@example.invalid"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            extension = (
                home
                / ".local/share/gnome-shell/extensions"
                / public_uuid
            )
            extension.mkdir(parents=True)

            gnome_extensions = root / "gnome-extensions"
            gnome_extensions.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"info\" ]]; then\n"
                f"  printf '%s\\n' \"{public_uuid}\" \"  State: DISABLED\" "
                f"\"  Path: {home}/private-path\"\n"
                "elif [[ \"$1\" == \"list\" && \"${2:-}\" == \"--enabled\" ]]; then\n"
                f"  printf '%s\\n' \"{other_uuid}\"\n"
                "elif [[ \"$1\" == \"list\" ]]; then\n"
                f"  printf '%s\\n' \"{public_uuid}\" \"{other_uuid}\"\n"
                "else\n"
                "  exit 2\n"
                "fi\n",
                encoding="utf-8",
            )
            gnome_extensions.chmod(0o755)

            gnome_shell = root / "gnome-shell"
            gnome_shell.write_text(
                "#!/usr/bin/env bash\nprintf '%s\\n' 'GNOME Shell 50.1'\n",
                encoding="utf-8",
            )
            gnome_shell.chmod(0o755)

            gsettings = root / "gsettings"
            gsettings.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$3\" == \"disable-user-extensions\" ]]; then\n"
                "  printf '%s\\n' 'true'\n"
                "else\n"
                f"  printf \"['{public_uuid}', '{other_uuid}']\\n\"\n"
                "fi\n",
                encoding="utf-8",
            )
            gsettings.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": str(home),
                    "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
                    "XDG_SESSION_TYPE": "wayland",
                    "CPB_DIAGNOSTIC_GNOME_EXTENSIONS_BIN": str(gnome_extensions),
                    "CPB_DIAGNOSTIC_GNOME_SHELL_BIN": str(gnome_shell),
                    "CPB_DIAGNOSTIC_GSETTINGS_BIN": str(gsettings),
                }
            )
            completed = subprocess.run(
                [str(FIRST_ACTIVATION_DIAGNOSTIC)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

        report = completed.stdout
        self.assertIn("gnome.shell=GNOME Shell 50.1", report)
        self.assertIn("extension.directory=present", report)
        self.assertIn("gnome.info.state=DISABLED", report)
        self.assertIn("gnome.list.contains_public_uuid=true", report)
        self.assertIn("gnome.enabled_list.contains_public_uuid=false", report)
        self.assertIn("gsettings.disable_user_extensions=true", report)
        self.assertIn(
            "gsettings.enabled_extensions.contains_public_uuid=true", report
        )
        self.assertNotIn(other_uuid, report)
        self.assertNotIn("private-path", report)
        self.assertNotIn(str(home), report)


if __name__ == "__main__":
    unittest.main()
