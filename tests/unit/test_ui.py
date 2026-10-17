import json
import tempfile
import unittest
from pathlib import Path

from copypastebin.detection import (
    CustomLiteralExclusion,
    CustomLiteralRule,
    analyze_text,
)
from copypastebin.filters import FilterStatus
from copypastebin.history import HistoryStore
from copypastebin.models import Category, RiskLevel
from copypastebin.ui import (
    UiError,
    auto_clear_json,
    custom_rules_from_json,
    custom_rules_json,
    detections_json,
    exclusion_request_from_json,
    exclusion_result_json,
    filters_json,
    history_json,
    redacted_suggestion,
)


class UiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temporary.name) / "state")

    def tearDown(self):
        self.temporary.cleanup()

    def test_history_snapshot_has_at_most_eight_metadata_entries(self):
        canary = "private-editor-canary"
        for number in range(10):
            text = f"{canary}-{number}@example.com"
            self.store.record(
                text,
                "clipboard_event",
                "other",
                analyze_text(text),
                "warned",
                source_application="app.test",
            )
        encoded = history_json(self.store)
        payload = json.loads(encoded)
        self.assertEqual(1, payload["version"])
        self.assertEqual(8, len(payload["entries"]))
        self.assertEqual(
            {"time", "from", "to", "risk", "categories"},
            set(payload["entries"][0]),
        )
        self.assertNotIn(canary, encoded)

    def test_redaction_is_a_suggestion_without_history_write(self):
        suggestion = redacted_suggestion("Contact person@example.com for 13 zł")
        self.assertIn("[EMAIL_1]", suggestion)
        self.assertIn("[MONEY_AMOUNT_PLN_USD_1]", suggestion)
        self.assertFalse(self.store.database_path.exists())

    def test_redaction_and_filter_snapshot_respect_disabled_categories(self):
        disabled = frozenset({Category.EMAIL, Category.HOME_PATH})
        suggestion = redacted_suggestion(
            "person@example.com /home/example/file 13 PLN",
            disabled_categories=disabled,
        )
        self.assertIn("person@example.com", suggestion)
        self.assertIn("/home/example/file", suggestion)
        self.assertIn("[MONEY_AMOUNT_PLN_USD_1]", suggestion)
        payload = json.loads(filters_json(FilterStatus(disabled)))
        states = dict(payload["filters"])
        self.assertFalse(states["EMAIL"])
        self.assertFalse(states["HOME_PATH"])
        self.assertTrue(states["MONEY_AMOUNT_PLN_USD"])

    def test_empty_or_nul_text_is_rejected_safely(self):
        for text in ("", "bad\x00text"):
            with self.subTest(text=text), self.assertRaises(UiError):
                redacted_suggestion(text)

    def test_custom_rules_json_round_trip_is_closed_and_bounded(self):
        rules = (CustomLiteralRule("SYNTHETIC-MARKER", RiskLevel.WARNING),)
        exclusions = (CustomLiteralExclusion(
            "5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP
        ),)
        payload = json.loads(custom_rules_json(rules, exclusions))
        self.assertEqual(3, payload["version"])
        self.assertEqual(32, payload["max_rules"])
        self.assertEqual(32, payload["max_exclusions"])
        writable = json.dumps(
            {
                "version": 3,
                "rules": payload["rules"],
                "exclusions": payload["exclusions"],
            }
        )
        self.assertEqual(
            (rules, exclusions),
            custom_rules_from_json(writable),
        )
        for invalid in ("", "{}", '{"version":1,"rules":[],"extra":true}'):
            with self.subTest(invalid=invalid), self.assertRaises(UiError):
                custom_rules_from_json(invalid)

    def test_rules_json_rejects_high_and_critical_exclusions(self):
        for category in ("OPENAI_API_KEY", "POSSIBLE_SEED_PHRASE"):
            payload = json.dumps({
                "version": 3,
                "rules": [],
                "exclusions": [{
                    "literal": "SYNTHETIC-VALUE",
                    "category": category,
                    "enabled": True,
                }],
            })
            with self.subTest(category=category), self.assertRaises(UiError):
                custom_rules_from_json(payload)

    def test_exact_exclusion_request_is_closed_bounded_and_low_or_medium_only(self):
        request = exclusion_request_from_json(json.dumps({
            "version": 1,
            "literal": "5.6 Sol",
            "category": "CRYPTO_AMOUNT_BTC_XRP",
        }))
        self.assertEqual("5.6 Sol", request.literal)
        self.assertEqual(Category.CRYPTO_AMOUNT_BTC_XRP, request.category)
        self.assertTrue(request.enabled)
        self.assertEqual(
            {"version": 1, "status": "added"},
            json.loads(exclusion_result_json("added")),
        )
        for invalid in (
            {"version": 1, "literal": "ab", "category": "EMAIL"},
            {"version": 1, "literal": "secret-value", "category": "TOKEN"},
            {"version": 1, "literal": "bad\nvalue", "category": "EMAIL"},
            {"version": 2, "literal": "5.6 Sol", "category": "CRYPTO_AMOUNT_BTC_XRP"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(UiError):
                exclusion_request_from_json(json.dumps(invalid))
        with self.assertRaises(UiError):
            exclusion_result_json("unknown")

    def test_auto_clear_and_detection_snapshots_are_bounded_metadata(self):
        auto_clear = json.loads(auto_clear_json(FilterStatus(frozenset(), 300)))
        self.assertEqual({"version": 1, "seconds": 300}, auto_clear)
        canary = "prefix person@example.com suffix"
        payload = json.loads(detections_json(analyze_text(canary)))
        self.assertEqual(1, payload["version"])
        self.assertEqual(
            {"start", "end", "category", "risk"},
            set(payload["detections"][0]),
        )
        self.assertEqual("EMAIL", payload["detections"][0]["category"])
        self.assertNotIn("person@example.com", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
