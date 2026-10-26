import binascii
import os
import struct
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "gnome-extension" / "copypastebin@kozlowska-anna.github.io"
CORE = EXTENSION / "image-redaction-core.js"
EDITOR = EXTENSION / "image-redactor.js"
DRIVER = ROOT / "tests" / "helpers" / "image_redaction_driver.js"
GJS = Path("/usr/bin/gjs")


def run_driver(*arguments: object, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(GJS), "-m", str(DRIVER), *(str(argument) for argument in arguments)],
        check=check,
        capture_output=True,
        text=True,
        env={**os.environ, "G_MESSAGES_DEBUG": ""},
    )


def add_png_text_chunk(path: Path) -> None:
    content = path.read_bytes()
    offset = 8
    while offset < len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        kind = content[offset + 4 : offset + 8]
        if kind == b"IEND":
            payload = b"SyntheticNote\x00must-not-survive"
            chunk = (
                struct.pack(">I", len(payload))
                + b"tEXt"
                + payload
                + struct.pack(">I", binascii.crc32(b"tEXt" + payload) & 0xFFFFFFFF)
            )
            path.write_bytes(content[:offset] + chunk + content[offset:])
            return
        offset += 12 + length
    raise AssertionError("IEND chunk not found")


def png_chunk_types(path: Path) -> list[bytes]:
    content = path.read_bytes()
    result = []
    offset = 8
    while offset < len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        kind = content[offset + 4 : offset + 8]
        result.append(kind)
        offset += 12 + length
    return result


@unittest.skipUnless(GJS.exists(), "GJS is required by the GNOME image editor")
class ImageRedactionTests(unittest.TestCase):
    def test_rectangle_is_normalized_and_clamped(self):
        completed = run_driver("normalize", 7.8, 5.2, -3, 1, 8, 6)
        self.assertEqual(
            completed.stdout.strip(),
            '{"x":0,"y":1,"width":8,"height":5}',
        )

    def test_png_pixels_are_replaced_and_source_metadata_is_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic.png"
            output = Path(directory) / "safe-copy.png"
            run_driver("create", "png", source)
            add_png_text_chunk(source)

            run_driver("redact", source, output)

            self.assertEqual(run_driver("inspect", output, 3, 2).stdout.strip(), "32,32,32,255")
            self.assertIn(b"tEXt", png_chunk_types(source))
            self.assertNotIn(b"tEXt", png_chunk_types(output))
            self.assertTrue(source.exists())
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_jpeg_input_is_saved_as_a_new_png(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic.jpg"
            output = Path(directory) / "safe-copy.png"
            run_driver("create", "jpeg", source)
            before = source.read_bytes()

            run_driver("redact", source, output)

            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(output.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic.png"
            output = Path(directory) / "existing.png"
            run_driver("create", "png", source)
            output.write_bytes(b"keep me")

            completed = run_driver("redact", source, output, check=False)

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(output.read_bytes(), b"keep me")

    def test_symlink_and_oversized_inputs_are_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic.png"
            link = Path(directory) / "linked.png"
            output = Path(directory) / "safe-copy.png"
            run_driver("create", "png", source)
            link.symlink_to(source)

            linked = run_driver("redact", link, output, check=False)
            self.assertNotEqual(linked.returncode, 0)
            self.assertFalse(output.exists())

            oversized = Path(directory) / "oversized.png"
            with oversized.open("wb") as stream:
                stream.truncate(100 * 1024 * 1024 + 1)
            too_large = run_driver("redact", oversized, output, check=False)
            self.assertNotEqual(too_large.returncode, 0)
            self.assertFalse(output.exists())

    def test_editor_is_separate_local_file_only_process(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        core = CORE.read_text(encoding="utf-8")
        editor = EDITOR.read_text(encoding="utf-8")
        self.assertIn("Anonymize image", extension)
        self.assertIn("this._imageRedactorPath", extension)
        self.assertIn("Gio.SubprocessFlags.STDOUT_SILENCE", extension)
        redactor_method = extension[
            extension.index("\n    _openImageRedactor() {") :
            extension.index("\n    _addQuitAction() {")
        ]
        self.assertNotIn("STDIN_PIPE", redactor_method)
        self.assertIn("Only PNG and JPEG images are supported.", core)
        self.assertIn("Gio.FileCreateFlags.PRIVATE", core)
        self.assertIn("outputFile.create", core)
        self.assertNotIn("replace", core)
        for forbidden in ("St.Clipboard", "get_text", "screenshot", "Soup", "http://", "https://", "mktemp"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, core + editor)


if __name__ == "__main__":
    unittest.main()
