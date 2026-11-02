Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "packaging" / "deb" / "build-deb.sh"
SOURCE_BUILDER = ROOT / "packaging" / "deb" / "build-source-package.sh"
APT_REPOSITORY_TEST = ROOT / "packaging" / "deb" / "test-signed-apt-repository.sh"
README = ROOT / "packaging" / "deb" / "README.Debian"
DEB_LAUNCHER = ROOT / "packaging" / "deb" / "copypastebin.desktop"
ENABLE_HELPER = ROOT / "packaging" / "deb" / "enable-extension.js"
ICON_CACHE_HELPER = ROOT / "packaging" / "offline" / "refresh-user-icon-cache.sh"
METAINFO = ROOT / "packaging" / "deb" / "io.github.kozlowska_anna.CopyPasteBin.metainfo.xml"
DEBIAN_DIR = ROOT / "debian"
DEBIAN_CONTROL = DEBIAN_DIR / "control"
DEBIAN_CHANGELOG = DEBIAN_DIR / "changelog"
DEBIAN_RULES = DEBIAN_DIR / "rules"
DEBIAN_ENABLE_HELPER = DEBIAN_DIR / "enable-extension.js"
DEBIAN_ICON_CACHE_HELPER = DEBIAN_DIR / "refresh-user-icon-cache"
UUID = "copypastebin@kozlowska-anna.github.io"
VERSION = subprocess.run(
    ["dpkg-parsechangelog", "-l", str(DEBIAN_CHANGELOG), "-S", "Version"],
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()
OLD_VERSION = "1.1-2~ppa2"
PACKAGE_NAMES = (
    "copypastebin-backend",
    "gnome-shell-extension-copypastebin",
    "copypastebin",
)
SOURCE_EXTENSION_DIR = ROOT / "gnome-extension" / UUID


class DebPackagingTests(unittest.TestCase):
    def _build(self, destination: Path) -> dict[str, Path]:
        environment = os.environ.copy()
        environment["CPB_DEB_DIST_DIR"] = str(destination)
        completed = subprocess.run(
            [str(BUILDER)],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        packages = {
            subprocess.run(
                ["dpkg-deb", "--field", line, "Package"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(): Path(line)
            for line in completed.stdout.splitlines()
            if line.strip().endswith(".deb")
        }
        self.assertEqual(set(PACKAGE_NAMES), set(packages))
        self.assertTrue(all(path.is_file() for path in packages.values()))
        return packages

    def _fields(self, package: Path) -> str:
        return subprocess.run(
            ["dpkg-deb", "--field", str(package)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def _extract(self, package: Path, destination: Path) -> None:
        subprocess.run(
            ["dpkg-deb", "--extract", str(package), str(destination)],
            check=True,
            capture_output=True,
        )

    def _payload_paths(self, package: Path) -> set[str]:
        completed = subprocess.run(
            ["dpkg-deb", "--fsys-tarfile", str(package)],
            check=True,
            stdout=subprocess.PIPE,
        )
        listed = subprocess.run(
            ["tar", "-tf", "-"],
            input=completed.stdout,
            check=True,
            capture_output=True,
        ).stdout.decode().splitlines()
        return {path.removeprefix("./") for path in listed if not path.endswith("/")}

    def _make_old_monolith(self, root: Path) -> Path:
        stage = root / "old-stage"
        control = stage / "DEBIAN" / "control"
        control.parent.mkdir(parents=True)
        control.write_text(
            "Package: copypastebin\n"
            f"Version: {OLD_VERSION}\n"
            "Section: utils\n"
            "Priority: optional\n"
            "Architecture: all\n"
            "Maintainer: Synthetic Migration Test <noreply@example.invalid>\n"
            "Description: synthetic CopyPasteBin 1.1 monolith\n",
            encoding="utf-8",
        )
        old_backend = stage / "usr" / "bin" / "cpb"
        old_backend.parent.mkdir(parents=True)
        old_backend.write_text("synthetic old backend\n", encoding="utf-8")
        old_backend.chmod(0o755)
        old_extension = (
            stage / "usr" / "share" / "gnome-shell" / "extensions" / UUID /
            "extension.js"
        )
        old_extension.parent.mkdir(parents=True)
        old_extension.write_text("// synthetic old extension\n", encoding="utf-8")
        package = root / f"copypastebin_{OLD_VERSION}_all.deb"
        subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", str(stage), str(package)],
            check=True,
            capture_output=True,
        )
        return package

    def _simulate_apt_upgrade(self, root: Path, packages: dict[str, Path]) -> str:
        repository = root / "repository"
        repository.mkdir()
        for package in packages.values():
            shutil.copy2(package, repository / package.name)
        scanned = subprocess.run(
            ["dpkg-scanpackages", ".", "/dev/null"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )
        (repository / "Packages").write_text(scanned.stdout, encoding="utf-8")

        client = root / "apt-client"
        lists = client / "lists"
        archives = client / "cache" / "archives"
        (lists / "partial").mkdir(parents=True)
        (archives / "partial").mkdir(parents=True)
        source = client / "sources.list"
        source.write_text(
            f"deb [trusted=yes] file:{repository} ./\n",
            encoding="utf-8",
        )
        installed = {
            "copypastebin": OLD_VERSION,
            "python3": "3.14.0-1",
            "gir1.2-gdkpixbuf-2.0": "2.44.0-1",
            "gir1.2-glib-2.0": "2.86.0-1",
            "gir1.2-gtk-4.0": "4.20.0-1",
            "gjs": "1.86.0-1",
            "gnome-shell": "50.0-1",
        }
        status = client / "status"
        status.write_text(
            "\n".join(
                "\n".join((
                    f"Package: {name}",
                    "Status: install ok installed",
                    "Priority: optional",
                    "Section: utils",
                    "Architecture: all",
                    f"Version: {version}",
                    f"Description: synthetic installed {name}",
                    "",
                ))
                for name, version in installed.items()
            ),
            encoding="utf-8",
        )
        options = [
            "-o", f"Dir::Etc::sourcelist={source}",
            "-o", "Dir::Etc::sourceparts=-",
            "-o", f"Dir::State::status={status}",
            "-o", f"Dir::State::lists={lists}",
            "-o", f"Dir::Cache={client / 'cache'}",
            "-o", f"Dir::Cache::archives={archives}",
            "-o", "APT::Get::List-Cleanup=0",
            "-o", "Acquire::Languages=none",
            "-o", "Debug::NoLocking=1",
            "-o", f"APT::Sandbox::User={os.environ.get('USER', 'nobody')}",
        ]
        environment = {**os.environ, "LC_ALL": "C.UTF-8"}
        subprocess.run(
            ["apt-get", *options, "update"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return subprocess.run(
            ["apt-get", *options, "--simulate", "install", "copypastebin"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        ).stdout

    def test_builder_is_standard_offline_bounded_and_has_no_maintainer_scripts(self):
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn("dpkg-buildpackage --build=binary --no-sign", source)
        self.assertIn("dpkg-parsechangelog", source)
        self.assertIn('"$DIST_DIR" = /*', source)
        self.assertIn('"copypastebin-backend"', source)
        self.assertIn('"gnome-shell-extension-copypastebin"', source)
        self.assertIn('"copypastebin"', source)
        self.assertNotIn("packaging/deb/control", source)
        self.assertFalse((ROOT / "packaging" / "deb" / "control").exists())
        self.assertFalse((ROOT / "packaging" / "deb" / "copyright").exists())
        for forbidden in (
            "curl ", "wget ", "sudo ", "$HOME", ".config/copypastebin",
            ".local/state/copypastebin", "dput ", "debsign ",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        for maintainer_script in ("preinst", "postinst", "prerm", "postrm"):
            self.assertFalse((DEBIAN_DIR / maintainer_script).exists())
        self.assertTrue(BUILDER.stat().st_mode & stat.S_IXUSR)

    def test_source_package_defines_three_exactly_matched_binary_packages(self):
        control = DEBIAN_CONTROL.read_text(encoding="utf-8")
        rules = DEBIAN_RULES.read_text(encoding="utf-8")
        paragraphs = {
            paragraph.splitlines()[0].removeprefix("Package: "): paragraph
            for paragraph in control.split("\n\n")
            if paragraph.startswith("Package: ")
        }
        self.assertEqual(set(PACKAGE_NAMES), set(paragraphs))
        backend = paragraphs["copypastebin-backend"]
        extension = paragraphs["gnome-shell-extension-copypastebin"]
        complete = paragraphs["copypastebin"]
        self.assertIn("python3 (>= 3.11)", backend)
        self.assertNotIn("gnome-shell", backend)
        self.assertNotIn("gir1.2-", backend)
        self.assertIn("copypastebin-backend (= ${binary:Version})", extension)
        self.assertIn("gnome-shell (>= 50~)", extension)
        self.assertIn("gnome-shell (<< 51~)", extension)
        self.assertIn("copypastebin-backend (= ${binary:Version})", complete)
        self.assertIn(
            "gnome-shell-extension-copypastebin (= ${binary:Version})", complete
        )
        for owner in (backend, extension):
            self.assertIn("Breaks: copypastebin (<< 1.2~)", owner)
            self.assertIn("Replaces: copypastebin (<< 1.2~)", owner)
        self.assertNotIn("Breaks:", complete)
        self.assertIn("BACKEND_ROOT = debian/copypastebin-backend", rules)
        self.assertIn(
            "EXTENSION_ROOT = debian/gnome-shell-extension-copypastebin", rules
        )
        self.assertNotIn("glib-compile-schemas", rules)
        self.assertIn('__version__ = "1.2"', rules)
        self.assertIn("const VERSION = '1.2';", rules)
        self.assertIn('\"version\": 7', rules)
        self.assertNotIn("1.2.dev0", rules)
        self.assertNotIn("1.2-dev", rules)
        self.assertNotIn("--with python3", rules)

        changelog = subprocess.run(
            ["dpkg-parsechangelog", "-l", str(DEBIAN_CHANGELOG)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn(f"Version: {VERSION}", changelog)
        self.assertIn("Distribution: resolute", changelog)
        subprocess.run(
            ["dpkg", "--compare-versions", VERSION, "gt", OLD_VERSION], check=True
        )
        subprocess.run(
            ["dpkg", "--compare-versions", VERSION, "ge", "1.2"], check=True
        )

        self.assertEqual(
            ENABLE_HELPER.read_text(encoding="utf-8"),
            DEBIAN_ENABLE_HELPER.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            ICON_CACHE_HELPER.read_text(encoding="utf-8"),
            DEBIAN_ICON_CACHE_HELPER.read_text(encoding="utf-8"),
        )
        tests_control = (DEBIAN_DIR / "tests" / "control").read_text(encoding="utf-8")
        self.assertIn("Tests: backend-only", tests_control)
        self.assertIn("Depends: copypastebin-backend", tests_control)
        self.assertIn("Tests: smoke", tests_control)
        self.assertTrue((DEBIAN_DIR / "tests" / "backend-only").stat().st_mode & stat.S_IXUSR)

    def test_source_builder_and_packaging_are_bounded_and_do_not_enroll_apt(self):
        readme = " ".join(
            (DEBIAN_DIR / "README.source").read_text(encoding="utf-8").split()
        )
        self.assertIn("three binary packages", readme)
        self.assertIn("Repository enrollment is a separate", readme)
        self.assertIn("must never be stored in this source tree", readme)

        source_builder = SOURCE_BUILDER.read_text(encoding="utf-8")
        self.assertIn('UPSTREAM_VERSION="1.2"', source_builder)
        self.assertIn('SOURCE_REF="${CPB_DEB_SOURCE_REF:-HEAD}"', source_builder)
        self.assertIn('"$DIST_DIR" = /*', source_builder)
        self.assertIn("git -C \"$ROOT\" archive", source_builder)
        self.assertIn('rm -rf -- "$UPSTREAM_DIR/debian"', source_builder)
        self.assertIn('"$ROOT/debian/copypastebin-backend"', source_builder)
        self.assertIn('"$ROOT/debian/gnome-shell-extension-copypastebin"', source_builder)
        self.assertIn("dpkg-source -b .", source_builder)
        self.assertNotIn("gpg ", source_builder)
        self.assertNotIn("dput ", source_builder)
        self.assertNotIn("debsign ", source_builder)

        forbidden_fragments = (
            "apt-key", "add-apt-repository", "/etc/apt/", "curl ", "wget ",
            "sudo ", "systemctl ", "launchpad.net", "ppa.launchpadcontent.net",
        )
        packaging_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in DEBIAN_DIR.rglob("*")
            if path.is_file()
        )
        for forbidden in forbidden_fragments:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, packaging_text)

        apt_test = APT_REPOSITORY_TEST.read_text(encoding="utf-8")
        self.assertIn("CopyPasteBin disposable APT test key", apt_test)
        self.assertIn("tampered repository rejection: PASS", apt_test)
        self.assertNotIn("sudo ", apt_test)
        self.assertNotIn("apt-key", apt_test)

    def test_source_package_is_reproducible_and_keeps_debian_out_of_orig(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builds = []
            for name in ("first", "second"):
                destination = root / name
                environment = {
                    **os.environ,
                    "CPB_DEB_SOURCE_REF": "HEAD",
                    "CPB_DEB_SOURCE_DIST_DIR": str(destination),
                }
                completed = subprocess.run(
                    [str(SOURCE_BUILDER)],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
                artifacts = [
                    Path(line) for line in completed.stdout.splitlines()
                    if Path(line).is_absolute() and Path(line).is_file()
                ]
                self.assertEqual(3, len(artifacts))
                builds.append({path.name: path for path in artifacts})
            self.assertEqual(set(builds[0]), set(builds[1]))
            for name in builds[0]:
                self.assertEqual(builds[0][name].read_bytes(), builds[1][name].read_bytes())

            orig = next(path for name, path in builds[0].items() if name.endswith(".orig.tar.gz"))
            listing = subprocess.run(
                ["tar", "-tzf", str(orig)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            self.assertFalse(any("/debian/" in path for path in listing))

            dsc = next(path for name, path in builds[0].items() if name.endswith(".dsc"))
            debian_tar = next(
                path for name, path in builds[0].items()
                if name.endswith(".debian.tar.xz")
            )
            with tarfile.open(debian_tar, "r:xz") as archive:
                members = {member.name: member for member in archive.getmembers()}
            self.assertEqual(0o644, members["debian/control"].mode)
            for relative in (
                "refresh-user-icon-cache",
                "rules",
                "tests/backend-only",
                "tests/smoke",
            ):
                self.assertEqual(0o755, members[f"debian/{relative}"].mode)

            extracted = root / "extracted-source"
            subprocess.run(
                ["dpkg-source", "--extract", str(dsc), str(extracted)],
                check=True,
                capture_output=True,
                text=True,
            )
            extracted_control = (extracted / "debian" / "control").read_text(
                encoding="utf-8"
            )
            for package in PACKAGE_NAMES:
                self.assertIn(f"Package: {package}\n", extracted_control)

            subprocess.run(
                ["dpkg-buildpackage", "--build=binary", "--no-sign"],
                cwd=extracted,
                check=True,
                capture_output=True,
                text=True,
            )
            direct = self._build(root / "direct-binary")
            for package in PACKAGE_NAMES:
                source_built = root / f"{package}_{VERSION}_all.deb"
                self.assertTrue(source_built.is_file())
                self.assertEqual(direct[package].read_bytes(), source_built.read_bytes())

    def test_first_start_and_appstream_metadata_are_explicit_and_honest(self):
        launcher = DEB_LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("Name=CopyPasteBin\n", launcher)
        self.assertNotIn("\nName[pl]=", launcher)
        self.assertIn(
            "Exec=/usr/bin/gjs -m /usr/share/copypastebin/enable-extension.js",
            launcher,
        )
        self.assertNotIn("sudo", launcher)
        helper = ENABLE_HELPER.read_text(encoding="utf-8")
        self.assertIn("Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS", helper)
        self.assertIn("'/usr/bin/gnome-extensions', 'enable', UUID", helper)
        self.assertIn("'.local', 'share', 'gnome-shell', 'extensions', UUID", helper)
        self.assertIn("'/usr/libexec/copypastebin/refresh-user-icon-cache'", helper)
        self.assertNotIn("delete(", helper)
        component = ET.parse(METAINFO).getroot()
        self.assertEqual("desktop-application", component.attrib["type"])
        self.assertEqual("FSFAP", component.findtext("metadata_license"))
        self.assertEqual("GPL-3.0-or-later", component.findtext("project_license"))
        self.assertEqual("copypastebin.desktop", component.findtext("launchable"))
        self.assertEqual("copypastebin", component.find("icon").text)
        self.assertEqual("Anna Kozłowska", component.find("developer/name").text)
        self.assertEqual(
            "1.2",
            component.find("releases/release").attrib["version"],
        )

        documentation = " ".join(README.read_text(encoding="utf-8").split())
        self.assertIn("exactly matching", documentation)
        self.assertIn("does not enable the extension", documentation)
        self.assertIn("preserves ~/.config/copypastebin", documentation)
        self.assertIn("~/.local/state/copypastebin", documentation)
        self.assertIn("Removing only the extension package leaves the backend", documentation)

    def test_split_packages_are_reproducible_disjoint_and_runnable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._build(root / "first")
            second = self._build(root / "second")
            (root / "controls").mkdir()
            for name in PACKAGE_NAMES:
                self.assertEqual(first[name].read_bytes(), second[name].read_bytes())
                fields = self._fields(first[name])
                self.assertIn(f"Package: {name}\n", fields)
                self.assertIn(f"Version: {VERSION}\n", fields)
                self.assertIn("Architecture: all\n", fields)
                control_dir = root / "controls" / name
                subprocess.run(
                    ["dpkg-deb", "--control", str(first[name]), str(control_dir)],
                    check=True,
                    capture_output=True,
                )
                self.assertTrue(
                    {path.name for path in control_dir.iterdir()} <= {"control", "md5sums"}
                )
                for maintainer_script in ("preinst", "postinst", "prerm", "postrm"):
                    self.assertFalse((control_dir / maintainer_script).exists())

            backend_fields = self._fields(first["copypastebin-backend"])
            extension_fields = self._fields(first["gnome-shell-extension-copypastebin"])
            complete_fields = self._fields(first["copypastebin"])
            self.assertIn(f"Breaks: copypastebin (<< 1.2~)\n", backend_fields)
            self.assertIn(f"Replaces: copypastebin (<< 1.2~)\n", backend_fields)
            self.assertIn(f"Breaks: copypastebin (<< 1.2~)\n", extension_fields)
            self.assertIn(f"Replaces: copypastebin (<< 1.2~)\n", extension_fields)
            self.assertIn(f"copypastebin-backend (= {VERSION})", extension_fields)
            self.assertIn(f"copypastebin-backend (= {VERSION})", complete_fields)
            self.assertIn(
                f"gnome-shell-extension-copypastebin (= {VERSION})", complete_fields
            )

            payloads = {name: self._payload_paths(first[name]) for name in PACKAGE_NAMES}
            backend = payloads["copypastebin-backend"]
            extension = payloads["gnome-shell-extension-copypastebin"]
            complete = payloads["copypastebin"]
            self.assertIn("usr/bin/cpb", backend)
            self.assertTrue(any(path.startswith("usr/lib/python3/dist-packages/copypastebin/") for path in backend))
            self.assertIn("usr/share/man/man1/cpb.1.gz", backend)
            self.assertFalse(any("gnome-shell/extensions" in path for path in backend))
            self.assertIn(f"usr/share/gnome-shell/extensions/{UUID}/extension.js", extension)
            self.assertIn(f"usr/share/gnome-shell/extensions/{UUID}/backend-probe.js", extension)
            self.assertIn(f"usr/share/gnome-shell/extensions/{UUID}/bridge-worker.js", extension)
            self.assertIn(f"usr/share/gnome-shell/extensions/{UUID}/extension-channel.js", extension)
            self.assertIn("usr/share/applications/copypastebin.desktop", extension)
            self.assertIn("usr/libexec/copypastebin/refresh-user-icon-cache", extension)
            self.assertNotIn("usr/bin/cpb", extension)
            self.assertFalse(any("python3/dist-packages" in path for path in extension))
            self.assertTrue(complete)
            self.assertTrue(all(
                path.startswith("usr/share/doc/copypastebin/") or
                path == "usr/share/lintian/overrides/copypastebin"
                for path in complete
            ))
            self.assertTrue(backend.isdisjoint(extension))

            backend_root = root / "backend-only"
            self._extract(first["copypastebin-backend"], backend_root)
            self.assertTrue((backend_root / "usr/bin/cpb").is_file())
            self.assertFalse((backend_root / "usr/share/gnome-shell").exists())
            environment = {
                **os.environ,
                "PYTHONPATH": str(backend_root / "usr/lib/python3/dist-packages"),
            }
            capabilities = subprocess.run(
                [str(backend_root / "usr/bin/cpb"), "bridge", "capabilities"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            capability_document = json.loads(capabilities.stdout)
            self.assertEqual(2, capability_document["protocol_version"])
            self.assertEqual("1.2", capability_document["product_version"])
            analyzed = subprocess.run(
                [
                    str(backend_root / "usr/bin/cpb"),
                    "--state-dir", str(root / "packaged-state"),
                    "--config", str(root / "missing.toml"),
                    "--purpose", "email",
                ],
                input="synthetic@example.invalid\n",
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertIn("risk=medium", analyzed.stdout)
            self.assertIn("category=EMAIL count=1", analyzed.stdout)
            self.assertNotIn("synthetic@example.invalid", analyzed.stdout)

            full_root = root / "complete"
            for name in PACKAGE_NAMES:
                self._extract(first[name], full_root)
            extension_file = (
                full_root / "usr/share/gnome-shell/extensions" / UUID / "extension.js"
            )
            self.assertEqual(
                (SOURCE_EXTENSION_DIR / "extension.js").read_text(encoding="utf-8"),
                extension_file.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (SOURCE_EXTENSION_DIR / "backend-probe.js").read_text(encoding="utf-8"),
                extension_file.with_name("backend-probe.js").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (SOURCE_EXTENSION_DIR / "extension-channel.js").read_text(encoding="utf-8"),
                extension_file.with_name("extension-channel.js").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (SOURCE_EXTENSION_DIR / "bridge-worker.js").read_text(encoding="utf-8"),
                extension_file.with_name("bridge-worker.js").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "const VERSION = '1.2';",
                extension_file.with_name("about.js").read_text(encoding="utf-8"),
            )
            metadata = json.loads(
                extension_file.with_name("metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(7, metadata["version"])
            self.assertIn(
                '__version__ = "1.2"',
                (ROOT / "src" / "copypastebin" / "__init__.py").read_text(
                    encoding="utf-8"
                ),
            )
            packaged_files = [
                path for path in (full_root / "usr").rglob("*") if path.is_file()
            ]
            self.assertFalse(any(path.suffix in {".so", ".a", ".o"} for path in packaged_files))
            for path in (full_root / "usr").rglob("*"):
                with self.subTest(packaged_path=path.relative_to(full_root)):
                    self.assertFalse(path.is_symlink())
                    mode = path.stat().st_mode
                    self.assertEqual(0, mode & (stat.S_ISUID | stat.S_ISGID))
                    self.assertEqual(0, mode & (stat.S_IWGRP | stat.S_IWOTH))

    def test_ppa2_monolith_migrates_to_split_packages_without_state_loss(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packages = self._build(root / "new")
            old_package = self._make_old_monolith(root)
            apt_plan = self._simulate_apt_upgrade(root, packages)
            self.assertIn(f"Inst copypastebin [{OLD_VERSION}] ({VERSION}", apt_plan)
            self.assertIn(f"Inst copypastebin-backend ({VERSION}", apt_plan)
            self.assertIn(
                f"Inst gnome-shell-extension-copypastebin ({VERSION}", apt_plan
            )
            self.assertNotIn("Remv copypastebin", apt_plan)

            installation = root / "installation"
            home = installation / "home" / "example"
            config = home / ".config" / "copypastebin"
            state = home / ".local" / "state" / "copypastebin"
            config.mkdir(parents=True)
            state.mkdir(parents=True)
            (config / "synthetic.toml").write_text("synthetic=true\n", encoding="utf-8")
            (state / "synthetic.state").write_text("synthetic\n", encoding="utf-8")

            self._extract(old_package, installation)
            old_extension = installation / "usr/share/gnome-shell/extensions" / UUID
            self.assertIn(
                "synthetic old extension",
                (old_extension / "extension.js").read_text(encoding="utf-8"),
            )
            for name in PACKAGE_NAMES:
                self._extract(packages[name], installation)
            self.assertNotIn(
                "synthetic old extension",
                (old_extension / "extension.js").read_text(encoding="utf-8"),
            )
            self.assertTrue((installation / "usr/bin/cpb").is_file())
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())

            shutil.rmtree(old_extension)
            for relative in (
                "usr/share/applications/copypastebin.desktop",
                "usr/share/copypastebin/enable-extension.js",
                "usr/libexec/copypastebin/refresh-user-icon-cache",
                "usr/share/metainfo/io.github.kozlowska_anna.CopyPasteBin.metainfo.xml",
            ):
                (installation / relative).unlink()
            self.assertTrue((installation / "usr/bin/cpb").is_file())
            self.assertFalse(old_extension.exists())
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())

            self._extract(packages["gnome-shell-extension-copypastebin"], installation)
            self.assertTrue((old_extension / "extension.js").is_file())
            self.assertEqual("synthetic=true\n", (config / "synthetic.toml").read_text())
            self.assertEqual("synthetic\n", (state / "synthetic.state").read_text())


if __name__ == "__main__":
    unittest.main()
