"""Static checks of the Windows stage 0 sources.

These checks run on any system. They confirm what the source text does and
does not contain. They do NOT prove that the tools compile or behave
correctly on Windows.

Run from the repository root:

    python3 -B -m unittest discover -s windows/checks -v
"""

import re
import unittest
from pathlib import Path


WINDOWS = Path(__file__).resolve().parents[1]
SRC = WINDOWS / "src"
PROBE_SOURCES = ("Native.cs", "Common.cs", "ClipboardProbe.cs")
ALL_SOURCES = PROBE_SOURCES + ("SyntheticOwner.cs", "ClipboardBlocker.cs")
CANARY = "CPB-STAGE0-CANARY"


def read(name):
    return (SRC / name).read_text(encoding="utf-8")


def strip_comments_and_strings(source):
    source = re.sub(r"///?[^\n]*", "", source)
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', source)


class Stage0SourceTests(unittest.TestCase):
    def test_expected_files_exist_and_are_the_only_sources(self):
        self.assertEqual(
            sorted(path.name for path in SRC.iterdir()), sorted(ALL_SOURCES)
        )

    def test_native_entry_points_are_a_closed_list(self):
        native = read("Native.cs")
        declared = set(re.findall(r"public static extern [\w.]+ (\w+)\(", native))
        self.assertEqual(
            declared,
            {
                "AddClipboardFormatListener",
                "RemoveClipboardFormatListener",
                "GetClipboardSequenceNumber",
                "IsClipboardFormatAvailable",
                "OpenClipboard",
                "CloseClipboard",
                "EmptyClipboard",
                "GetClipboardData",
                "SetClipboardData",
                "GetClipboardOwner",
                "RegisterClipboardFormat",
                "GlobalAlloc",
                "GlobalFree",
                "GlobalLock",
                "GlobalUnlock",
                "GlobalSize",
                "GetCurrentProcessId",
                "ProcessIdToSessionId",
                "WTSRegisterSessionNotification",
                "WTSUnRegisterSessionNotification",
            },
        )
        for name in ALL_SOURCES:
            if name != "Native.cs":
                self.assertNotIn("DllImport", read(name), name)

    def test_no_source_identifies_programs_or_uses_network_or_registry(self):
        forbidden = (
            "GetWindowText",
            "GetWindowThreadProcessId",
            "GetForegroundWindow",
            "EnumClipboardFormats",
            "GetClipboardFormatName",
            "CountClipboardFormats",
            "GetUpdatedClipboardFormats",
            "System.Net",
            "System.Diagnostics.Process",
            "Process.",
            "Registry",
            "Environment.UserName",
            "MachineName",
            "Clipboard.GetText",
            "Clipboard.GetData",
            "DateTime",
            "File.",
            "http",
        )
        for name in ALL_SOURCES:
            source = read(name)
            for token in forbidden:
                self.assertNotIn(token, source, f"{token} in {name}")

    def test_probe_requests_only_privacy_flags_and_synthetic_format(self):
        probe = strip_comments_and_strings(read("ClipboardProbe.cs"))
        requested = re.findall(r"GetClipboardData\(([^)]*)\)", probe)
        self.assertEqual(sorted(requested), ["format", "formatSynthetic"])
        callers = re.findall(r"ReadPrivacyFlag\(([^)]*)\)", probe)
        self.assertEqual(
            sorted(callers), ["formatCloud", "formatHistory", "uint format"]
        )
        text_uses = re.findall(r"[^\n]*CF_UNICODETEXT[^\n]*", probe)
        self.assertEqual(len(text_uses), 1)
        self.assertIn("IsClipboardFormatAvailable(Native.CF_UNICODETEXT)", text_uses[0])

    def test_probe_never_writes_or_owns_the_clipboard(self):
        probe = strip_comments_and_strings(read("ClipboardProbe.cs"))
        for token in ("SetClipboardData", "EmptyClipboard", "GetClipboardOwner",
                      "GlobalAlloc", "Marshal.Copy", "PtrToString"):
            self.assertNotIn(token, probe)
        self.assertEqual(probe.count("Marshal.ReadInt32"), 1)

    def test_probe_does_not_touch_the_clipboard_while_locked(self):
        probe = read("ClipboardProbe.cs")
        handler = probe[probe.index("private void OnClipboardUpdate()"):
                        probe.index("private static string Presence(")]
        gate = handler.index("if (locked)")
        returned = handler.index("return;", gate)
        for token in ("IsClipboardFormatAvailable", "OpenClipboard", "GetClipboardData",
                      "Presence(", "ReadPrivacyFlag(", "RequestSyntheticFormat("):
            position = handler.find(token)
            self.assertTrue(position == -1 or position > returned, token)

    def test_blocker_only_opens_and_closes(self):
        blocker = strip_comments_and_strings(read("ClipboardBlocker.cs"))
        self.assertEqual(
            set(re.findall(r"Native\.(\w+)", blocker)),
            {"OpenClipboard", "CloseClipboard"},
        )

    def test_owner_never_reads_clipboard_data(self):
        owner = strip_comments_and_strings(read("SyntheticOwner.cs"))
        for token in ("GetClipboardData", "GlobalSize", "Marshal.Read", "PtrToString"):
            self.assertNotIn(token, owner)

    def test_canary_text_exists_only_in_the_synthetic_owner(self):
        for name in ALL_SOURCES:
            count = read(name).count(CANARY)
            self.assertEqual(count, 1 if name == "SyntheticOwner.cs" else 0, name)

    def test_log_files_are_never_overwritten(self):
        common = read("Common.cs")
        self.assertIn("FileMode.CreateNew", common)
        for mode in ("FileMode.Create,", "FileMode.Append", "FileMode.OpenOrCreate",
                     "FileMode.Truncate"):
            self.assertNotIn(mode, common)

    def test_sources_avoid_syntax_newer_than_the_built_in_compiler(self):
        for name in ALL_SOURCES:
            code = strip_comments_and_strings(read(name))
            for token in ("=>", "?.", "nameof(", "out var", "out _", " is not ",
                          "switch {", "record ", "??="):
                self.assertNotIn(token, code, f"{token} in {name}")
            self.assertNotIn('$"', read(name), name)
            for opening, closing in ("{}", "()", "[]"):
                self.assertEqual(code.count(opening), code.count(closing), name)

    def test_each_tool_has_exactly_one_entry_point(self):
        for name in ("ClipboardProbe.cs", "SyntheticOwner.cs", "ClipboardBlocker.cs"):
            self.assertEqual(read(name).count("static int Main(string[] args)"), 1)
        for name in ("Native.cs", "Common.cs"):
            self.assertNotIn(" Main(", read(name))

    def test_build_script_uses_only_the_built_in_compiler_and_all_sources(self):
        script = (WINDOWS / "build.cmd").read_text(encoding="utf-8")
        for name in ALL_SOURCES:
            self.assertIn("%SRC%\\" + name, script)
        lowered = script.lower()
        for token in ("curl", "powershell", "invoke-webrequest", "http", "nuget",
                      "dotnet ", "runas", "reg add", "schtasks"):
            self.assertNotIn(token, lowered)
        self.assertEqual(script.count("/out:"), 3)

    def test_documents_exist(self):
        for name in ("README.md", "TEST-PROTOCOL.md"):
            self.assertTrue((WINDOWS / name).is_file(), name)

    def test_unique_canary_option_and_generation(self):
        owner = read("SyntheticOwner.cs")
        self.assertIn("--unique-canary", owner)
        self.assertIn("MakeCanaryId", owner)
        self.assertIn("Guid.NewGuid()", owner)
        self.assertIn("Substring(0, 16)", owner)
        self.assertIn("ToUpperInvariant()", owner)
        self.assertIn('CanaryBase + "-"', owner)
        self.assertEqual(owner.count(CANARY), 1)

    def test_unique_canary_id_is_emitted_by_owner_only(self):
        owner = read("SyntheticOwner.cs")
        self.assertIn('log.Write("canary_id"', owner)
        self.assertIn("text_published=", owner)
        probe = read("ClipboardProbe.cs")
        self.assertNotIn("canary_id", probe)
        self.assertNotIn(CANARY, probe)
        self.assertNotIn("unique-canary", probe)

    def test_unique_canary_preserves_default_behaviour(self):
        owner = read("SyntheticOwner.cs")
        self.assertIn("plan.CanaryId != null ? plan.CanaryId : CanaryText", owner)


if __name__ == "__main__":
    unittest.main()
