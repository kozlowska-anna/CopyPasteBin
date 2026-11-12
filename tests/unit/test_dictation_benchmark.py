import json
import subprocess
import sys
import tempfile
import unittest
import wave
import hashlib
import importlib.util
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "experiments" / "dictation-benchmark" / "score.py"
REAL_ANALYZER = ROOT / "experiments" / "dictation-benchmark" / "analyze_runs.py"
AUDIO_VALIDATOR = ROOT / "experiments" / "dictation-benchmark" / "validate_audio_manifest.py"
NATURAL_AUDIO_VALIDATOR = ROOT / "experiments" / "dictation-benchmark" / "validate_natural_audio_manifest.py"
NATURAL_AUDIO_PLAN = ROOT / "experiments" / "dictation-benchmark" / "audio-manifest.natural-pl.plan.json"
NATURAL_CASES_PLAN = ROOT / "experiments" / "dictation-benchmark" / "cases.natural-pl.plan.json"
RUNNER = ROOT / "experiments" / "dictation-benchmark" / "run_adapter.py"
ISOLATED_RUNNER = ROOT / "experiments" / "dictation-benchmark" / "run_isolated.py"
VOSK_ADAPTER = ROOT / "experiments" / "dictation-benchmark" / "adapters" / "vosk_ctypes.py"
WHISPER_ADAPTER = ROOT / "experiments" / "dictation-benchmark" / "adapters" / "whisper_cli.py"


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
        return self._run_results([result])

    def _run_results(self, results: list[dict]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            result_path = Path(temporary) / "real-results.json"
            result_path.write_text(
                json.dumps({"version": 3, "results": results}),
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
            "input_pacing": "realtime",
            "audio_duration_ms": 1000,
            "ready_ms": 120,
            "model_init_ms": 120,
            "first_partial_ms": 370,
            "final_result_ms": 1220,
            "final_audio_position_ms": 1000,
            "completed_ms": 1250,
            "partials": [
                {"at_ms": 370, "audio_position_ms": 200, "lag_ms": 50,
                 "text": "To jest"},
                {"at_ms": 770, "audio_position_ms": 600, "lag_ms": 50,
                 "text": "To jest syntetyczna próba"},
            ],
            "cpu_seconds": 0.8,
            "peak_rss_mib": 300,
            "engine_bytes": 7_000_000,
            "model_bytes": 50_000_000,
            "offline": True,
            "isolation_profile": "bwrap-v1",
        }
        result.update(overrides)
        return result

    def test_real_report_has_accuracy_latency_partial_and_resource_metrics(self):
        completed = self._run(self._result())
        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(4, report["version"])
        self.assertEqual(3, report["source_result_version"])
        engine = report["engines"][0]
        self.assertEqual(0, engine["wer"])
        self.assertEqual(0, engine["cer"])
        self.assertEqual(0, engine["normalized_wer"])
        self.assertEqual(0, engine["normalized_cer"])
        self.assertEqual(0, engine["punctuation_aware_cer"])
        self.assertEqual(1, engine["mean_punctuation_accuracy"])
        self.assertEqual(1, engine["punctuation_assessable_runs"])
        self.assertEqual(1, engine["punctuation_correct_marks"])
        self.assertEqual(0, engine["punctuation_runs_blocked_by_word_errors"])
        self.assertEqual(1.25, engine["mean_wall_clock_ratio"])
        self.assertEqual(100, engine["mean_endpoint_latency_ms"])
        self.assertEqual(50, engine["mean_partial_lag_ms"])
        self.assertEqual(250, engine["mean_first_partial_after_ready_ms"])
        self.assertEqual(120, engine["mean_adapter_ready_ms"])
        self.assertEqual(1250, engine["median_completed_ms"])
        self.assertEqual(300, engine["mean_peak_rss_mib"])
        self.assertEqual(300, engine["max_peak_rss_mib"])
        self.assertIsNotNone(engine["mean_partial_churn"])
        self.assertNotIn("syntetyczna", completed.stdout)

    def test_punctuation_v2_separates_lexical_and_placement_errors(self):
        completed = self._run(self._result(
            transcript="To jest syntetyczna próba lokalnego dyktowania",
        ))
        self.assertEqual(0, completed.returncode, completed.stderr)
        engine = json.loads(completed.stdout)["engines"][0]
        self.assertEqual(0, engine["normalized_wer"])
        self.assertEqual(0, engine["normalized_cer"])
        self.assertGreater(engine["punctuation_aware_cer"], 0)
        self.assertEqual(1, engine["punctuation_missing_marks"])

        completed = self._run(self._result(
            transcript="To jest błędna próba lokalnego dyktowania.",
        ))
        self.assertEqual(0, completed.returncode, completed.stderr)
        engine = json.loads(completed.stdout)["engines"][0]
        self.assertEqual(0, engine["punctuation_assessable_runs"])
        self.assertEqual(1, engine["punctuation_runs_blocked_by_word_errors"])
        self.assertIsNone(engine["punctuation_precision"])

        specification = importlib.util.spec_from_file_location(
            "real_analyzer", REAL_ANALYZER)
        module = importlib.util.module_from_spec(specification)
        assert specification.loader is not None
        sys.path.insert(0, str(REAL_ANALYZER.parent))
        try:
            specification.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        reference = "Ala ma kota, dzisiaj."
        missing = module._punctuation_assessment(
            reference, "Ala ma kota dzisiaj.")
        misplaced = module._punctuation_assessment(
            reference, "Ala ma, kota dzisiaj.")
        extra = module._punctuation_assessment(
            "Ala ma kota.", "Ala, ma kota.")
        self.assertEqual(1, missing["missing"])
        self.assertEqual(1, missing["correct"])
        self.assertEqual(1, misplaced["misplaced"])
        self.assertEqual(1, misplaced["correct"])
        self.assertEqual(1, extra["extra"])
        self.assertIsNone(module._punctuation_assessment(
            reference, "Ala ma psa, dzisiaj."))

    def test_batch_mode_marks_partial_metrics_unavailable(self):
        completed = self._run(self._result(
            engine="whisper.cpp-tiny",
            recognition_mode="batch",
            input_pacing="fast",
            first_partial_ms=None,
            final_result_ms=800,
            completed_ms=820,
            partials=[],
        ))
        self.assertEqual(0, completed.returncode, completed.stderr)
        engine = json.loads(completed.stdout)["engines"][0]
        self.assertIsNone(engine["mean_first_partial_ms"])
        self.assertEqual(1, engine["runs_without_partial"])
        self.assertEqual("batch", engine["recognition_mode"])
        self.assertEqual("fast", engine["input_pacing"])
        self.assertEqual("native-cli-reported-load", engine["model_init_scope"])
        self.assertIsNone(engine["mean_endpoint_latency_ms"])

    def test_model_init_and_ready_timestamps_are_distinct(self):
        completed = self._run(self._result(
            model_init_ms=50,
            ready_ms=120,
        ))
        self.assertEqual(0, completed.returncode, completed.stderr)
        engine = json.loads(completed.stdout)["engines"][0]
        self.assertEqual(50, engine["mean_model_init_ms"])
        self.assertEqual("adapter-start-to-ready", engine["model_init_scope"])
        self.assertEqual(250, engine["mean_first_partial_after_ready_ms"])

    def test_repeats_are_aggregated_by_unique_case_without_claiming_independence(self):
        results = [
            self._result(run=1, completed_ms=1250, peak_rss_mib=300),
            self._result(run=2, completed_ms=1350, peak_rss_mib=320),
            self._result(run=3, completed_ms=1550, peak_rss_mib=280),
        ]
        completed = self._run_results(results)
        self.assertEqual(0, completed.returncode, completed.stderr)
        engine = json.loads(completed.stdout)["engines"][0]
        self.assertEqual(3, engine["runs"])
        self.assertEqual(1, engine["unique_cases"])
        self.assertEqual(1, engine["zero_word_error_cases"])
        self.assertEqual(0, engine["cases_with_quality_variation"])
        self.assertEqual(1350, engine["median_completed_ms"])
        self.assertEqual(300, engine["mean_repeat_completed_range_ms"])
        self.assertEqual(300, engine["max_repeat_completed_range_ms"])
        self.assertEqual(300, engine["mean_peak_rss_mib"])
        self.assertEqual(320, engine["max_peak_rss_mib"])

    def test_unconfirmed_offline_run_fails_without_echoing_transcript(self):
        canary = "private transcript canary"
        completed = self._run(self._result(transcript=canary, offline=False))
        self.assertNotEqual(0, completed.returncode)
        self.assertNotIn(canary, completed.stderr + completed.stdout)

    def test_realtime_report_rejects_claimed_lag_inconsistent_with_audio_position(self):
        result = self._result()
        result["partials"][0]["lag_ms"] = 999
        completed = self._run(result)
        self.assertNotEqual(0, completed.returncode)
        self.assertNotIn(result["transcript"], completed.stderr + completed.stdout)

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

    def test_attributed_v2_audio_manifest_accepts_a_safe_subdirectory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            corpus.mkdir()
            audio = corpus / "pl-01.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 1600)
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "version": 2,
                "dataset": {
                    "name": "Synthetic attributed corpus", "language": "pl",
                    "speaker": "synthetic", "selection": "test fixture",
                    "audio_license": "CC BY 4.0",
                    "reference_license": "CC BY 2.0 FR",
                    "attribution_url": "https://example.invalid/author",
                    "retrieved_at": "2026-11-12", "conversion": "synthetic PCM",
                },
                "samples": [{
                    "case_id": "pl-01", "file": "corpus/pl-01.wav",
                    "sha256": digest, "source_sha256": "0" * 64,
                    "source_url": "https://example.invalid/source.mp3",
                    "reference_url": "https://example.invalid/sentence/1",
                    "purpose": "technical",
                }],
            }), encoding="utf-8")
            completed = subprocess.run([
                sys.executable, str(AUDIO_VALIDATOR),
                "--manifest", str(manifest), "--audio-root", str(root),
            ], capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual(2, json.loads(completed.stdout)["version"])

    def test_natural_corpus_plan_has_fifteen_closed_unfilled_slots(self):
        manifest = json.loads(NATURAL_AUDIO_PLAN.read_text(encoding="utf-8"))
        references = json.loads(NATURAL_CASES_PLAN.read_text(encoding="utf-8"))
        self.assertEqual("planned-no-audio", manifest["status"])
        self.assertEqual(15, manifest["target"]["samples"])
        self.assertEqual(5, manifest["target"]["minimum_speakers"])
        self.assertLessEqual(manifest["target"]["maximum_download_bytes"], 25_000_000)
        slot_ids = [slot["case_id"] for slot in manifest["slots"]]
        case_ids = [case["id"] for case in references["cases"]]
        self.assertEqual(case_ids, slot_ids)
        self.assertEqual(len(slot_ids), len(set(slot_ids)))
        self.assertTrue(all(slot["source_item_id"] is None
                            for slot in manifest["slots"]))
        self.assertTrue(all(case["text"] is None and case["source_item_id"] is None
                            for case in references["cases"]))

    def test_natural_v3_manifest_validates_files_speakers_duration_and_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio_root = root / "audio"
            audio_root.mkdir()
            audio_root.chmod(0o700)
            cases = []
            samples = []
            categories = [
                "daily-conversation", "natural-long", "numbers-dates-times",
                "proper-names", "computing", "pauses-tempo",
                "self-correction", "punctuation",
            ]
            revision = "5ab868a7cddb87d84224ebfc8112ebd0905fc5bd"
            for index in range(1, 13):
                case_id = f"natural-pl-{index:02d}"
                cases.append({"id": case_id, "text": f"Syntetyczna próba numer {index}."})
                audio = audio_root / f"{case_id}.wav"
                with wave.open(str(audio), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(16000)
                    output.writeframes(b"\0\0" * 240000)
                audio.chmod(0o600)
                samples.append({
                    "case_id": case_id,
                    "file": audio.name,
                    "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
                    "source_sha256": "0" * 64,
                    "source_dataset": "voxpopuli-pl",
                    "source_revision": revision,
                    "source_item_id": f"synthetic-{index:02d}",
                    "source_url": "https://example.invalid/audio",
                    "reference_url": "https://example.invalid/reference",
                    "audio_license": "CC0-1.0",
                    "reference_license": "CC0-1.0",
                    "attribution": "Synthetic test fixture",
                    "speaker_id": f"speaker-{(index - 1) % 3 + 1}",
                    "duration_ms": 15000,
                    "categories": [categories[(index - 1) % len(categories)]],
                    "purpose": "quality",
                })
            cases_path = root / "cases.json"
            cases_path.write_text(json.dumps({
                "version": 1, "language": "pl", "cases": cases,
            }), encoding="utf-8")
            manifest_path = root / "manifest.json"
            document = {
                "version": 3,
                "corpus": {
                    "name": "Synthetic natural corpus",
                    "language": "pl",
                    "selection": "Synthetic validator fixture",
                    "source_revisions": {"voxpopuli-pl": revision},
                    "conversion": "Synthetic mono PCM",
                    "minimum_speakers": 3,
                    "clip_duration_ms": {"minimum": 10000, "maximum": 30000},
                    "total_duration_ms": {"minimum": 180000, "maximum": 360000},
                    "coverage_gaps": [],
                },
                "samples": samples,
            }
            manifest_path.write_text(json.dumps(document), encoding="utf-8")
            command = [
                sys.executable, str(NATURAL_AUDIO_VALIDATOR),
                "--manifest", str(manifest_path), "--audio-root", str(audio_root),
                "--cases", str(cases_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(12, report["samples"])
            self.assertEqual(3, report["speakers"])
            self.assertEqual(180000, report["duration_ms"])

            for sample in document["samples"]:
                sample["speaker_id"] = "speaker-1"
            manifest_path.write_text(json.dumps(document), encoding="utf-8")
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(0, completed.returncode)

    def test_offline_flag_or_environment_claim_cannot_bypass_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = subprocess.run([
                sys.executable, str(RUNNER),
                "--case-id", "pl-01", "--engine", "vosk-small-pl-0.22",
                "--run", "1", "--mode", "streaming", "--input-pacing", "fast",
                "--session", "direct-run", "--audio", str(root / "audio.wav"),
                "--engine-path", str(root), "--model-path", str(root),
                "--results", str(root / "results.json"), "--offline", "--",
                "/usr/bin/python3", "/engine/fixture.py", "direct-run",
            ], capture_output=True, text=True, env={
                **os.environ, "CPB_BENCHMARK_ISOLATION": "bwrap-v1",
            })
            self.assertNotEqual(0, completed.returncode)
            self.assertFalse((root / "results.json").exists())

    def test_launcher_accepts_only_exact_approved_adapter_commands(self):
        specification = importlib.util.spec_from_file_location("isolated", ISOLATED_RUNNER)
        module = importlib.util.module_from_spec(specification)
        assert specification.loader is not None
        specification.loader.exec_module(module)
        session = "closed-command"
        vosk = [
            "/usr/bin/python3", "/benchmark/adapters/vosk_ctypes.py",
            "--library", "/engine", "--model", "/model",
            "--audio", "/audio/input.wav", "--session", session,
            "--feed-mode", "file",
        ]
        module._validate_command(
            vosk, "vosk-small-pl-0.22", "streaming", "fast", session, 300)
        whisper = [
            "/usr/bin/python3", "/benchmark/adapters/whisper_cli.py",
            "--binary", "/engine/whisper-cli", "--model", "/model",
            "--audio", "/audio/input.wav", "--session", session,
            "--threads", "4", "--timeout-seconds", "295",
        ]
        module._validate_command(
            whisper, "whisper.cpp-tiny", "batch", "fast", session, 300)
        rejected = (
            (["/usr/bin/python3", "/engine/fixture.py", session],
             "vosk-small-pl-0.22", "streaming"),
            (vosk + ["--chunk-ms", "200"],
             "vosk-small-pl-0.22", "streaming"),
            (whisper[:-1] + ["294"], "whisper.cpp-tiny", "batch"),
        )
        for command, engine, mode in rejected:
            with self.subTest(command=command):
                with self.assertRaises(module.IsolationError):
                    module._validate_command(
                        command, engine, mode, "fast", session, 300)

    def test_pinned_engine_layout_rejects_renamed_inputs(self):
        specification = importlib.util.spec_from_file_location("isolated", ISOLATED_RUNNER)
        module = importlib.util.module_from_spec(specification)
        assert specification.loader is not None
        specification.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "libvosk.so"
            library.write_bytes(b"library")
            vosk_model = root / "vosk-model-small-pl-0.22"
            vosk_model.mkdir()
            module._validate_engine_layout(
                "vosk-small-pl-0.22", library, vosk_model)
            whisper = root / "whisper"
            whisper.mkdir()
            binary = whisper / "whisper-cli"
            binary.write_bytes(b"binary")
            binary.chmod(0o700)
            tiny = root / "ggml-tiny.bin"
            tiny.write_bytes(b"model")
            module._validate_engine_layout("whisper.cpp-tiny", whisper, tiny)
            with self.assertRaises(module.IsolationError):
                module._validate_engine_layout(
                    "whisper.cpp-tiny", whisper, root / "renamed.bin")

    def test_vosk_realtime_pacing_uses_monotonic_deadlines(self):
        specification = importlib.util.spec_from_file_location("vosk_adapter", VOSK_ADAPTER)
        module = importlib.util.module_from_spec(specification)
        assert specification.loader is not None
        specification.loader.exec_module(module)

        class FakeAudio:
            def __init__(self):
                self.chunks = [b"\0\0" * 1600, b"\0\0" * 1600]

            def readframes(self, _count):
                return self.chunks.pop(0) if self.chunks else b""

        now = [0.0]
        sleeps = []

        def monotonic():
            return now[0]

        def sleep(delay):
            sleeps.append(delay)
            now[0] += delay

        chunks = list(module.iter_audio_chunks(
            FakeAudio(), 1600, "realtime", monotonic=monotonic, sleep=sleep))
        self.assertEqual([1600, 3200], [frames for _, frames in chunks])
        self.assertEqual([0.1, 0.1], [round(delay, 3) for delay in sleeps])

        now[0] = 0
        sleeps.clear()
        list(module.iter_audio_chunks(
            FakeAudio(), 1600, "file", monotonic=monotonic, sleep=sleep))
        self.assertEqual([], sleeps)

        self.assertEqual(2272.6875, module._audio_position_ms(36363))

    @unittest.skipUnless(shutil.which("bwrap"), "bwrap is required for isolation test")
    def test_whisper_adapter_uses_batch_protocol_without_leaking_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "pl-01.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 36363)
            engine = root / "engine"
            engine.mkdir()
            fake = engine / "whisper-cli"
            fake.write_text(
                "#!/usr/bin/python3\n"
                "import json, sys\n"
                "print(json.dumps({'transcription':[{'text':'syntetyczna tajna treść'}]}))\n"
                "print('whisper_print_timings: load time = 12.34 ms', file=sys.stderr)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            (engine / "libfake.so.1").write_bytes(b"library")
            (engine / "libfake.so").symlink_to("libfake.so.1")
            model = root / "ggml-tiny.bin"
            model.write_bytes(b"model")
            results = root / "results.json"
            session = "synthetic-whisper"
            completed = subprocess.run([
                sys.executable, str(ISOLATED_RUNNER),
                "--case-id", "pl-01", "--engine", "whisper.cpp-tiny",
                "--run", "1", "--mode", "batch", "--input-pacing", "fast",
                "--session", session, "--audio", str(audio),
                "--engine-path", str(engine), "--model-path", str(model),
                "--results", str(results), "--", "/usr/bin/python3",
                "/benchmark/adapters/whisper_cli.py",
                "--binary", "/engine/whisper-cli", "--model", "/model",
                "--audio", "/audio/input.wav", "--session", session,
                "--threads", "4", "--timeout-seconds", "295",
            ], capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertNotIn("syntetyczna", completed.stdout + completed.stderr)
            result = json.loads(results.read_text(encoding="utf-8"))["results"][0]
            self.assertEqual("batch", result["recognition_mode"])
            self.assertEqual(12.34, result["model_init_ms"])
            self.assertGreaterEqual(result["ready_ms"], result["model_init_ms"])
            self.assertEqual([], result["partials"])

    def test_whisper_parser_rejects_malformed_output_without_echoing_it(self):
        specification = importlib.util.spec_from_file_location("whisper_adapter", WHISPER_ADAPTER)
        module = importlib.util.module_from_spec(specification)
        assert specification.loader is not None
        specification.loader.exec_module(module)
        canary = b"private transcript canary"
        with self.assertRaises(module.AdapterError) as raised:
            module._parse_output(canary)
        self.assertNotIn(canary.decode(), str(raised.exception))

    def test_timeout_helpers_kill_adapter_process_groups(self):
        runner_spec = importlib.util.spec_from_file_location("runner", RUNNER)
        runner = importlib.util.module_from_spec(runner_spec)
        assert runner_spec.loader is not None
        sys.path.insert(0, str(RUNNER.parent))
        try:
            runner_spec.loader.exec_module(runner)
        finally:
            sys.path.pop(0)
        whisper_spec = importlib.util.spec_from_file_location(
            "whisper_adapter", WHISPER_ADAPTER)
        whisper = importlib.util.module_from_spec(whisper_spec)
        assert whisper_spec.loader is not None
        whisper_spec.loader.exec_module(whisper)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child_pid = root / "child.pid"
            fake = root / "spawner.py"
            fake.write_text(
                "#!/usr/bin/python3\n"
                "import pathlib, subprocess, time\n"
                f"p=subprocess.Popen(['/usr/bin/sleep','60'])\n"
                f"pathlib.Path({str(child_pid)!r}).write_text(str(p.pid))\n"
                "time.sleep(60)\n",
                encoding="utf-8",
            )
            fake.chmod(0o700)
            process = subprocess.Popen([str(fake)], start_new_session=True)
            deadline = time.monotonic() + 2
            while not child_pid.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(child_pid.exists())
            pid = int(child_pid.read_text(encoding="ascii"))
            runner._kill_process_group(process)
            deadline = time.monotonic() + 2
            state = None
            while time.monotonic() < deadline:
                try:
                    state = Path(f"/proc/{pid}/stat").read_text().split()[2]
                except OSError:
                    state = None
                    break
                if state == "Z":
                    break
                time.sleep(0.01)
            self.assertIn(state, {None, "Z"})

            child_pid.unlink()
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                with self.assertRaises(subprocess.TimeoutExpired):
                    whisper._run_cli([str(fake)], stdout, stderr, 0.1)
            self.assertTrue(child_pid.exists())
            pid = int(child_pid.read_text(encoding="ascii"))
            deadline = time.monotonic() + 2
            state = None
            while time.monotonic() < deadline:
                try:
                    state = Path(f"/proc/{pid}/stat").read_text().split()[2]
                except OSError:
                    state = None
                    break
                if state == "Z":
                    break
                time.sleep(0.01)
            self.assertIn(state, {None, "Z"})


if __name__ == "__main__":
    unittest.main()
