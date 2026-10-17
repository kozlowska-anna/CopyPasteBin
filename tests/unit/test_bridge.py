import io
import tempfile
import unittest
from pathlib import Path

from copypastebin.bridge import BridgeError, bridge_result_json, observe_framed_event
from copypastebin.filters import FilterStore
from copypastebin.history import HistoryStore
from copypastebin.models import Category
from copypastebin.pause import PauseStore


def frame(application, text):
    application_bytes = application.encode("ascii")
    return len(application_bytes).to_bytes(4, "big") + application_bytes + text


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.history = HistoryStore(self.state)
        self.pause = PauseStore(self.state)

    def tearDown(self):
        self.temporary.cleanup()

    def observe(self, payload):
        return observe_framed_event(
            io.BytesIO(payload),
            history=self.history,
            pause=self.pause,
        )

    def test_event_records_metadata_without_content(self):
        canary = b"person@example.com"
        self.observe(frame("org.mozilla.firefox", canary))
        entry = self.history.recent()[0]
        self.assertEqual("clipboard_event", entry.source_kind)
        self.assertEqual("org.mozilla.firefox", entry.source_application)
        self.assertEqual("unknown", entry.destination_application)
        self.assertNotIn(canary, self.history.database_path.read_bytes())

    def test_warning_and_high_return_safe_metadata_but_safe_text_does_not(self):
        self.assertIsNone(self.observe(frame("app.one", b"ordinary sentence")))
        warning = self.observe(frame("app.two", b"1234 PLN"))
        self.assertEqual("low", warning.risk.value)
        high = self.observe(frame("app.three", b"password=synthetic-only"))
        self.assertEqual("high", high.risk.value)
        self.assertNotIn("1234", repr(warning))

    def test_disabled_filter_suppresses_banner_category_and_redaction_metadata(self):
        FilterStore(self.state).set_enabled(Category.MONEY_AMOUNT_PLN_USD, False)
        self.assertIsNone(self.observe(frame("app.two", b"1234 PLN")))
        entry = self.history.recent()[0]
        self.assertEqual("none", entry.highest_risk)
        self.assertEqual((), entry.category_counts)

    def test_bridge_result_json_is_bounded_and_content_free(self):
        safe = bridge_result_json(None)
        warning = bridge_result_json(self.observe(frame("app.two", b"1234 PLN")))
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[]}\n',
            safe,
        )
        self.assertIn('"risk":"low"', warning)
        self.assertIn('"MONEY_AMOUNT_PLN_USD"', warning)
        self.assertNotIn("1234", warning)
        self.assertLessEqual(len(warning.encode("ascii")), 2048)

    def test_pause_rejects_event_before_history_or_result(self):
        self.pause.pause_indefinitely()
        with self.assertRaises(BridgeError):
            self.observe(frame("app.one", b"person@example.com"))
        self.assertFalse(self.history.database_path.exists())

    def test_malformed_frames_fail_closed(self):
        cases = (
            b"",
            b"\x00\x00\x00",
            (129).to_bytes(4, "big") + b"a" * 129 + b"text",
            frame("app", b""),
            frame("app", b"bad\x00text"),
            frame("app", b"\xff"),
        )
        for payload in cases:
            with self.subTest(payload=payload[:20]), self.assertRaises(BridgeError):
                self.observe(payload)

    def test_invalid_application_id_is_reduced_to_unknown(self):
        self.observe(frame("../private", b"ordinary text"))
        self.assertEqual("unknown", self.history.recent()[0].source_application)


if __name__ == "__main__":
    unittest.main()
