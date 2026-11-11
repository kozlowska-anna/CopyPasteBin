import json
import subprocess
import sys
import tempfile
import unittest
import wave
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "experiments" / "dictation-benchmark" / "score.py"
REAL_ANALYZER = ROOT / "experiments" / "dictation-benchmark" / "analyze_runs.py"
AUDIO_VALIDATOR = ROOT / "experiments" / "dictation-benchmark" / "validate_audio_manifest.py"
RUNNER = ROOT / "experiments" / "dictation-benchmark" / "run_adapter.py"
ADAPTER_FIXTURE = ROOT / "tests" / "helpers" / "stt_adapter_fixture.py"


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


class RealDictationBenchmarkTests(unittest.TestCase):
    def _run(self, result: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            result_path = Path(temporary) / "real-results.json"
            result_path.write_text(
                json.dumps({"version": 2, "results": [result]}),
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, str(REAL_ANALYZER), "--results", str(result_path)],
                capture_output=True,
                text=True,
            )

    @staticmethod
    def _result(**overrides):
        result = {
            "case_id": "pl-01",
            "engine": "vosk-small-pl-0.22",
            "run": 1,
            "transcript": "To jest syntetyczna próba lokalnego dyktowania.",
            "recognition_mode": "streaming",
            "audio_duration_ms": 1000,
            "model_init_ms": 120,
            "first_partial_ms": 200,
            "final_result_ms": 1100,
            "partials": [
                {"at_ms": 200, "text": "To jest"},
                {"at_ms": 600, "text": "To jest syntetyczna próba"},
            ],
            "cpu_seconds": 0.8,
            "peak_rss_mib": 300,
            "engine_bytes": 7_000_000,
            "model_bytes": 50_000_000,
            "offline": True,
        }
        result.update(overrides)
        return result

    def test_real_report_has_accuracy_latency_partial_and_resource_metrics(self):
        completed = self._run(self._result())
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        engine = report["engines"][0]
        self.assertEqual(0, engine["wer"])
        self.assertEqual(0, engine["cer"])
        self.assertEqual(1, engine["mean_punctuation_accuracy"])
        self.assertEqual(1.1, engine["mean_realtime_factor"])
        self.assertEqual(100, engine["mean_endpoint_latency_ms"])
        self.assertIsNotNone(engine["mean_partial_churn"])
        self.assertNotIn("syntetyczna", completed.stdout)

    def test_batch_mode_marks_partial_metrics_unavailable(self):
        completed = self._run(self._result(
            engine="whisper.cpp-tiny",
            recognition_mode="batch",
            first_partial_ms=None,
            partials=[],
        ))
        self.assertEqual(0, completed.returncode, completed.stderr)
        engine = json.loads(completed.stdout)["engines"][0]
        self.assertIsNone(engine["mean_first_partial_ms"])
        self.assertEqual(1, engine["runs_without_partial"])
        self.assertEqual(["batch"], engine["modes"])

    def test_unconfirmed_offline_run_fails_without_echoing_transcript(self):
        canary = "private transcript canary"
        completed = self._run(self._result(transcript=canary, offline=False))
        self.assertNotEqual(0, completed.returncode)
        self.assertNotIn(canary, completed.stderr + completed.stdout)

    def test_audio_manifest_accepts_only_pinned_pcm_wav_in_audio_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "pl-01.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 1600)
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"version": 1, "samples": [{
                "case_id": "pl-01",
                "file": "pl-01.wav",
                "sha256": digest,
                "license": "CC0-1.0",
                "source_url": "https://example.invalid/synthetic-test",
                "purpose": "technical",
            }]}), encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(AUDIO_VALIDATOR),
                "--manifest", str(manifest), "--audio-root", str(root),
            ], capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(100, json.loads(completed.stdout)["duration_ms"])

    def test_runner_records_protocol_metrics_privately_without_printing_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "pl-01.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 1600)
            engine = root / "engine"
            model = root / "model"
            engine.mkdir()
            model.mkdir()
            (engine / "binary").write_bytes(b"engine")
            (model / "weights").write_bytes(b"model")
            results = root / "results.json"
            session = "synthetic-run"
            completed = subprocess.run([
                sys.executable, str(RUNNER),
                "--case-id", "pl-01", "--engine", "vosk-small-pl-0.22",
                "--run", "1", "--mode", "streaming", "--session", session,
                "--audio", str(audio), "--engine-path", str(engine),
                "--model-path", str(model), "--results", str(results),
                "--offline", "--", sys.executable, str(ADAPTER_FIXTURE), session,
            ], capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertNotIn("syntetyczna", completed.stdout + completed.stderr)
            result = json.loads(results.read_text(encoding="utf-8"))["results"][0]
            self.assertEqual("streaming", result["recognition_mode"])
            self.assertEqual(1, len(result["partials"]))
            self.assertEqual(0o600, results.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
