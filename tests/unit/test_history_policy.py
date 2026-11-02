Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
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

    def test_ordinary_text_and_common_non_secret_shapes_remain_eligible(self):
        cases = (
            "Zwykła syntetyczna notatka do późniejszego użycia.",
            "https://example.invalid/docs/history",
            "customer_order_reference_2026",
            "const result = calculateTotal(items);",
            "550e8400-e29b-41d4-a716-446655440000",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(self.eligible(text))


if __name__ == "__main__":
    unittest.main()
