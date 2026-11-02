Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from benchmarks.persistent_bridge_performance import (
    PersistentWorker,
    WorkerFailure,
)
from copypastebin.config import save_customizations
from copypastebin.detection import CustomLiteralRule
from copypastebin.filters import FilterStore
from copypastebin.history import HistoryStore
from copypastebin.models import Category, RiskLevel
from copypastebin.pause import PauseStore


class PersistentBridgeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.config = self.root / "missing.toml"

    def tearDown(self):
        self.temporary.cleanup()

    def worker(self, *, idle_timeout=30.0):
        return PersistentWorker(
            self.state,
            self.config,
            idle_timeout=idle_timeout,
        )

    def test_multiple_requests_share_process_without_persisting_content(self):
        worker = self.worker()
        try:
            first = worker.request("person@example.invalid")
            second = worker.request("ordinary synthetic sentence")
            self.assertEqual("medium", first["risk"])
            self.assertEqual("none", second["risk"])
        finally:
            worker.close()
        database = HistoryStore(self.state).database_path.read_bytes()
        self.assertNotIn(b"person@example.invalid", database)
        self.assertNotIn(b"ordinary synthetic sentence", database)
        self.assertEqual(2, len(HistoryStore(self.state).recent()))

    def test_pause_is_rechecked_and_failure_stops_worker(self):
        worker = self.worker()
        worker.request("ordinary synthetic sentence")
        PauseStore(self.state).pause_indefinitely()
        with self.assertRaises(WorkerFailure):
            worker.request("person@example.invalid")
        worker.close(expected_code=1)
        self.assertEqual(1, len(HistoryStore(self.state).recent()))

    def test_filters_and_custom_rules_are_reloaded_for_each_request(self):
        worker = self.worker()
        try:
            self.assertEqual(
                "medium", worker.request("person@example.invalid")["risk"]
            )
            FilterStore(self.state).set_enabled(Category.EMAIL, False)
            self.assertEqual(
                "none", worker.request("person@example.invalid")["risk"]
            )
            self.assertEqual("none", worker.request("violet zebra")["risk"])
            save_customizations(
                (CustomLiteralRule("violet zebra", RiskLevel.HIGH),),
                (),
                self.config,
            )
            self.assertEqual("high", worker.request("violet zebra")["risk"])
        finally:
            worker.close()

    def test_worker_results_match_the_existing_one_shot_bridge(self):
        worker = self.worker()
        try:
            for index, text in enumerate((
                "ordinary synthetic sentence",
                "person@example.invalid",
                "amount 1234 PLN",
                "key sk-proj-CPBINSYNTHETIC0123456789abcdef",
            )):
                with self.subTest(text=text):
                    application = b"synthetic.worker-parity"
                    payload = (
                        len(application).to_bytes(4, "big")
                        + application
                        + text.encode("ascii")
                    )
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "copypastebin.cli",
                            "--state-dir",
                            str(self.root / f"one-shot-{index}"),
                            "--config",
                            str(self.config),
                            "bridge",
                            "observe",
                        ],
                        input=payload,
                        check=True,
                        capture_output=True,
                        env={
                            **os.environ,
                            "PYTHONDONTWRITEBYTECODE": "1",
                            "PYTHONPATH": str(
                                Path(__file__).resolve().parents[2] / "src"
                            ),
                        },
                    )
                    self.assertEqual(
                        json.loads(completed.stdout.decode("ascii")),
                        worker.request(text),
                    )
        finally:
            worker.close()

    def test_malformed_inner_frame_fails_closed_and_stops_worker(self):
        worker = self.worker()
        with self.assertRaises(WorkerFailure):
            worker.request_payload(b"synthetic-private-canary")
        self.assertEqual(1, worker.process.wait(timeout=2))
        self.assertIsNotNone(worker.process.stderr)
        error = worker.process.stderr.read().decode("utf-8")
        self.assertTrue(error)
        self.assertNotIn("synthetic-private-canary", error)
        worker.close(expected_code=1)
        self.assertFalse(HistoryStore(self.state).database_path.exists())

    def test_idle_timeout_and_stdin_eof_leave_no_worker(self):
        idle_worker = self.worker(idle_timeout=0.1)
        time.sleep(0.2)
        self.assertEqual(0, idle_worker.process.wait(timeout=2))
        idle_worker.close()

        eof_worker = self.worker()
        pid = eof_worker.process.pid
        eof_worker.close()
        self.assertFalse(Path(f"/proc/{pid}").exists())


if __name__ == "__main__":
    unittest.main()
