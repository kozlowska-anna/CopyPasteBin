import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin import cli
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

    def test_observe_returns_only_bounded_safe_metadata_and_records_no_content(self):
        canary = "ordinary private canary"
        code, stdout, stderr = self.run_cli(
            frame("org.mozilla.firefox", canary)
        )
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[]}\n',
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

    def test_long_numeric_identifier_does_not_create_phone_warning(self):
        code, stdout, stderr = self.run_cli(
            frame("app.one", "1234-5678-9012-3456-7890-1234")
        )
        self.assertEqual((0, ""), (code, stderr))
        self.assertEqual(
            '{"version":1,"risk":"none","categories":[]}\n',
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
            '{"version":1,"risk":"none","categories":[]}\n',
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


if __name__ == "__main__":
    unittest.main()
