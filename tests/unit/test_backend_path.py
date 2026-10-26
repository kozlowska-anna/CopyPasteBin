import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "gnome-extension" / "copypastebin@kozlowska-anna.github.io"
RESOLVER = EXTENSION / "backend-path.js"
DRIVER = ROOT / "tests" / "helpers" / "backend_path_driver.js"
GJS = Path("/usr/bin/gjs")
SYSTEM = "/usr/bin/cpb"
USER = "/home/example/.local/share/copypastebin/venv/bin/cpb"


@unittest.skipUnless(GJS.exists(), "GJS is required by the GNOME extension")
class BackendPathTests(unittest.TestCase):
    def resolve(self, *available: str) -> str:
        completed = subprocess.run(
            [str(GJS), "-m", str(DRIVER), SYSTEM, USER, *available],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    def test_system_backend_wins_when_both_installations_exist(self):
        self.assertEqual(SYSTEM, self.resolve(USER, SYSTEM))

    def test_user_backend_is_the_compatible_fallback(self):
        self.assertEqual(USER, self.resolve(USER))

    def test_missing_backend_fails_closed(self):
        self.assertEqual("NONE", self.resolve())

    def test_resolver_uses_only_two_fixed_absolute_candidates(self):
        source = RESOLVER.read_text(encoding="utf-8")
        self.assertIn("export const SYSTEM_BACKEND_PATH = '/usr/bin/cpb'", source)
        self.assertIn("'.local'", source)
        self.assertIn("'venv'", source)
        self.assertIn("GLib.FileTest.IS_REGULAR", source)
        self.assertIn("GLib.FileTest.IS_EXECUTABLE", source)
        for forbidden in ("find_program_in_path", "getenv('PATH')", 'getenv("PATH")'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
