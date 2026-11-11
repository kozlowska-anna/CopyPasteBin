import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin import bridge_cli, cli
from copypastebin import __version__
from copypastebin.config import save_customizations
from copypastebin.detection import CustomLiteralExclusion
from copypastebin.history import HistoryStore
from copypastebin.models import Category
from copypastebin.pause import PauseStore


class _Input(io.TextIOWrapper):
    def __init__(self, data):
        self.raw_stream = io.BytesIO(data)
        super().__init__(self.raw_stream, encoding="utf-8")


def frame(application, text):
    app = application.encode("ascii")
    return len(app).to_bytes(4, "big") + app + text.encode("utf-8")


class BridgeCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.config = Path(self.temporary.name) / "missing.toml"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, payload):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(
            [
                "--state-dir",
                str(self.state),
                "--config",
                str(self.config),
                "bridge",
                "observe",
            ],
            stdin=_Input(payload),
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_capabilities_are_stateless_and_do_not_read_input(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        input_stream = _Input(b"synthetic-private-canary")
        with patch("copypastebin.cli.HistoryStore") as history_type:
            code = cli.main(
                [
                    "--state-dir",
                    str(self.state),
                    "--config",
                    str(self.config),
                    "bridge",
                    "capabilities",
                ],
                stdin=input_stream,
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(0, code)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(
            {
                "document_version": 1,
                "product_version": __version__,
                "protocol_version": 2,
            },
            json.loads(stdout.getvalue()),
        )
        self.assertNotIn("synthetic-private-canary", stdout.getvalue())
        self.assertFalse(self.state.exists())
        self.assertFalse(self.config.exists())
        history_type.assert_not_called()

    def test_observe_returns_only_bounded_safe_metadata_and_records_no_content(self):
        canary = "ordinary private canary"
        code, stdout, stderr = self.run_cli(
            frame("org.mozilla.firefox", canary)
        )
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[],'
            '"history_eligible":true}\n',
            stdout,
        )
        entry = HistoryStore(self.state).recent()[0]
        self.assertEqual("org.mozilla.firefox", entry.source_application)
        self.assertNotIn(canary.encode(), HistoryStore(self.state).database_path.read_bytes())

    def test_warning_returns_safe_banner_shape_without_system_notifier(self):
        with patch("copypastebin.cli.DesktopNotifier") as notifier_type:
            code, stdout, stderr = self.run_cli(frame("app.one", "1234 PLN"))
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn('"risk":"low"', stdout)
        self.assertIn('"MONEY_AMOUNT_PLN_USD"', stdout)
        self.assertNotIn("1234", stdout)
        notifier_type.assert_not_called()

    def test_sentence_final_email_returns_bounded_warning_metadata(self):
        synthetic = "Kontakt: test@example.invalid."
        code, stdout, stderr = self.run_cli(frame("app.one", synthetic))
        self.assertEqual((0, ""), (code, stderr))
        self.assertIn('"risk":"medium"', stdout)
        self.assertIn('"EMAIL"', stdout)
        self.assertNotIn("test@example.invalid", stdout)

    def test_long_numeric_identifier_does_not_create_phone_warning(self):
        code, stdout, stderr = self.run_cli(
            frame("app.one", "1234-5678-9012-3456-7890-1234")
        )
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[],'
            '"history_eligible":true}\n',
            stdout,
        )

    def test_labeled_phone_fields_still_create_warning(self):
        code, stdout, stderr = self.run_cli(
            frame("app.one", "phone: 123456789 501234567")
        )
        self.assertEqual((0, ""), (code, stderr))
        self.assertIn('"risk":"low"', stdout)
        self.assertIn('"PHONE"', stdout)
        self.assertNotIn("501234567", stdout)

    def test_exact_exclusion_suppresses_false_positive_banner_only(self):
        save_customizations(
            (),
            (CustomLiteralExclusion(
                "5.6 Sol", Category.CRYPTO_AMOUNT_BTC_XRP
            ),),
            self.config,
        )
        code, stdout, stderr = self.run_cli(frame("app.one", "5.6 Sol"))
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[],'
            '"history_eligible":true}\n',
            stdout,
        )

        code, stdout, stderr = self.run_cli(
            frame("app.one", "5.6 Sol person@example.com")
        )
        self.assertEqual((0, ""), (code, stderr))
        self.assertIn('"risk":"medium"', stdout)
        self.assertNotIn('"CRYPTO_AMOUNT_BTC_XRP"', stdout)
        self.assertIn('"EMAIL"', stdout)

    def test_pause_and_bad_frame_fail_through_redacted_path(self):
        PauseStore(self.state).pause_indefinitely()
        for payload in (frame("app.one", "person@example.com"), b"bad"):
            with self.subTest(payload=payload[:10]):
                code, stdout, stderr = self.run_cli(payload)
                self.assertEqual(1, code)
                self.assertEqual("", stdout)
                self.assertEqual(
                    "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
                    stderr,
                )

class MinimalBridgeCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.config = Path(self.temporary.name) / "missing.toml"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, payload, *, arguments=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        selected_arguments = (
            [
                "--state-dir",
                str(self.state),
                "--config",
                str(self.config),
                "bridge",
                "observe",
            ]
            if arguments is None
            else arguments
        )
        code = bridge_cli.main(
            selected_arguments,
            stdin=_Input(payload),
            stdout=stdout,
            stderr=stderr,
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_capabilities_match_full_cli_without_state_access(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("copypastebin.bridge_cli.HistoryStore") as history_type:
            code = bridge_cli.main(
                ["bridge", "capabilities"],
                stdin=_Input(b"synthetic-private-canary"),
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual((0, ""), (code, stderr.getvalue()))
        self.assertEqual(__version__, json.loads(stdout.getvalue())["product_version"])
        self.assertFalse(self.state.exists())
        history_type.assert_not_called()

    def test_observe_matches_bounded_bridge_result_and_records_no_content(self):
        canary = "person@example.invalid"
        code, stdout, stderr = self.run_cli(frame("app.one", canary))
        self.assertEqual((0, ""), (code, stderr))
        self.assertIn('"risk":"medium"', stdout)
        self.assertNotIn(canary, stdout)
        self.assertNotIn(
            canary.encode(), HistoryStore(self.state).database_path.read_bytes()
        )

    def test_pause_bad_frame_and_usage_fail_without_echoing_input(self):
        PauseStore(self.state).pause_indefinitely()
        code, stdout, stderr = self.run_cli(
            frame("app.one", "private-canary")
        )
        self.assertEqual((1, ""), (code, stdout))
        self.assertNotIn("private-canary", stderr)

        code, stdout, stderr = self.run_cli(
            b"private-canary",
            arguments=["--unknown-private-canary"],
        )
        self.assertEqual((2, ""), (code, stdout))
        self.assertNotIn("private-canary", stderr)


if __name__ == "__main__":
    unittest.main()
