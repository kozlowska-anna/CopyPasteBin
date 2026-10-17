import io
import os
import tempfile
import unittest
from pathlib import Path

from copypastebin.input_sources import InputError, MAX_INPUT_BYTES, decode_text, read_stream, read_text_file
from copypastebin.safe_text import neutralize_for_terminal


class InputAndDisplayTests(unittest.TestCase):
    def test_utf8_bom_and_limits(self):
        self.assertEqual("ok", decode_text(b"\xef\xbb\xbfok"))
        for data in (b"bad\x00text", b"\xff", b"x" * (MAX_INPUT_BYTES + 1)):
            with self.subTest(length=len(data)), self.assertRaises(InputError):
                decode_text(data)

    def test_file_rejects_symlink_and_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_text("ok", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(InputError):
                read_text_file(link)
            with self.assertRaises(InputError):
                read_text_file(root)

    def test_terminal_controls_are_neutralized(self):
        value = "safe\x1b[31m\u202esecret\x00"
        rendered = neutralize_for_terminal(value)
        self.assertNotIn("\x1b", rendered)
        self.assertNotIn("\u202e", rendered)
        self.assertNotIn("\x00", rendered)

    def test_interrupted_stream_is_redacted_input_error(self):
        class BrokenStream:
            def read(self, size):
                raise OSError("private-canary-path")

        with self.assertRaises(InputError) as caught:
            read_stream(BrokenStream())
        self.assertNotIn("private-canary", str(caught.exception) + repr(caught.exception))
