import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ProcessCliTests(unittest.TestCase):
    def run_process(self, arguments, data=b""):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).parents[2] / "src")
        return subprocess.run(
            [sys.executable, "-m", "copypastebin", *arguments],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
            timeout=10,
        )

    def test_real_process_success_and_usage_code(self):
        with tempfile.TemporaryDirectory() as directory:
            success = self.run_process(["--state-dir", directory, "--config", str(Path(directory) / "missing.toml")], b"1234 PLN")
        self.assertEqual(0, success.returncode)
        self.assertIn(b"MONEY_AMOUNT_PLN_USD", success.stdout)
        invalid = self.run_process(["--unknown-private-canary\x1b"])
        self.assertEqual(2, invalid.returncode)
        self.assertEqual(b"", invalid.stdout)
        self.assertNotIn(b"private-canary", invalid.stderr)
        self.assertNotIn(b"\x1b", invalid.stderr)

    def test_no_force_or_yes_bypass_exists(self):
        for option in ("--force", "--yes"):
            result = self.run_process([option])
            self.assertEqual(2, result.returncode)
