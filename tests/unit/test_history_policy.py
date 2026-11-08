import unittest

from copypastebin.detection import detect_text
from copypastebin.history_policy import history_text_is_eligible


class HistoryPolicyTests(unittest.TestCase):
    def eligible(self, text):
        return history_text_is_eligible(text, detect_text(text))

    def test_recognized_private_key_token_seed_and_password_are_rejected(self):
        cases = (
            "-----BEGIN PRIVATE KEY-----\nSYNTHETIC\n-----END PRIVATE KEY-----",
            "github_pat_" + "A1" * 40,
            "abandon abandon abandon abandon abandon abandon abandon abandon "
            "abandon abandon abandon about",
            "password: synthetic-only-value",
        )
        for text in cases:
            with self.subTest(text=text[:20]):
                self.assertFalse(self.eligible(text))

    def test_standalone_high_entropy_password_is_history_only_rejection(self):
        text = "Kx9#mP42!qT7&vL"
        self.assertEqual((), detect_text(text))
        self.assertFalse(self.eligible(text))

    def test_one_trailing_line_ending_does_not_bypass_secret_policy(self):
        for line_ending in ("\n", "\r\n"):
            with self.subTest(line_ending=repr(line_ending)):
                text = "Kx9#mP42!qT7&vL" + line_ending
                self.assertEqual((), detect_text(text))
                self.assertFalse(self.eligible(text))

    def test_at_sign_does_not_bypass_standalone_secret_policy(self):
        cases = (
            "Kx9#mP42@qT7&vL",
            "Kx9#mP42@qT7@vL",
            "Person42@example",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual((), detect_text(text))
                self.assertFalse(self.eligible(text))

    def test_full_email_detection_remains_eligible(self):
        for line_ending in ("", "\n", "\r\n"):
            with self.subTest(line_ending=repr(line_ending)):
                address = "Person42@example.com"
                text = address + line_ending
                detections = detect_text(text)
                self.assertEqual(1, len(detections))
                self.assertEqual("EMAIL", detections[0].category.value)
                self.assertEqual(
                    (0, len(address)),
                    (detections[0].start, detections[0].end),
                )
                self.assertTrue(history_text_is_eligible(text, detections))

    def test_email_detection_does_not_exempt_surrounding_characters(self):
        for text in ("Person42@example.com!", "(Person42@example.com)"):
            with self.subTest(text=text):
                detections = detect_text(text)
                self.assertEqual(1, len(detections))
                self.assertNotEqual(
                    (0, len(text)),
                    (detections[0].start, detections[0].end),
                )
                self.assertFalse(history_text_is_eligible(text, detections))

    def test_ordinary_text_and_common_non_secret_shapes_remain_eligible(self):
        cases = (
            "Zwykła syntetyczna notatka do późniejszego użycia.",
            "https://example.invalid/docs/history",
            "/tmp/synthetic/report.txt",
            "customer_order_reference_2026",
            "const result = calculateTotal(items);",
            "550e8400-e29b-41d4-a716-446655440000",
        )
        for text in cases:
            for line_ending in ("", "\n", "\r\n"):
                with self.subTest(text=text, line_ending=repr(line_ending)):
                    self.assertTrue(self.eligible(text + line_ending))

    def test_line_ending_preserves_policy_for_high_entropy_technical_ids(self):
        cases = (
            "7f3a9c2d1e0b4a6f8c9d2e3f4a5b6c7d8e9f0a1b",
            "copypastebin_1.2-2_all",
        )
        for text in cases:
            baseline = self.eligible(text)
            self.assertFalse(baseline)
            for line_ending in ("\n", "\r\n"):
                with self.subTest(text=text, line_ending=repr(line_ending)):
                    self.assertEqual(baseline, self.eligible(text + line_ending))

    def test_other_whitespace_exceptions_remain_unchanged(self):
        secret = "Kx9#mP42!qT7&vL"
        cases = (
            secret + "\n\n",
            secret + "\r",
            secret + " ",
            secret + "\t",
            " " + secret,
            secret + "\nsecond-line",
        )
        for text in cases:
            with self.subTest(text=repr(text)):
                self.assertEqual((), detect_text(text))
                self.assertTrue(self.eligible(text))


if __name__ == "__main__":
    unittest.main()
