import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from copypastebin.history import HistoryStore


ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tests" / "helpers" / "bridge_worker_driver.js"
FAILURE_DRIVER = ROOT / "tests" / "helpers" / "bridge_worker_failure_driver.js"
GJS = Path("/usr/bin/gjs")


@unittest.skipUnless(GJS.exists(), "GJS is required by the GNOME extension")
class BridgeWorkerGjsTests(unittest.TestCase):
    def run_fake(self, body: str, *, timeout_ms: int = 100, mode: str = "request"):
        with tempfile.TemporaryDirectory() as directory:
            entry_point = Path(directory) / "fake-worker"
            entry_point.write_text(
                f"#!{sys.executable}\n"
                "import json, sys, time\n"
                "assert sys.argv[1:] == ['bridge', 'worker']\n"
                "handshake = json.dumps({"
                "'document_version': 1, 'product_version': '1.2', "
                "'protocol_version': 2, 'worker_protocol_version': 1}, "
                "sort_keys=True, separators=(',', ':')).encode('ascii') + b'\\n'\n"
                "sys.stdout.buffer.write(len(handshake).to_bytes(4, 'big') + handshake)\n"
                "sys.stdout.buffer.flush()\n"
                f"{body}\n",
                encoding="utf-8",
            )
            entry_point.chmod(0o700)
            return subprocess.run(
                [
                    str(GJS), "-m", str(FAILURE_DRIVER), str(entry_point),
                    str(timeout_ms), mode,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, "LC_ALL": "C.UTF-8"},
            ).stdout.strip()

    def test_real_gjs_client_reuses_production_worker_and_closes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            config = root / "missing.toml"
            entry_point = root / "cpb-test-entry"
            entry_point.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                "from copypastebin import cli\n"
                f"arguments = ['--state-dir', {str(state)!r}, "
                f"'--config', {str(config)!r}, *sys.argv[1:]]\n"
                "raise SystemExit(cli.main(arguments))\n",
                encoding="utf-8",
            )
            entry_point.chmod(0o700)
            completed = subprocess.run(
                [str(GJS), "-m", str(DRIVER), str(entry_point)],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
                env={
                    **os.environ,
                    "LC_ALL": "C.UTF-8",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(ROOT / "src"),
                },
            )
            self.assertEqual(
                {"first": "medium", "second": "none"},
                json.loads(completed.stdout),
            )
            database = HistoryStore(state).database_path.read_bytes()
            self.assertNotIn(b"person@example.invalid", database)
            self.assertNotIn(b"ordinary synthetic sentence", database)
            self.assertEqual(2, len(HistoryStore(state).recent()))

    def test_crash_malformed_response_and_timeout_fail_closed(self):
        self.assertEqual("ERROR", self.run_fake("raise SystemExit(7)"))
        self.assertEqual(
            "ERROR",
            self.run_fake(
                "sys.stdin.buffer.read(4)\n"
                "sys.stdout.buffer.write((2049).to_bytes(4, 'big'))\n"
                "sys.stdout.buffer.flush()"
            ),
        )
        self.assertEqual(
            "ERROR",
            self.run_fake("time.sleep(1)", timeout_ms=30),
        )

    def test_cancellation_suppresses_late_callback(self):
        self.assertEqual(
            "CANCELLED",
            self.run_fake("time.sleep(1)", timeout_ms=100, mode="cancel"),
        )


if __name__ == "__main__":
    unittest.main()
