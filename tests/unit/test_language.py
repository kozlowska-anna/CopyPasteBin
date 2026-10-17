import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin.language import LanguageError, LanguageStore


class LanguageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"
        self.store = LanguageStore(self.state)

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_state_uses_system_language_without_writing(self):
        with patch("copypastebin.language.locale.getlocale", return_value=("pl_PL", "UTF-8")):
            self.assertEqual(("system", "pl"), (
                self.store.status().choice,
                self.store.status().effective,
            ))
        self.assertFalse(self.state.exists())

    def test_choice_is_private_persistent_and_closed(self):
        status = self.store.set_choice("en")
        self.assertEqual(("en", "en"), (status.choice, status.effective))
        self.assertEqual(0o700, self.state.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.store.state_path.stat().st_mode & 0o777)
        self.assertEqual(
            {"choice": "en", "version": 1},
            json.loads(self.store.state_path.read_text(encoding="ascii")),
        )
        self.assertEqual("en", LanguageStore(self.state).status().choice)
        for invalid in ("de", "", True, None):
            with self.subTest(invalid=invalid), self.assertRaises(LanguageError):
                self.store.set_choice(invalid)

    def test_corrupt_symlink_or_non_private_state_fails_closed(self):
        self.state.mkdir(mode=0o700)
        self.store.state_path.write_text('{"choice":"en","extra":1,"version":1}')
        self.store.state_path.chmod(0o600)
        with self.assertRaises(LanguageError):
            self.store.status()
        self.store.state_path.unlink()
        target = self.state / "target"
        target.write_text('{"choice":"en","version":1}')
        self.store.state_path.symlink_to(target)
        with self.assertRaises(LanguageError):
            self.store.status()

    def test_error_does_not_disclose_cause(self):
        error = LanguageError("private-canary")
        self.assertEqual("Unable to safely handle the language setting.", str(error))
        self.assertEqual("LanguageError(redacted=True)", repr(error))
        self.assertNotIn("private-canary", str(error) + repr(error))


if __name__ == "__main__":
    unittest.main()
