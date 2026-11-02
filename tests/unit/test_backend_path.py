import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from copypastebin import __version__
from copypastebin.bridge import capabilities_json


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "gnome-extension" / "copypastebin@kozlowska-anna.github.io"
RESOLVER = EXTENSION / "backend-path.js"
DRIVER = ROOT / "tests" / "helpers" / "backend_path_driver.js"
CAPABILITIES_DRIVER = ROOT / "tests" / "helpers" / "backend_capabilities_driver.js"
PROBE_DRIVER = ROOT / "tests" / "helpers" / "backend_probe_driver.js"
USABILITY_DRIVER = ROOT / "tests" / "helpers" / "backend_usability_driver.js"
GJS = Path("/usr/bin/gjs")
SYSTEM = "/usr/bin/cpb"
USER = "/home/example/.local/share/copypastebin/venv/bin/cpb"


@unittest.skipUnless(GJS.exists(), "GJS is required by the GNOME extension")
class BackendPathTests(unittest.TestCase):
    def resolve(self, *available: str) -> str:
        completed = subprocess.run(
            [str(GJS), "-m", str(DRIVER), SYSTEM, USER, *available],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def capabilities(self, rendered: str, expected_protocol: int = 2):
        completed = subprocess.run(
            [
                str(GJS),
                "-m",
                str(CAPABILITIES_DRIVER),
                str(expected_protocol),
                rendered,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        output = completed.stdout.strip()
        return output if output == "INVALID" else json.loads(output)

    def probe(self, body: str, *, timeout_ms: int = 500, mode: str = "run"):
        with tempfile.TemporaryDirectory() as directory:
            backend = Path(directory) / "cpb"
            backend.write_text(
                "#!/usr/bin/python3\n"
                "import sys\n"
                f"{body}\n",
                encoding="utf-8",
            )
            backend.chmod(0o700)
            completed = subprocess.run(
                [
                    str(GJS), "-m", str(PROBE_DRIVER), str(backend),
                    str(timeout_ms), mode,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "LC_ALL": "C.UTF-8"},
            )
            output = completed.stdout.strip()
            if output in {"DESTROYED", "CALLBACK"}:
                return output
            return json.loads(output)

    def usability(self, path: Path) -> str:
        completed = subprocess.run(
            [str(GJS), "-m", str(USABILITY_DRIVER), str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def test_system_backend_wins_when_both_installations_exist(self):
        self.assertEqual(SYSTEM, self.resolve(USER, SYSTEM))

    def test_user_backend_is_the_compatible_fallback(self):
        self.assertEqual(USER, self.resolve(USER))

    def test_missing_backend_fails_closed(self):
        self.assertEqual("NONE", self.resolve())

    def test_matching_protocol_is_compatible(self):
        self.assertEqual(
            {
                "compatible": True,
                "productVersion": "1.2.dev0",
                "protocolVersion": 2,
            },
            self.capabilities(
                '{"document_version":1,"product_version":"1.2.dev0",'
                '"protocol_version":2}'
            ),
        )

    def test_backend_output_matches_extension_protocol(self):
        self.assertEqual(
            {
                "compatible": True,
                "productVersion": __version__,
                "protocolVersion": 2,
            },
            self.capabilities(capabilities_json()),
        )

    def test_older_and_newer_protocols_are_incompatible(self):
        for protocol in (1, 3):
            with self.subTest(protocol=protocol):
                self.assertEqual(
                    {
                        "compatible": False,
                        "productVersion": "1.2",
                        "protocolVersion": protocol,
                    },
                    self.capabilities(
                        '{"document_version":1,"product_version":"1.2",'
                        f'"protocol_version":{protocol}}}',
                        expected_protocol=2,
                    ),
                )

    def test_malformed_capabilities_fail_closed(self):
        cases = (
            "",
            "{}",
            "not-json",
            '{"document_version":1,"product_version":"1.2",'
            '"protocol_version":1,"extra":true}',
            '{"document_version":2,"product_version":"1.2",'
            '"protocol_version":1}',
            '{"document_version":1,"product_version":"bad\\nversion",'
            '"protocol_version":1}',
            '{"document_version":1,"product_version":"1.2",'
            '"protocol_version":0}',
            "x" * 513,
        )
        for rendered in cases:
            with self.subTest(rendered=rendered[:40]):
                self.assertEqual("INVALID", self.capabilities(rendered))

    def test_async_probe_uses_fixed_command_and_accepts_compatible_backend(self):
        self.assertEqual(
            {
                "status": "compatible",
                "productVersion": "1.2.dev0",
                "protocolVersion": 2,
            },
            self.probe(
                "assert sys.argv[1:] == ['bridge', 'capabilities']\n"
                "print('{\"document_version\":1,\"product_version\":'"
                "'\"1.2.dev0\",\"protocol_version\":2}')"
            ),
        )

    def test_async_probe_reports_both_versions_for_incompatible_backend(self):
        self.assertEqual(
            {
                "status": "incompatible",
                "productVersion": "2.0",
                "protocolVersion": 3,
            },
            self.probe(
                "print('{\"document_version\":1,\"product_version\":\"2.0\",'"
                "'\"protocol_version\":3}')"
            ),
        )

    def test_async_probe_fails_closed_for_bad_exit_malformed_or_oversized_output(self):
        cases = (
            "sys.exit(7)",
            "print('{\"document_version\":1,\"product_version\":\"1.2\",'"
            "'\"protocol_version\":1}')\nsys.exit(7)",
            "print('not-json')",
            "print('x' * 513)",
            "sys.stdout.buffer.write(b'\\xff')",
        )
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual({"status": "error"}, self.probe(body))

    def test_async_probe_times_out_and_destroy_suppresses_late_callback(self):
        slow = "import time\ntime.sleep(1)"
        self.assertEqual(
            {"status": "error"},
            self.probe(slow, timeout_ms=30),
        )
        self.assertEqual(
            "DESTROYED",
            self.probe(slow, timeout_ms=1000, mode="destroy"),
        )

    def test_resolver_uses_only_two_fixed_absolute_candidates(self):
        source = RESOLVER.read_text(encoding="utf-8")
        self.assertIn("export const SYSTEM_BACKEND_PATH = '/usr/bin/cpb'", source)
        self.assertIn("'.local'", source)
        self.assertIn("'venv'", source)
        self.assertIn("GLib.FileTest.IS_REGULAR", source)
        self.assertIn("GLib.FileTest.IS_EXECUTABLE", source)
        self.assertIn("GLib.FileTest.IS_SYMLINK", source)
        for forbidden in ("find_program_in_path", "getenv('PATH')", 'getenv("PATH")'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_backend_candidate_must_be_regular_executable_and_not_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = root / "cpb"
            backend.write_text("#!/bin/true\n", encoding="utf-8")
            backend.chmod(0o700)
            symlink = root / "cpb-link"
            symlink.symlink_to(backend)
            non_executable = root / "cpb-data"
            non_executable.write_text("data\n", encoding="utf-8")

            self.assertEqual("USABLE", self.usability(backend))
            self.assertEqual("UNUSABLE", self.usability(symlink))
            self.assertEqual("UNUSABLE", self.usability(non_executable))
            self.assertEqual("UNUSABLE", self.usability(root))


if __name__ == "__main__":
    unittest.main()
