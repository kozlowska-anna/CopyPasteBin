import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from copypastebin.bridge import observe_framed_event
from copypastebin.detection import detect_text
from copypastebin.filters import FilterStore
from copypastebin.history import HistoryStore
from copypastebin.history_policy import history_text_is_eligible
from copypastebin.input_sources import MAX_INPUT_BYTES
from copypastebin.models import Category
from copypastebin.pause import PauseStore


ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "tests" / "fixtures" / "history_policy" / "cases.json"
CASE_FIELDS = {
    "id",
    "group",
    "classification",
    "transform",
    "text",
    "detection",
    "required_categories",
    "banner",
    "history",
    "target_history",
}
GROUPS = {
    "recognized_secret",
    "heuristic_secret",
    "ordinary_text",
    "technical_identifier",
    "ambiguous",
    "known_bypass",
}
CLASSIFICATIONS = {"secret", "non_secret", "ambiguous"}
OBSERVATIONS = {"required", "none", "observe"}
HISTORY_EXPECTATIONS = {"block", "allow", "observe"}
TARGET_EXPECTATIONS = {"block", "allow", "observe"}
CASE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def load_corpus():
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if type(document) is not dict or set(document) != {
        "version",
        "description",
        "cases",
    }:
        raise AssertionError("invalid corpus document")
    if document["version"] != 1 or type(document["description"]) is not str:
        raise AssertionError("invalid corpus metadata")
    if type(document["cases"]) is not list:
        raise AssertionError("invalid corpus cases")
    return document["cases"]


def frame(text):
    application = b"app.synthetic.corpus"
    return len(application).to_bytes(4, "big") + application + text.encode("utf-8")


class HistoryPolicyCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_corpus()
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        cls.enabled_state = root / "enabled"
        cls.disabled_state = root / "disabled"
        enabled_filters = FilterStore(cls.enabled_state)
        disabled_filters = FilterStore(cls.disabled_state)
        for category in Category:
            enabled_filters.set_enabled(category, True)
            disabled_filters.set_enabled(category, False)
        cls.enabled_history = HistoryStore(cls.enabled_state)
        cls.disabled_history = HistoryStore(cls.disabled_state)
        cls.enabled_pause = PauseStore(cls.enabled_state)
        cls.disabled_pause = PauseStore(cls.disabled_state)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def observe(cls, text, *, filters_enabled):
        if filters_enabled:
            history = cls.enabled_history
            pause = cls.enabled_pause
        else:
            history = cls.disabled_history
            pause = cls.disabled_pause
        return observe_framed_event(
            io.BytesIO(frame(text)),
            history=history,
            pause=pause,
        )

    def test_corpus_schema_is_closed_complete_and_synthetic(self):
        identifiers = set()
        groups = set()
        transforms = set()
        for case in self.cases:
            identifier = case.get("id") if type(case) is dict else None
            with self.subTest(case=identifier):
                self.assertIs(type(case), dict)
                self.assertEqual(CASE_FIELDS, set(case), identifier)
                self.assertIs(type(identifier), str)
                self.assertRegex(identifier, CASE_ID)
                self.assertNotIn(identifier, identifiers)
                identifiers.add(identifier)
                self.assertIn(case["group"], GROUPS, identifier)
                self.assertIn(case["classification"], CLASSIFICATIONS, identifier)
                self.assertIs(type(case["transform"]), str)
                self.assertTrue(case["transform"], identifier)
                groups.add(case["group"])
                transforms.add(case["transform"])
                self.assertIs(type(case["text"]), str)
                self.assertTrue(case["text"], identifier)
                self.assertFalse("/home/" in case["text"], identifier)
                self.assertLessEqual(
                    len(case["text"].encode("utf-8")),
                    MAX_INPUT_BYTES,
                    identifier,
                )
                self.assertIn(case["detection"], OBSERVATIONS, identifier)
                self.assertIn(case["banner"], OBSERVATIONS, identifier)
                self.assertIn(case["history"], HISTORY_EXPECTATIONS, identifier)
                self.assertIn(
                    case["target_history"], TARGET_EXPECTATIONS, identifier
                )
                self.assertIs(type(case["required_categories"]), list)
                self.assertEqual(
                    case["required_categories"],
                    sorted(set(case["required_categories"])),
                    identifier,
                )
                for category in case["required_categories"]:
                    self.assertIn(category, {item.value for item in Category})
        self.assertEqual(GROUPS, groups)
        self.assertGreaterEqual(len(transforms), 12)

    def test_known_bypasses_are_observational_with_block_target(self):
        bypasses = [case for case in self.cases if case["group"] == "known_bypass"]
        self.assertGreaterEqual(len(bypasses), 8)
        for case in bypasses:
            with self.subTest(case=case["id"]):
                self.assertEqual("secret", case["classification"])
                self.assertEqual("observe", case["history"])
                self.assertEqual("block", case["target_history"])

    def test_recognized_secrets_have_absolute_block_expectations(self):
        recognized = [
            case for case in self.cases if case["group"] == "recognized_secret"
        ]
        self.assertGreaterEqual(len(recognized), 10)
        for case in recognized:
            with self.subTest(case=case["id"]):
                self.assertEqual("secret", case["classification"])
                self.assertEqual("required", case["detection"])
                self.assertEqual("required", case["banner"])
                self.assertEqual("block", case["history"])
                self.assertEqual("block", case["target_history"])

    def test_benchmark_report_contains_no_case_content(self):
        environment = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": "src",
        }
        completed = subprocess.run(
            [sys.executable, "benchmarks/history_policy_corpus.py"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, "corpus benchmark failed")
        rendered = completed.stdout + completed.stderr
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertFalse(case["text"] in rendered, case["id"])

    def test_policy_bridge_banner_and_filter_expectations(self):
        for case in self.cases:
            identifier = case["id"]
            with self.subTest(case=identifier):
                detections = detect_text(case["text"])
                categories = {item.category.value for item in detections}
                if case["detection"] == "required":
                    self.assertTrue(detections, identifier)
                elif case["detection"] == "none":
                    self.assertFalse(detections, identifier)
                self.assertLessEqual(
                    set(case["required_categories"]), categories, identifier
                )

                direct = history_text_is_eligible(case["text"], detections)
                enabled = self.observe(case["text"], filters_enabled=True)
                disabled = self.observe(case["text"], filters_enabled=False)
                self.assertEqual(direct, enabled.history_eligible, identifier)
                self.assertEqual(direct, disabled.history_eligible, identifier)
                self.assertIsNone(disabled.notification, identifier)

                if case["banner"] == "required":
                    self.assertIsNotNone(enabled.notification, identifier)
                elif case["banner"] == "none":
                    self.assertIsNone(enabled.notification, identifier)

                if case["history"] == "block":
                    self.assertFalse(direct, identifier)
                elif case["history"] == "allow":
                    self.assertTrue(direct, identifier)


if __name__ == "__main__":
    unittest.main()
