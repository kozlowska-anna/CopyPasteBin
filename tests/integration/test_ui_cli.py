import io
import json
import tempfile
import unittest
from pathlib import Path

from copypastebin import cli
from copypastebin.detection import analyze_text
from copypastebin.filters import FilterStore
from copypastebin.history import HistoryStore
from copypastebin.models import Category
from copypastebin.pause import PauseStore


class _Input(io.TextIOWrapper):
    def __init__(self, data):
        self.raw_stream = io.BytesIO(data)
        super().__init__(self.raw_stream, encoding="utf-8")


class UiCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.config = Path(self.temporary.name) / "missing.toml"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, action, payload=b"", extra=()):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(
            [
                "--state-dir",
                str(self.state),
                "--config",
                str(self.config),
                "ui",
                action,
                *extra,
            ],
            stdin=_Input(payload),
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_history_command_returns_bounded_content_free_json(self):
        canary = "ui-history-private-canary@example.com"
        store = HistoryStore(self.state)
        store.record(
            canary,
            "clipboard_event",
            "other",
            analyze_text(canary),
            "warned",
            source_application="app.test",
        )
        code, stdout, stderr = self.run_cli("history")
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual(1, len(json.loads(stdout)["entries"]))
        self.assertNotIn(canary, stdout)

    def test_redact_returns_only_suggestion_and_does_not_record(self):
        code, stdout, stderr = self.run_cli(
            "redact", b"Contact person@example.com and 13 PLN"
        )
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn("[EMAIL_1]", stdout)
        self.assertIn("[MONEY_AMOUNT_PLN_USD_1]", stdout)
        self.assertFalse(HistoryStore(self.state).database_path.exists())

    def test_redact_supports_btc_and_xrp_amounts(self):
        code, stdout, stderr = self.run_cli("redact", b"0.25 BTC and 15 XRP")
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual(2, stdout.count("[CRYPTO_AMOUNT_BTC_XRP_"))

    def test_filter_settings_are_visible_persistent_and_control_redaction(self):
        code, stdout, stderr = self.run_cli("filters")
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        states = dict(json.loads(stdout)["filters"])
        self.assertEqual(
            {"HOME_PATH", "POSSIBLE_SEED_PHRASE", "TOKEN"},
            {category for category, enabled in states.items() if not enabled},
        )
        self.assertTrue(states["EMAIL"])
        self.assertTrue(states["OPENAI_API_KEY"])

        code, stdout, stderr = self.run_cli(
            "filter-set", extra=("HOME_PATH", "off")
        )
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertFalse(dict(json.loads(stdout)["filters"])["HOME_PATH"])
        self.assertFalse(FilterStore(self.state).status().enabled(Category.HOME_PATH))

        code, stdout, stderr = self.run_cli(
            "redact", b"/home/example/private.txt person@example.com"
        )
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn("/home/example/private.txt", stdout)
        self.assertIn("[EMAIL_1]", stdout)

    def test_language_choice_is_visible_persistent_and_closed(self):
        code, stdout, stderr = self.run_cli("language")
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("system", json.loads(stdout)["choice"])
        self.assertIn(json.loads(stdout)["effective"], {"pl", "en"})

        code, stdout, stderr = self.run_cli("language-set", extra=("en",))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(
            {"version": 1, "choice": "en", "effective": "en"},
            json.loads(stdout),
        )

    def test_custom_rules_can_be_listed_saved_and_used_by_editor_redaction(self):
        code, stdout, stderr = self.run_cli("rules")
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual([], json.loads(stdout)["rules"])

        payload = json.dumps(
            {
                "version": 3,
                "rules": [
                    {
                        "literal": "SYNTHETIC-MARKER",
                        "risk": "warning",
                        "enabled": True,
                    }
                ],
                "exclusions": [],
            }
        ).encode()
        code, stdout, stderr = self.run_cli("rules-save", payload)
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("SYNTHETIC-MARKER", json.loads(stdout)["rules"][0]["literal"])
        self.assertEqual(0o600, self.config.stat().st_mode & 0o777)

        code, stdout, stderr = self.run_cli("redact", b"SYNTHETIC-MARKER")
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual("[CUSTOM_RULE_1]", stdout)

    def test_disabled_custom_rule_is_saved_but_not_detected(self):
        payload = json.dumps(
            {
                "version": 3,
                "rules": [
                    {
                        "literal": "SYNTHETIC-MARKER",
                        "risk": "high",
                        "enabled": False,
                    }
                ],
                "exclusions": [],
            }
        ).encode()
        code, stdout, stderr = self.run_cli("rules-save", payload)
        self.assertEqual((0, ""), (code, stderr))
        self.assertFalse(json.loads(stdout)["rules"][0]["enabled"])
        code, stdout, stderr = self.run_cli("redact", b"SYNTHETIC-MARKER")
        self.assertEqual((0, "SYNTHETIC-MARKER", ""), (code, stdout, stderr))

    def test_literal_exclusion_is_saved_and_suppresses_only_exact_detection(self):
        payload = json.dumps(
            {
                "version": 3,
                "rules": [],
                "exclusions": [
                    {
                        "literal": "5.6 Sol",
                        "category": "CRYPTO_AMOUNT_BTC_XRP",
                        "enabled": True,
                    }
                ],
            }
        ).encode()
        code, stdout, stderr = self.run_cli("rules-save", payload)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("5.6 Sol", json.loads(stdout)["exclusions"][0]["literal"])

        code, stdout, stderr = self.run_cli("redact", b"5.6 Sol 1 SOL")
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("5.6 Sol [CRYPTO_AMOUNT_BTC_XRP_1]", stdout)

    def test_editor_can_add_enable_and_reuse_one_exact_exclusion(self):
        request = json.dumps({
            "version": 1,
            "literal": "5.6 Sol",
            "category": "CRYPTO_AMOUNT_BTC_XRP",
        }).encode()
        code, stdout, stderr = self.run_cli("exclusion-add", request)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("added", json.loads(stdout)["status"])
        self.assertNotIn("5.6 Sol", stdout)
        self.assertEqual(0o600, self.config.stat().st_mode & 0o777)

        code, stdout, stderr = self.run_cli("exclusion-add", request)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("exists", json.loads(stdout)["status"])

        code, stdout, stderr = self.run_cli("redact", b"5.6 Sol 1 SOL")
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("5.6 Sol [CRYPTO_AMOUNT_BTC_XRP_1]", stdout)

    def test_editor_exclusion_add_enables_inactive_and_reports_rule_conflict(self):
        inactive = json.dumps({
            "version": 3,
            "rules": [],
            "exclusions": [{
                "literal": "5.6 Sol",
                "category": "CRYPTO_AMOUNT_BTC_XRP",
                "enabled": False,
            }],
        }).encode()
        code, _stdout, stderr = self.run_cli("rules-save", inactive)
        self.assertEqual((0, ""), (code, stderr))
        request = json.dumps({
            "version": 1,
            "literal": "5.6 Sol",
            "category": "CRYPTO_AMOUNT_BTC_XRP",
        }).encode()
        code, stdout, stderr = self.run_cli("exclusion-add", request)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("enabled", json.loads(stdout)["status"])

        conflict = json.dumps({
            "version": 3,
            "rules": [{
                "literal": "SYNTHETIC-MARKER",
                "risk": "low",
                "enabled": True,
            }],
            "exclusions": [],
        }).encode()
        code, _stdout, stderr = self.run_cli("rules-save", conflict)
        self.assertEqual((0, ""), (code, stderr))
        conflicting_request = json.dumps({
            "version": 1,
            "literal": "SYNTHETIC-MARKER",
            "category": "EMAIL",
        }).encode()
        code, stdout, stderr = self.run_cli("exclusion-add", conflicting_request)
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual("conflict", json.loads(stdout)["status"])
        self.assertNotIn("SYNTHETIC-MARKER", stdout)

    def test_editor_exclusion_add_rejects_high_risk_without_disclosure(self):
        canary = "SYNTHETIC-PRIVATE-CANARY"
        request = json.dumps({
            "version": 1,
            "literal": canary,
            "category": "TOKEN",
        }).encode()
        code, stdout, stderr = self.run_cli("exclusion-add", request)
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertNotIn(canary, stderr)
        self.assertFalse(self.config.exists())

    def test_auto_clear_setting_and_detection_positions_use_closed_json(self):
        code, stdout, stderr = self.run_cli("auto-clear")
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual({"version": 1, "seconds": 0}, json.loads(stdout))
        code, stdout, stderr = self.run_cli("auto-clear-set", extra=("60",))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(60, json.loads(stdout)["seconds"])
        self.assertEqual(60, FilterStore(self.state).status().auto_clear_seconds)

        canary = b"before person@example.com after"
        code, stdout, stderr = self.run_cli("detections", canary)
        self.assertEqual((0, ""), (code, stderr))
        result = json.loads(stdout)
        self.assertEqual("EMAIL", result["detections"][0]["category"])
        self.assertNotIn("person@example.com", stdout)

    def test_custom_rules_save_rejects_bad_payload_without_disclosure(self):
        canary = b'{"version":3,"rules":[{"literal":"PRIVATE-CANARY","risk":"bad"}],"exclusions":[]}'
        code, stdout, stderr = self.run_cli("rules-save", canary)
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertNotIn("PRIVATE-CANARY", stderr)

    def test_high_and_critical_exclusions_are_rejected_without_disclosure(self):
        for category in ("OPENAI_API_KEY", "POSSIBLE_SEED_PHRASE"):
            payload = json.dumps({
                "version": 3,
                "rules": [],
                "exclusions": [{
                    "literal": "SYNTHETIC-PRIVATE-CANARY",
                    "category": category,
                    "enabled": True,
                }],
            }).encode()
            code, stdout, stderr = self.run_cli("rules-save", payload)
            self.assertEqual(1, code)
            self.assertEqual("", stdout)
            self.assertNotIn("SYNTHETIC-PRIVATE-CANARY", stderr)

    def test_bad_editor_input_uses_redacted_error_path(self):
        for payload in (b"", b"bad\x00text", b"\xff"):
            with self.subTest(payload=payload):
                code, stdout, stderr = self.run_cli("redact", payload)
                self.assertEqual(1, code)
                self.assertEqual("", stdout)
                self.assertEqual(
                    "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
                    stderr,
                )

    def test_pause_blocks_redaction_before_reading_editor_input(self):
        PauseStore(self.state).pause_indefinitely()
        canary = b"paused-private-canary@example.com"
        stream = _Input(canary)
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(
            ["--state-dir", str(self.state), "ui", "redact"],
            stdin=stream,
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(1, code)
        self.assertEqual(0, stream.buffer.tell())
        self.assertNotIn(canary.decode(), stdout.getvalue() + stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
