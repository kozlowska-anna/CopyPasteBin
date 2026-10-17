import unittest

from copypastebin.application_id import normalize_application_id


class ApplicationIdTests(unittest.TestCase):
    def test_safe_stable_ids_are_preserved(self):
        for value in ("org.mozilla.firefox", "libreoffice-writer", "Code_1.desktop"):
            self.assertEqual(value, normalize_application_id(value))

    def test_untrusted_or_unbounded_ids_become_unknown(self):
        for value in (
            None,
            True,
            "",
            "../private",
            "has space",
            "line\nbreak",
            "ąpp",
            "a" * 129,
        ):
            with self.subTest(value=value):
                self.assertEqual("unknown", normalize_application_id(value))


if __name__ == "__main__":
    unittest.main()
