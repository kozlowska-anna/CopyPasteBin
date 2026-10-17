import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from copypastebin import cli
from copypastebin.filters import FilterStore
from copypastebin.models import Category


class _Input(io.TextIOWrapper):
    def __init__(self, value: bytes):
        self.raw_stream = io.BytesIO(value)
        super().__init__(self.raw_stream, encoding="utf-8")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name) / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, argv, data=b""):
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = cli.main(["--state-dir", str(self.state), "--config", str(Path(self.temporary.name) / "missing.toml"), *argv], stdin=_Input(data), stdout=stdout, stderr=stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def synthetic_clipboard_backend(self, body: str) -> Path:
        path = Path(self.temporary.name) / "synthetic-wl-paste"
        path.write_text(
            "#!/usr/bin/python3\n"
            "import os\n"
            "import sys\n"
            "import time\n"
            "if sys.argv[1:] != ['--no-newline', '--type', 'text']:\n"
            "    raise SystemExit(91)\n"
            f"{body}\n",
            encoding="utf-8",
        )
        path.chmod(0o700)
        return path

    def test_stdin_no_detection_has_required_disclaimer(self):
        code, stdout, stderr = self.run_cli([], b"ordinary text 1234")
        self.assertEqual(0, code)
        self.assertIn("To nie gwarantuje", stdout)
        self.assertEqual("", stderr)

    def test_file_and_clipboard_are_explicit_sources(self):
        path = Path(self.temporary.name) / "input.txt"
        path.write_text("1234 PLN", encoding="utf-8")
        code, stdout, _ = self.run_cli(["--file", str(path)])
        self.assertEqual(0, code)
        self.assertIn("MONEY_AMOUNT_PLN_USD", stdout)
        with patch("copypastebin.cli.read_clipboard", return_value="person@example.com") as reader:
            code, stdout, _ = self.run_cli(["--clipboard"])
        self.assertEqual(0, code)
        reader.assert_called_once_with()
        self.assertIn("EMAIL", stdout)

    def test_explicit_analysis_respects_persistent_filter_settings(self):
        FilterStore(self.state).set_enabled(Category.EMAIL, False)
        code, stdout, stderr = self.run_cli([], b"person@example.com 1234 PLN")
        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertNotIn("category=EMAIL", stdout)
        self.assertIn("MONEY_AMOUNT_PLN_USD", stdout)

    def test_mutually_exclusive_sources_fail_without_leak(self):
        path = Path(self.temporary.name) / "private-canary\x1b.txt"
        code, stdout, stderr = self.run_cli(["--file", str(path), "--clipboard"])
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertNotIn("private-canary", stderr)
        self.assertNotIn("\x1b", stderr)

    def test_high_risk_original_requires_exact_interactive_phrase(self):
        copied = []
        with patch("copypastebin.cli.write_clipboard", side_effect=copied.append):
            code, stdout, stderr = self.run_cli(["--copy", "original"], b"password=private-canary\nwrong\n")
        self.assertEqual(1, code)
        self.assertEqual([], copied)
        self.assertNotIn("private-canary", stdout + stderr)

    def test_redacted_copy_never_passes_original(self):
        copied = []
        with patch("copypastebin.cli.write_clipboard", side_effect=copied.append):
            code, stdout, stderr = self.run_cli(["--copy", "redacted"], b"person@example.com")
        self.assertEqual(0, code)
        self.assertEqual(["[EMAIL_1]"], copied)
        self.assertNotIn("person@example.com", stdout + stderr)

    def test_history_shows_only_eight_and_no_content(self):
        for number in range(10):
            self.run_cli([], f"person{number}@example.com".encode())
        code, stdout, stderr = self.run_cli(["history"])
        self.assertEqual(0, code)
        self.assertEqual(8, len(stdout.strip().splitlines()))
        self.assertNotIn("@example.com", stdout + stderr)

    def test_unknown_options_do_not_echo_private_argument(self):
        code, stdout, stderr = self.run_cli(["--private-canary\x1b"])
        self.assertEqual(2, code)
        self.assertEqual("", stdout)
        self.assertNotIn("private-canary", stderr)
        self.assertNotIn("\x1b", stderr)

    def test_file_high_risk_original_can_only_use_exact_phrase(self):
        path = Path(self.temporary.name) / "input.txt"
        path.write_text("password=synthetic-secret", encoding="utf-8")
        copied = []
        stdout = io.StringIO()
        stderr = io.StringIO()
        # First obtain a deterministic operation ID from the prompt by replacing UUID generation.
        with patch("copypastebin.history.uuid.uuid4", return_value="00000000-0000-0000-0000-000000000001"), patch("copypastebin.cli.write_clipboard", side_effect=copied.append):
            code = cli.main(
                ["--state-dir", str(self.state), "--config", str(Path(self.temporary.name) / "missing.toml"), "--file", str(path), "--copy", "original"],
                stdin=_Input(b"COPY 00000000-0000-0000-0000-000000000001\n"),
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(0, code)
        self.assertEqual(["password=synthetic-secret"], copied)
        self.assertNotIn("synthetic-secret", stdout.getvalue() + stderr.getvalue())

    def test_input_is_not_executed(self):
        marker = Path(self.temporary.name) / "must-not-exist"
        payload = f"$(touch {marker}) `touch {marker}`; touch {marker}".encode()
        code, _, _ = self.run_cli([], payload)
        self.assertEqual(0, code)
        self.assertFalse(marker.exists())

    def test_failed_clipboard_write_has_safe_error_and_failed_history(self):
        with patch("copypastebin.cli.write_clipboard", side_effect=cli.ClipboardError()):
            code, stdout, stderr = self.run_cli(["--copy", "redacted"], b"person@example.com")
        self.assertEqual(1, code)
        self.assertNotIn("person@example.com", stdout + stderr)
        from copypastebin.history import HistoryStore
        self.assertEqual("failed", HistoryStore(self.state).recent()[0].status)

    def test_clipboard_backend_receives_fixed_argv_and_stdin(self):
        with patch("copypastebin.clipboard.shutil.which", return_value="/usr/bin/wl-copy"), patch("copypastebin.clipboard.subprocess.run") as run:
            run.return_value.returncode = 0
            from copypastebin.clipboard import write_clipboard
            write_clipboard("$(touch /tmp/never) `id` private-canary")
        kwargs = run.call_args.kwargs
        self.assertEqual(["/usr/bin/wl-copy", "--type", "text/plain;charset=utf-8"], run.call_args.args[0])
        self.assertIn(b"private-canary", kwargs["input"])
        self.assertFalse(kwargs["shell"])

    def test_clipboard_read_uses_fixed_argv_and_suppresses_backend_errors(self):
        backend = self.synthetic_clipboard_backend(
            "os.write(2, b'private-canary\\x1b')\n"
            "os.write(1, b'1234 PLN')"
        )
        with patch("copypastebin.clipboard.shutil.which", return_value=str(backend)):
            from copypastebin.clipboard import read_clipboard
            self.assertEqual("1234 PLN", read_clipboard())

    def test_clipboard_read_process_has_fixed_safe_shape(self):
        process = object()
        with patch(
            "copypastebin.clipboard.shutil.which", return_value="/usr/bin/wl-paste"
        ), patch(
            "copypastebin.clipboard.subprocess.Popen", return_value=process
        ) as popen, patch(
            "copypastebin.clipboard._read_limited_output", return_value=b"hello"
        ) as read_limited, patch(
            "copypastebin.clipboard._close_process"
        ) as close_process:
            from copypastebin.clipboard import MAX_INPUT_BYTES, read_clipboard

            self.assertEqual("hello", read_clipboard())

        self.assertEqual(
            ["/usr/bin/wl-paste", "--no-newline", "--type", "text"],
            popen.call_args.args[0],
        )
        self.assertIs(subprocess.DEVNULL, popen.call_args.kwargs["stdin"])
        self.assertIs(subprocess.PIPE, popen.call_args.kwargs["stdout"])
        self.assertIs(subprocess.DEVNULL, popen.call_args.kwargs["stderr"])
        self.assertFalse(popen.call_args.kwargs["shell"])
        self.assertTrue(popen.call_args.kwargs["close_fds"])
        read_limited.assert_called_once_with(process, 5.0, MAX_INPUT_BYTES)
        close_process.assert_called_once_with(process)

    def test_clipboard_read_accepts_empty_text_result(self):
        backend = self.synthetic_clipboard_backend("pass")
        with patch("copypastebin.clipboard.shutil.which", return_value=str(backend)):
            from copypastebin.clipboard import read_clipboard

            self.assertEqual("", read_clipboard())

    def test_clipboard_read_accepts_exact_limit(self):
        backend = self.synthetic_clipboard_backend("os.write(1, b'x' * 32)")
        with patch("copypastebin.clipboard.shutil.which", return_value=str(backend)), patch("copypastebin.clipboard.MAX_INPUT_BYTES", 32):
            from copypastebin.clipboard import read_clipboard
            self.assertEqual("x" * 32, read_clipboard())

    def test_clipboard_read_rejects_limit_plus_one_without_full_buffering(self):
        backend = self.synthetic_clipboard_backend(
            "chunk = b'x' * 65536\n"
            "while True:\n"
            "    os.write(1, chunk)"
        )
        requested: list[int] = []
        real_read = os.read

        def tracked_read(fd, size):
            requested.append(size)
            return real_read(fd, size)

        with patch("copypastebin.clipboard.shutil.which", return_value=str(backend)), patch("copypastebin.clipboard.MAX_INPUT_BYTES", 32), patch("copypastebin.clipboard.os.read", side_effect=tracked_read):
            from copypastebin.clipboard import ClipboardError, read_clipboard
            with self.assertRaises(ClipboardError):
                read_clipboard()
        self.assertEqual([33], requested)

    def test_clipboard_read_errors_are_safe_and_processes_are_closed(self):
        cases = (
            (
                "os.write(2, b'private-canary\\x1b')\nraise SystemExit(7)",
                5.0,
            ),
            ("os.write(1, b'\\xff')", 5.0),
            ("os.write(1, b'a\\x00b')", 5.0),
            ("time.sleep(1)", 0.02),
        )
        from copypastebin.clipboard import ClipboardError, read_clipboard
        for body, timeout in cases:
            with self.subTest(body=body):
                backend = self.synthetic_clipboard_backend(body)
                with patch("copypastebin.clipboard.shutil.which", return_value=str(backend)), patch("copypastebin.clipboard.CLIPBOARD_TIMEOUT_SECONDS", timeout):
                    with self.assertRaises(ClipboardError) as caught:
                        read_clipboard()
                rendered = str(caught.exception) + repr(caught.exception)
                self.assertNotIn("private-canary", rendered)
                self.assertNotIn("\x1b", rendered)

    def test_bip39_resource_failure_blocks_public_operation_safely(self):
        from copypastebin.detection import load_bip39_words

        load_bip39_words.cache_clear()
        try:
            with patch("copypastebin.detection.BIP39_RESOURCE_SHA256", "0" * 64):
                code, stdout, stderr = self.run_cli([], b"ordinary text private-canary\x1b")
        finally:
            load_bip39_words.cache_clear()
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertNotIn("private-canary", stderr)
        self.assertNotIn("\x1b", stderr)

    def test_missing_bip39_resource_package_has_safe_public_error(self):
        from copypastebin.detection import load_bip39_words

        load_bip39_words.cache_clear()
        try:
            with patch(
                "copypastebin.detection.files",
                side_effect=ModuleNotFoundError("synthetic-resource-package"),
            ):
                code, stdout, stderr = self.run_cli(
                    [], b"ordinary text private-canary\x1b"
                )
        finally:
            load_bip39_words.cache_clear()
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertEqual(
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n",
            stderr,
        )
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("private-canary", stderr)
        self.assertNotIn("\x1b", stderr)
