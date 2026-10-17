import json
import tempfile
import unittest
from pathlib import Path

from copypastebin.filters import (
    AUTO_CLEAR_CHOICES,
    DEFAULT_DISABLED_CATEGORIES,
    FilterError,
    FilterStore,
)
from copypastebin.models import Category


class FilterStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.store = FilterStore(self.state)

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_state_uses_safe_defaults_without_creating_a_file(self):
        status = self.store.status()
        self.assertEqual(
            frozenset(
                {
                    Category.HOME_PATH,
                    Category.POSSIBLE_SEED_PHRASE,
                    Category.TOKEN,
                }
            ),
            DEFAULT_DISABLED_CATEGORIES,
        )
        self.assertEqual(DEFAULT_DISABLED_CATEGORIES, status.disabled)
        self.assertEqual(0, status.auto_clear_seconds)
        self.assertTrue(status.enabled(Category.EMAIL))
        self.assertTrue(status.enabled(Category.OPENAI_API_KEY))
        self.assertFalse(status.enabled(Category.HOME_PATH))
        self.assertFalse(status.enabled(Category.POSSIBLE_SEED_PHRASE))
        self.assertFalse(status.enabled(Category.TOKEN))
        self.assertFalse(self.state.exists())

    def test_disable_and_enable_are_persistent_and_category_specific(self):
        self.store.set_enabled(Category.HOME_PATH, False)
        self.store.set_enabled(Category.MONEY_AMOUNT_PLN_USD, False)
        other = FilterStore(self.state)
        self.assertFalse(other.status().enabled(Category.HOME_PATH))
        self.assertFalse(other.status().enabled(Category.MONEY_AMOUNT_PLN_USD))
        self.assertTrue(other.status().enabled(Category.EMAIL))
        other.set_enabled(Category.HOME_PATH, True)
        self.assertTrue(self.store.status().enabled(Category.HOME_PATH))

    def test_existing_state_overrides_fresh_install_defaults_without_rewrite(self):
        self.state.mkdir(mode=0o700)
        payload = '{"auto_clear_seconds":0,"disabled":[],"version":2}'
        self.store.state_path.write_text(payload, encoding="ascii")
        self.store.state_path.chmod(0o600)

        status = self.store.status()

        self.assertEqual(frozenset(), status.disabled)
        self.assertTrue(all(status.enabled(category) for category in Category))
        self.assertEqual(payload, self.store.state_path.read_text(encoding="ascii"))

    def test_state_is_private_canonical_and_contains_no_clipboard_data(self):
        self.store.set_enabled(Category.CRYPTO_AMOUNT_BTC_XRP, False)
        self.assertEqual(0o700, self.state.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.store.state_path.stat().st_mode & 0o777)
        document = json.loads(self.store.state_path.read_text(encoding="ascii"))
        self.assertEqual(
            {
                "auto_clear_seconds": 0,
                "disabled": [
                    "CRYPTO_AMOUNT_BTC_XRP",
                    "HOME_PATH",
                    "POSSIBLE_SEED_PHRASE",
                    "TOKEN",
                ],
                "version": 2,
            },
            document,
        )
        self.assertNotIn("clipboard", self.store.state_path.read_text(encoding="ascii"))

    def test_corrupt_extended_or_noncanonical_state_fails_closed(self):
        self.state.mkdir(mode=0o700)
        cases = (
            b"not-json",
            b"[]",
            b'{"auto_clear_seconds":1,"disabled":[],"version":2}',
            b'{"disabled":[],"version":3}',
            b'{"disabled":[],"extra":1,"version":1}',
            b'{"disabled":["UNKNOWN"],"version":1}',
            b'{"disabled":["EMAIL","EMAIL"],"version":1}',
        )
        for payload in cases:
            with self.subTest(payload=payload):
                self.store.state_path.write_bytes(payload)
                self.store.state_path.chmod(0o600)
                with self.assertRaises(FilterError):
                    self.store.status()

    def test_legacy_state_is_read_and_migrated_on_next_write(self):
        self.state.mkdir(mode=0o700)
        self.store.state_path.write_text(
            '{"disabled":["HOME_PATH"],"version":1}', encoding="ascii"
        )
        self.store.state_path.chmod(0o600)
        status = self.store.status()
        self.assertFalse(status.enabled(Category.HOME_PATH))
        self.assertEqual(0, status.auto_clear_seconds)
        self.store.set_auto_clear(300)
        document = json.loads(self.store.state_path.read_text(encoding="ascii"))
        self.assertEqual(2, document["version"])
        self.assertEqual(300, document["auto_clear_seconds"])
        self.assertEqual(["HOME_PATH"], document["disabled"])

    def test_auto_clear_choices_are_persistent_and_closed(self):
        for seconds in AUTO_CLEAR_CHOICES:
            with self.subTest(seconds=seconds):
                status = self.store.set_auto_clear(seconds)
                self.assertEqual(seconds, status.auto_clear_seconds)
                self.assertEqual(seconds, FilterStore(self.state).status().auto_clear_seconds)
        for invalid in (-1, 1, 61, 3600, True, "60"):
            with self.subTest(invalid=invalid), self.assertRaises(FilterError):
                self.store.set_auto_clear(invalid)

    def test_symlink_and_non_private_state_are_rejected(self):
        target = self.root / "target"
        target.mkdir(mode=0o700)
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(FilterError):
            self.store.set_enabled(Category.EMAIL, False)

        self.state.unlink()
        self.state.mkdir(mode=0o700)
        foreign = self.root / "foreign"
        foreign.write_text('{"disabled":[],"version":1}', encoding="ascii")
        self.store.state_path.symlink_to(foreign)
        with self.assertRaises(FilterError):
            self.store.status()
        self.assertTrue(self.store.state_path.is_symlink())

    def test_wrong_permissions_and_oversized_state_are_rejected(self):
        self.store.set_enabled(Category.EMAIL, False)
        self.store.state_path.chmod(0o644)
        with self.assertRaises(FilterError):
            self.store.status()

        self.store.state_path.unlink()
        self.store.state_path.write_bytes(b"x" * 1025)
        self.store.state_path.chmod(0o600)
        with self.assertRaises(FilterError):
            self.store.status()

    def test_invalid_types_and_error_text_are_closed(self):
        for category, enabled in (("EMAIL", True), (Category.EMAIL, 1)):
            with self.subTest(category=category, enabled=enabled):
                with self.assertRaises(FilterError):
                    self.store.set_enabled(category, enabled)
        error = FilterError("private-canary")
        self.assertEqual(
            "Nie udało się bezpiecznie obsłużyć ustawień filtrów.", str(error)
        )
        self.assertEqual("FilterError(redacted=True)", repr(error))
        self.assertNotIn("private-canary", str(error) + repr(error))


if __name__ == "__main__":
    unittest.main()
