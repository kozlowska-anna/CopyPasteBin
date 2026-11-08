import io
import tempfile
import unittest
from pathlib import Path

from copypastebin import __version__
from copypastebin.bridge import (
    BACKEND_PROTOCOL_VERSION,
    MAX_CAPABILITIES_RESULT_BYTES,
    BridgeError,
    BridgeObservation,
    bridge_result_json,
    capabilities_json,
    observe_framed_event,
)
from copypastebin.filters import FilterStore
from copypastebin.history import HistoryStore
from copypastebin.history_settings import HistorySettingsStore
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

    def test_capabilities_are_exact_bounded_and_content_free(self):
        rendered = capabilities_json()
        self.assertEqual(
            '{"document_version":1,"product_version":'
            f'"{__version__}","protocol_version":'
            f'{BACKEND_PROTOCOL_VERSION}}}\n',
            rendered,
        )
        self.assertLessEqual(
            len(rendered.encode("ascii")),
            MAX_CAPABILITIES_RESULT_BYTES,
        )
        self.assertNotIn(str(self.state), rendered)

    def test_event_records_metadata_without_content(self):
        canary = b"person@example.com"
        self.observe(frame("org.mozilla.firefox", canary))
        entry = self.history.recent()[0]
        self.assertEqual("clipboard_event", entry.source_kind)
        self.assertEqual("org.mozilla.firefox", entry.source_application)
        self.assertEqual("unknown", entry.destination_application)
        self.assertNotIn(canary, self.history.database_path.read_bytes())

    def test_warning_and_high_return_safe_metadata_but_safe_text_does_not(self):
        safe = self.observe(frame("app.one", b"ordinary sentence"))
        self.assertIsNone(safe.notification)
        self.assertTrue(safe.history_eligible)
        warning = self.observe(frame("app.two", b"1234 PLN"))
        self.assertEqual("low", warning.notification.risk.value)
        high = self.observe(frame("app.three", b"password=synthetic-only"))
        self.assertEqual("high", high.notification.risk.value)
        self.assertFalse(high.history_eligible)
        self.assertNotIn("1234", repr(warning))

    def test_disabled_filter_suppresses_banner_category_and_redaction_metadata(self):
        FilterStore(self.state).set_enabled(Category.MONEY_AMOUNT_PLN_USD, False)
        self.assertIsNone(
            self.observe(frame("app.two", b"1234 PLN")).notification
        )
        entry = self.history.recent()[0]
        self.assertEqual("none", entry.highest_risk)
        self.assertEqual((), entry.category_counts)

    def test_bridge_result_json_is_bounded_and_content_free(self):
        safe = bridge_result_json(BridgeObservation(None, True))
        warning = bridge_result_json(self.observe(frame("app.two", b"1234 PLN")))
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[],'
            '"history_eligible":true}\n',
            safe,
        )
        self.assertIn('"risk":"low"', warning)
        self.assertIn('"MONEY_AMOUNT_PLN_USD"', warning)
        self.assertNotIn("1234", warning)
        self.assertLessEqual(len(warning.encode("ascii")), 2048)

    def test_disabled_warning_filter_does_not_enable_secret_history(self):
        FilterStore(self.state).set_enabled(Category.SECRET_ASSIGNMENT, False)
        result = self.observe(
            frame("app.synthetic", b"password: synthetic-value")
        )
        self.assertIsNone(result.notification)
        self.assertFalse(result.history_eligible)

    def test_at_sign_entropy_rejection_is_history_only(self):
        result = self.observe(frame("app.synthetic", b"Kx9#mP42@qT7&vL"))
        self.assertIsNone(result.notification)
        self.assertFalse(result.history_eligible)

    def test_trailing_line_ending_entropy_rejection_is_history_only(self):
        for line_ending in (b"\n", b"\r\n"):
            with self.subTest(line_ending=line_ending):
                result = self.observe(
                    frame("app.synthetic", b"Kx9#mP42!qT7&vL" + line_ending)
                )
                self.assertIsNone(result.notification)
                self.assertFalse(result.history_eligible)

    def test_disabled_text_history_does_not_disable_analysis_or_warning(self):
        HistorySettingsStore(self.state).set_enabled(False)
        result = self.observe(frame("app.synthetic", b"1234 PLN"))
        self.assertEqual("low", result.notification.risk.value)
        self.assertFalse(HistorySettingsStore(self.state).status().enabled)

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
