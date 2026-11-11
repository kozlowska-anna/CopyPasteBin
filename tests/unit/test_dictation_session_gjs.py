import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GJS = Path("/usr/bin/gjs")
DRIVER = ROOT / "tests" / "helpers" / "dictation_session_driver.js"


@unittest.skipUnless(GJS.is_file(), "gjs is required")
class DictationSessionGjsTests(unittest.TestCase):
    def run_driver(self, action: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(GJS), "-m", str(DRIVER), action],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_partial_replaces_preview_and_final_segments_are_not_duplicated(self):
        result = json.loads(self.run_driver("stream").stdout)
        self.assertEqual(["Ala", "Ala ma", ""], result["partials"])
        self.assertEqual(["Ala ma kota.", "Drugi segment."], result["finals"])
        self.assertEqual("Początek. Ala ma kota. Drugi segment.", result["document"])
        self.assertEqual("idle", result["state"])
        self.assertEqual(
            ["starting", "recording", "stopping", "idle"],
            result["states"],
        )

    def test_manual_edit_survives_partial_correction_and_final_commit(self):
        result = json.loads(self.run_driver("manual").stdout)
        self.assertEqual(
            "Początek. [ręczna korekta] Ala ma kota. Drugi segment.",
            result["document"],
        )
        self.assertNotIn("opóźnione", result["document"])

    def test_cancel_clears_partial_without_committing_it(self):
        result = json.loads(self.run_driver("cancel").stdout)
        self.assertEqual([], result["finals"])
        self.assertEqual("Początek.", result["document"])
        self.assertEqual(["Ala", "Ala ma", ""], result["partials"])
        self.assertEqual("idle", result["state"])

    def test_worker_error_clears_preview_and_enters_error_state(self):
        result = json.loads(self.run_driver("error").stdout)
        self.assertEqual([], result["finals"])
        self.assertEqual(["Ala", "Ala ma", ""], result["partials"])
        self.assertEqual("error", result["state"])
        self.assertEqual(["starting", "recording", "error"], result["states"])

    def test_invalid_frame_error_is_closed_and_does_not_echo_content(self):
        completed = self.run_driver("invalid")
        self.assertEqual("Invalid dictation worker response.\n", completed.stdout)
        self.assertNotIn("private canary", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
