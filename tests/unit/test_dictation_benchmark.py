import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "experiments" / "dictation-benchmark" / "score.py"


class DictationBenchmarkTests(unittest.TestCase):
    def _run(self, document: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            result_path = Path(temporary) / "synthetic-results.json"
            result_path.write_text(json.dumps(document), encoding="utf-8")
            return subprocess.run([sys.executable, str(HARNESS), "--results", str(result_path)], capture_output=True, text=True)

    def test_exact_synthetic_transcript_has_zero_error_and_is_not_repeated(self):
        transcript = "To jest syntetyczna próba lokalnego dyktowania."
        completed = self._run({"version": 1, "results": [{
            "case_id": "pl-01", "engine": "vosk-small-pl-0.22", "run": 1,
            "transcript": transcript, "first_result_ms": 100,
            "final_result_ms": 250, "cpu_seconds": 0.2,
            "peak_rss_mib": 128, "model_bytes": 50_000_000,
        }]})
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(0, report["engines"][0]["wer"])
        self.assertEqual(0, report["engines"][0]["cer"])
        self.assertNotIn(transcript, completed.stdout)

    def test_unknown_fields_fail_closed_without_echoing_transcript(self):
        transcript = "synthetic transcript canary"
        completed = self._run({"version": 1, "results": [{
            "case_id": "pl-01", "engine": "vosk-small-pl-0.22", "run": 1,
            "transcript": transcript, "first_result_ms": 100,
            "final_result_ms": 250, "cpu_seconds": 0.2,
            "peak_rss_mib": 128, "model_bytes": 50_000_000,
            "unexpected": True,
        }]})
        self.assertNotEqual(0, completed.returncode)
        self.assertNotIn(transcript, completed.stderr)


if __name__ == "__main__":
    unittest.main()
