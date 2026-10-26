import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_UUID = "copypastebin@kozlowska-anna.github.io"
EXTENSION = ROOT / "gnome-extension" / PUBLIC_UUID
LAUNCHER = ROOT / "packaging" / "copypastebin.desktop"


class GnomeExtensionTests(unittest.TestCase):
    def test_about_links_use_native_browser_activation_and_translated_labels(self):
        import re
        from urllib.parse import urlsplit

        window = (EXTENSION / "about.js").read_text(encoding="utf-8")
        catalog = (EXTENSION / "i18n.js").read_text(encoding="utf-8")
        site = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
        canonical = re.search(r'rel="canonical" href="([^"]+)"', site).group(1)
        for constant, url, english, polish in (
            ("WEBSITE_URL", canonical, "Website", "Strona internetowa"),
            ("LATEST_RELEASE_URL", "https://github.com/kozlowska-anna/CopyPasteBin/releases/latest",
             "Download the latest version", "Pobierz najnowszą wersję"),
            ("ISSUES_URL", "https://github.com/kozlowska-anna/CopyPasteBin/issues",
             "Report an issue", "Zgłoś błąd"),
        ):
            with self.subTest(link=constant):
                self.assertIn(f"const {constant} = '{url}';", window)
                self.assertIn(
                    "new Gtk.LinkButton({\n"
                    f"            label: t('{english}'),\n"
                    f"            uri: {constant},\n"
                    "        })", window,
                )
                self.assertIn(f"['{english}', '{polish}']", catalog)
                self.assertEqual("https", urlsplit(url).scheme)
                self.assertEqual("", urlsplit(url).query)
        self.assertEqual(3, window.count("new Gtk.LinkButton("))
        self.assertIn(
            "Updates are not checked automatically. Open the latest release to download a new version.",
            window,
        )
        self.assertIn(
            "Aktualizacje nie są sprawdzane automatycznie. Otwórz najnowsze wydanie, aby pobrać nową wersję.",
            catalog,
        )
        # Keep GTK's default, user-triggered URI handler; no eager launch or upload.
        for forbidden in ("activate-link", "launch_default_for_uri", "fetch(",
                          "Soup", "Gio.Subprocess"):
            self.assertNotIn(forbidden, window)

    def test_all_backend_clients_use_one_deterministic_resolver(self):
        resolver = (EXTENSION / "backend-path.js").read_text(encoding="utf-8")
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        filters = (EXTENSION / "filter-editor.js").read_text(encoding="utf-8")
        rules = (EXTENSION / "rules-editor.js").read_text(encoding="utf-8")
        recent = (EXTENSION / "recent-clipboard.js").read_text(encoding="utf-8")
        about = (EXTENSION / "about.js").read_text(encoding="utf-8")

        self.assertIn("resolveBackendPath", extension)
        for client in (editor, filters, rules):
            self.assertIn("import {backendCommand} from './backend-path.js'", client)
            self.assertNotIn("venv',\n    'bin',\n    'cpb'", client)
        self.assertIn("backendCommand('ui', 'detections')", editor)
        self.assertIn("backendCommand('ui', 'redact')", editor)
        self.assertIn("backendCommand('ui', 'exclusion-add')", editor)
        self.assertIn("backendCommand('ui', 'rules')", rules)
        self.assertIn("backendCommand('ui', 'rules-save')", rules)
        self.assertIn("backendCommand('ui', ...arguments_)", filters)
        self.assertNotIn("backend-path.js", recent + about)
        self.assertNotIn("Gio.Subprocess", recent + about)
        self.assertIn("SYSTEM_BACKEND_PATH = '/usr/bin/cpb'", resolver)

    def test_metadata_targets_only_confirmed_shell_generation(self):
        metadata = json.loads((EXTENSION / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(PUBLIC_UUID, metadata["uuid"])
        self.assertEqual(["50"], metadata["shell-version"])
        self.assertNotIn("session-modes", metadata)

    def test_event_backend_uses_meta_without_polling_or_input_hooks(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        for forbidden in (
            "wl-paste",
            "shell=True",
            "/bin/sh",
            "eval(",
            "key-press",
            "get_title",
            "get_pid",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("Gio.Subprocess.new", source)
        self.assertIn("Gio.SubprocessFlags.STDERR_SILENCE", source)
        self.assertIn("GObject.registerClass", source)
        self.assertIn("global.display.get_selection()", source)
        self.assertIn("'owner-changed'", source)
        self.assertIn("Meta.SelectionType.SELECTION_CLIPBOARD", source)
        self.assertIn("transfer_async", source)
        self.assertNotIn("set_owner", source)

    def test_safe_paste_uses_one_standard_shortcut_without_auto_paste(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        metadata = json.loads((EXTENSION / "metadata.json").read_text(encoding="utf-8"))
        schema = (
            EXTENSION / "schemas" /
            "org.gnome.shell.extensions.copypastebin.gschema.xml"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            "org.gnome.shell.extensions.copypastebin",
            metadata["settings-schema"],
        )
        self.assertIn("<Super><Shift>v", schema)
        self.assertNotIn("<Super>v", schema.replace("<Super><Shift>v", ""))
        self.assertIn("Main.wm.addKeybinding(", source)
        self.assertIn("Main.wm.removeKeybinding(SAFE_PASTE_KEY)", source)
        self.assertIn("Shell.ActionMode.NORMAL", source)
        self.assertIn("[this._entryPoint, 'ui', 'detections']", source)
        self.assertIn("this._launchEditor(input, true)", source)
        self.assertIn("this._safePasteProcess?.force_exit()", source)
        self.assertIn("arguments_.push('--suggest-redaction')", source)
        self.assertIn("if (SUGGEST_REDACTION)", editor)
        self.assertIn("this._suggestRedaction()", editor)
        self.assertIn("stdout !== ACTIVE", source)
        for forbidden in (
            "Ctrl+V", "<Control>v", "grab_accelerator", "fake_key",
            "notify_keyval", "Clutter.Event", "xdotool", "ydotool",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source + editor + schema)

    def test_pause_gate_precedes_selection_transfer(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        gate = source.index("this._runPause('status'")
        transfer = source.index("this._selection.transfer_async")
        self.assertLess(gate, transfer)
        self.assertIn("if (stdout !== ACTIVE)", source[gate:transfer])
        self.assertIn("this._mode === 'transition'", source)
        self.assertIn("this._mode === 'indefinite'", source)

    def test_locked_or_greeter_session_never_starts_a_transfer(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        lock_gate = source.index("Main.sessionMode.isLocked")
        transfer = source.index("this._selection.transfer_async")
        self.assertLess(lock_gate, transfer)
        self.assertIn("Main.sessionMode.isGreeter", source[lock_gate:transfer])

    def test_content_uses_stdin_and_never_argv_or_environment(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        self.assertIn("[this._entryPoint, 'bridge', 'observe']", source)
        self.assertIn("Gio.SubprocessFlags.STDIN_PIPE", source)
        self.assertIn("new GLib.Bytes(frame)", source)
        self.assertNotIn("setenv", source)

    def test_only_closed_pause_actions_are_exposed(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        for action in ("30m", "1h", "until-resumed", "resume", "status"):
            self.assertIn(f"'{action}'", source)
        self.assertNotIn("15m", source)
        self.assertNotIn("2h", source)

    def test_resume_action_is_visible_only_while_pause_is_active(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        recent = source.index("this._recentClipboardItem = new PopupMenu.PopupMenuItem")
        status = source.index("this._statusItem = new PopupMenu.PopupMenuItem")
        pause_30m = source.index("this._addAction(this._t('Pause for 30 minutes'), '30m')")
        self.assertLess(recent, status)
        self.assertLess(status, pause_30m)
        self.assertIn("this._resumeItem = this._addAction(this._t('Resume now'), 'resume')", source)
        apply_status = source[
            source.index("    _applyStatus(stdout, automaticCheck) {"):
            source.index("    _showError() {", source.index("    _applyStatus"))
        ]
        active = apply_status[apply_status.index("if (stdout === ACTIVE)"):apply_status.index("if (stdout === INDEFINITE)")]
        indefinite = apply_status[apply_status.index("if (stdout === INDEFINITE)"):apply_status.index("const match = TIMED.exec(stdout)")]
        timed = apply_status[apply_status.index("this._mode = 'timed'"):]
        transition = source[source.index("    _run(action, automaticCheck) {"):source.index("    _runPause(action, onSuccess) {")]
        error = source[source.index("    _showError() {"):source.index("    _showEmptyClipboard() {")]
        self.assertIn("this._resumeItem.visible = false", active)
        self.assertIn("this._resumeItem.visible = true", indefinite)
        self.assertIn("this._resumeItem.visible = true", timed)
        self.assertIn("this._resumeItem.visible = false", transition)
        self.assertIn("this._resumeItem.visible = false", error)

    def test_english_category_names_are_consistent_across_the_ui(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        filters = (EXTENSION / "filter-editor.js").read_text(encoding="utf-8")
        i18n = (EXTENSION / "i18n.js").read_text(encoding="utf-8")
        rules = (EXTENSION / "rules-editor.js").read_text(encoding="utf-8")
        self.assertIn("['EMAIL', 'email address']", extension)
        self.assertIn("['EMAIL', 'Email address']", editor)
        self.assertIn("['EMAIL', t('Email address')]", filters)
        self.assertIn("['EMAIL', 'Email address']", rules)
        for ui_source in (editor, rules):
            self.assertIn("['PHONE', 'Phone number']", ui_source)
            self.assertIn("['MONEY_AMOUNT_PLN_USD', 'Currency amount']", ui_source)
            self.assertNotIn("'Fiat amount'", ui_source)
            self.assertNotIn("'Traditional currency amount'", ui_source)
        self.assertIn("['Email address', 'E-mail']", i18n)
        self.assertIn("['email address', 'e-mail']", i18n)
        self.assertIn("['Currency amount', 'Kwota waluty tradycyjnej']", i18n)

    def test_panel_icons_match_brand_states_and_flash_only_the_front_sheet(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        active = (EXTENSION / "icon-active.svg").read_text(encoding="utf-8")
        paused = (EXTENSION / "icon-paused.svg").read_text(encoding="utf-8")
        copying = (EXTENSION / "icon-copying.svg").read_text(encoding="utf-8")
        self.assertIn("this._setProtectionIcon(true)", source)
        self.assertIn("this._setProtectionIcon(false)", source)
        self.assertIn("icon-active.svg", source)
        self.assertIn("icon-paused.svg", source)
        self.assertIn('fill="#102d4b"', active)
        self.assertIn('fill="#0a223b"', active)
        self.assertIn('stroke="#4da9e8"', active)
        self.assertIn('stroke="#73c7fa"', active)
        self.assertIn('fill="#730a1b"', paused)
        self.assertIn('stroke="#e23b52"', paused)
        self.assertIn('stroke="#ff6478"', paused)
        self.assertIn("icon-copying.svg", source)
        self.assertIn('fill="#102d4b"', copying)
        self.assertIn('fill="#eaf6ff"', copying)
        self.assertIn('stroke="#73c7fa"', copying)
        self.assertNotIn('fill="#eaf6ff"', active)
        self.assertNotIn('fill="#eaf6ff"', paused)
        self.assertIn("CLIPBOARD_FLASH_MILLISECONDS = 200", source)
        self.assertIn("this._flashClipboardChange()", source)
        self.assertIn("this._clearClipboardFlash()", source)
        self.assertIn("this._mode === 'active'", source)
        self.assertIn("GLib.timeout_add(", source)
        for forbidden in ("<script", "href=", "url(", "data:", "https:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, active + paused + copying)

    def test_clipboard_change_flash_is_short_gated_and_cleaned_up(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        owner_start = source.index("    _onOwnerChanged(")
        owner_end = source.index("    _sourceApplication()", owner_start)
        owner = source[owner_start:owner_end]
        self.assertIn("if (stdout !== ACTIVE)", owner)
        self.assertNotIn("this._flashClipboardChange()", owner)
        self.assertIn("this._transferText(ownerSequence, sourceApplication)", owner)
        transfer_start = source.index("    _transferText(")
        transfer_end = source.index("    _clipboardDigest(", transfer_start)
        transfer = source[transfer_start:transfer_end]
        self.assertLess(
            transfer.index("digest === this._lastClipboardDigest"),
            transfer.index("this._flashClipboardChange()")
        )
        flash_start = source.index("    _flashClipboardChange()")
        flash_end = source.index("    _clearTimeout()", flash_start)
        flash = source[flash_start:flash_end]
        self.assertIn("this._panelIcon.gicon = this._copyingIcon", flash)
        self.assertIn("return GLib.SOURCE_REMOVE", flash)
        destroy_start = source.index("    destroy()")
        self.assertIn("this._clearClipboardFlash()", source[destroy_start:])

    def test_same_clipboard_content_is_ignored_before_creating_an_event(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        owner_start = source.index("    _onOwnerChanged(")
        owner_end = source.index("    _sourceApplication()", owner_start)
        owner = source[owner_start:owner_end]
        self.assertIn("const ownerSequence = ++this._ownerChangeSequence", owner)
        self.assertNotIn("this._cancelAutoClear()", owner)
        self.assertNotIn("++this._eventSequence", owner)

        transfer_start = source.index("    _transferText(")
        transfer_end = source.index("    _clipboardDigest(", transfer_start)
        transfer = source[transfer_start:transfer_end]
        duplicate = "digest === this._lastClipboardDigest ||\n                        digest === this._pendingClipboardDigest"
        self.assertIn(duplicate, transfer)
        self.assertLess(transfer.index(duplicate), transfer.index("this._cancelAutoClear()"))
        self.assertLess(
            transfer.index("this._cancelAutoClear()"),
            transfer.index("const sequence = ++this._eventSequence")
        )
        self.assertLess(
            transfer.index("const sequence = ++this._eventSequence"),
            transfer.index("this._flashClipboardChange()")
        )
        self.assertIn("this._sendToBridge(sequence, sourceApplication, bytes, digest)", transfer)

    def test_clipboard_identity_is_ram_only_and_cleared_at_session_boundaries(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        self.assertIn("GLib.compute_checksum_for_bytes(", source)
        self.assertIn("GLib.ChecksumType.SHA256", source)
        self.assertIn("this._lastClipboardDigest = null", source)
        self.assertIn("this._pendingClipboardDigest = null", source)
        self.assertNotIn("lastClipboardDigest", source.replace("_lastClipboardDigest", ""))
        session_start = source.index("Main.sessionMode.connect('updated'")
        session_end = source.index("this._menuSignalId", session_start)
        self.assertIn("this._resetClipboardIdentity()", source[session_start:session_end])
        destroy_start = source.index("    destroy()")
        self.assertIn("this._resetClipboardIdentity()", source[destroy_start:])

    def test_own_clipboard_writes_update_identity_and_safe_paste_bypasses_it(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        self.assertIn("this._rememberOwnClipboardText('')", source)
        self.assertIn("this._rememberOwnClipboardText(entry.text)", source)
        self.assertIn("this._rememberOwnClipboardText(edited)", source)
        safe_start = source.index("    safePaste()")
        safe_end = source.index("    _analyzeSafePaste(", safe_start)
        safe_paste = source[safe_start:safe_end]
        self.assertNotIn("_lastClipboardDigest", safe_paste)
        self.assertNotIn("_pendingClipboardDigest", safe_paste)

    def test_recent_clipboard_is_bounded_memory_only_and_session_scoped(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        self.assertIn("MAX_RECENT_CLIPBOARD_ENTRIES = 15", source)
        self.assertIn("MAX_RECENT_CLIPBOARD_ITEM_BYTES = 256 * 1024", source)
        self.assertIn("MAX_RECENT_CLIPBOARD_TOTAL_BYTES = 2 * 1024 * 1024", source)
        self.assertIn("this._rememberRecentClipboard(content)", source)
        self.assertIn("this._recentClipboardState = {entries: [], totalBytes: 0, nextId: 1}", source)
        self.assertIn("clearRecentClipboardState(this._recentClipboardState)", source)
        self.assertNotIn("[this._entryPoint, 'ui', 'history']", source)
        self.assertNotIn("language.json", source)

    def test_recent_clipboard_uses_separate_pipe_only_window(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        window = (EXTENSION / "recent-clipboard.js").read_text(encoding="utf-8")
        catalog = (EXTENSION / "i18n.js").read_text(encoding="utf-8")
        self.assertIn("this._recentClipboardItem.connect('activate'", source)
        self.assertIn("this._recentClipboardPath,", source)
        self.assertIn("Gio.SubprocessFlags.STDIN_PIPE", source)
        self.assertIn("Gio.SubprocessFlags.STDOUT_PIPE", source)
        self.assertIn("new GLib.Bytes(input)", source)
        self.assertIn("MAX_ENTRIES = 15", window)
        self.assertIn("MAX_ITEM_BYTES = 256 * 1024", window)
        self.assertIn("MAX_TOTAL_BYTES = 2 * 1024 * 1024", window)
        self.assertIn("MAX_PROTOCOL_BYTES = MAX_TOTAL_BYTES + 185", window)
        self.assertIn("new GioUnix.InputStream({fd: 0", window)
        self.assertIn("new GioUnix.OutputStream({fd: 1", window)
        self.assertIn("editable: false", window)
        self.assertIn("default_width: 1020", window)
        self.assertIn("default_height: 700", window)
        self.assertIn("content.set_position(320)", window)
        self.assertIn(
            "up to 15 recently copied text items only in temporary memory",
            window,
        )
        self.assertIn(
            "Locking the screen, logging out, or stopping the program clears the list.",
            window,
        )
        self.assertIn("Restore to clipboard", window)
        self.assertIn("Click again: Clear all", window)
        self.assertIn("Clipboard history — {count}/{limit}", source)
        self.assertIn("t('Clipboard history')", window)
        self.assertIn("['Clipboard history', 'Historia schowka']", catalog)
        self.assertNotIn("Ostatnie wpisy schowka", catalog)
        for forbidden in ("write_file", "append_to", "shell=True", "/bin/sh", "http://", "https://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source + window)

    def test_about_window_is_local_bilingual_and_credited(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        window = (EXTENSION / "about.js").read_text(encoding="utf-8")
        translations = (EXTENSION / "i18n.js").read_text(encoding="utf-8")
        metadata = (EXTENSION / "metadata.json").read_text(encoding="utf-8")
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("this._addAboutAction()", source)
        self.assertIn("this._aboutPath", source)
        self.assertIn("this._aboutProcess?.force_exit()", source)
        self.assertIn("About CopyPasteBin", window)
        self.assertIn("detects potentially sensitive data", window)
        self.assertIn("redact text and images", window)
        self.assertIn("Runs locally, with no account, cloud services, or telemetry.", window)
        self.assertIn("wykrywa potencjalnie wrażliwe dane", translations)
        self.assertIn("anonimizować tekst i obrazy", translations)
        self.assertIn("Program działa lokalnie, bez konta, chmury i telemetrii.", translations)
        self.assertIn("Author: Anna Kozłowska", window)
        self.assertIn("License: GPL-3.0-or-later", window)
        self.assertIn("This program comes with no warranty", window)
        self.assertIn("copypastebin-about-icon", window)
        self.assertIn("-gtk-icon-shadow", window)
        self.assertIn("#061827", window)
        self.assertIn("ChatGPT and Codex from OpenAI", window)
        self.assertIn("not an official OpenAI product", window)
        self.assertIn("Autorka: Anna Kozłowska", translations)
        self.assertIn("support from ChatGPT and Codex", metadata)
        self.assertIn('authors = [{name = "Anna Kozłowska"}]', project)
        self.assertIn('license = {text = "GPL-3.0-or-later"}', project)
        for forbidden in ("http://", "Gio.File", "Gio.Subprocess"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, window)

    def test_filter_settings_use_a_separate_bounded_checkbox_window(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "filter-editor.js").read_text(encoding="utf-8")
        self.assertIn("Detection filters — loading…", source)
        self.assertIn("Detection filters — {enabled}/{total}", source)
        self.assertIn("this._filtersItem.connect('activate'", source)
        self.assertIn("this._filterEditorPath, `--language=${this._language}`", source)
        self.assertIn("this._filterEditorProcess?.force_exit()", source)
        self.assertNotIn("this._filtersMenu", source)
        self.assertIn("[this._entryPoint, 'ui', ...arguments_]", source)
        self.assertIn("payload.filters.length !== expected.length", source)
        self.assertIn("this._refreshFilters()", source)
        self.assertIn("this._filterSequence++", source)
        self.assertIn("this._matchSubmenuBackgrounds()", source)
        self.assertIn("this.menu.actor.get_theme_node().get_background_color()", source)
        self.assertIn("FILTERS = new Map", editor)
        self.assertIn("Gtk.CheckButton", editor)
        self.assertIn("backendCommand('ui', ...arguments_)", editor)
        self.assertIn("['filter-set', category, enabled ? 'on' : 'off']", editor)
        self.assertIn("payload.filters.length !== expected.length", editor)
        self.assertIn("Changes are saved immediately", editor)
        for forbidden in ("shell=True", "/bin/sh", "eval(", "http://", "https://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source + editor)

    def test_filter_and_rules_save_lock_input_without_fading_all_controls(self):
        filters = (EXTENSION / "filter-editor.js").read_text(encoding="utf-8")
        rules = (EXTENSION / "rules-editor.js").read_text(encoding="utf-8")

        self.assertNotIn("_setBusy", filters + rules)
        self.assertIn("this._setSaving(true)", filters)
        self.assertIn("check.sensitive = this._available", filters)
        self.assertIn("check.can_target = interactive", filters)
        self.assertIn("check.focusable = interactive", filters)
        self.assertIn("if (check.active !== active)", filters)

        self.assertIn("this._setSaving(true)", rules)
        self.assertIn("row._enabled.sensitive = this._available", rules)
        self.assertIn("control.can_target = interactive", rules)
        self.assertIn("control.focusable = interactive", rules)
        self.assertIn("this._setAvailable(false)", rules)
        self.assertIn("this._setSaving(false)", rules)

    def test_nested_settings_menus_share_the_main_menu_background(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        start = source.index("    _matchSubmenuBackgrounds()")
        end = source.index("    _openFilterEditor()", start)
        styling = source[start:end]
        self.assertIn("this.menu.actor.get_theme_node().get_background_color()", styling)
        self.assertIn("[this._autoClearMenu, this._languageMenu]", styling)
        self.assertIn("submenu.menu.actor.set_style(style)", styling)
        self.assertNotIn("_matchFiltersBackground", source)

    def test_empty_text_is_visible_blue_information_not_protection_error(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        start = source.index("    _showEmptyClipboard() {")
        end = source.index("_setProtectionIcon(active)", start)
        empty = source[start:end]
        self.assertIn("'info'", empty)
        self.assertIn("CopyPasteBin: empty clipboard", empty)
        self.assertIn("The clipboard contains no text to analyze.", empty)
        self.assertNotIn("'error'", empty)
        transfer = source.index("if (bytes.length === 0)")
        bridge = source.index(
            "this._sendToBridge(sequence, sourceApplication, bytes, digest)", transfer
        )
        self.assertIn("this._showEmptyClipboard()", source[transfer:bridge])
        self.assertIn("if (bytes.length > MAX_INPUT_BYTES)", source[transfer:bridge])

    def test_custom_rules_editor_is_explicit_bounded_and_local(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "rules-editor.js").read_text(encoding="utf-8")
        self.assertIn("Custom rules and exceptions", extension)
        self.assertNotIn("Custom rules and exceptions…", extension)
        self.assertIn("'/usr/bin/gjs', '-m', this._rulesEditorPath", extension)
        self.assertIn("`--language=${this._language}`", extension)
        self.assertIn("this._rulesProcess?.force_exit()", extension)
        self.assertIn("MAX_RULES = 32", editor)
        self.assertIn("MAX_EXCLUSIONS = 32", editor)
        self.assertIn("backendCommand('ui', 'rules')", editor)
        self.assertIn("backendCommand('ui', 'rules-save')", editor)
        self.assertIn("Gio.SubprocessFlags.STDIN_PIPE", editor)
        self.assertIn("Do not enter a real password", editor)
        self.assertIn("Add an exception", editor)
        self.assertIn("Custom rules", editor)
        self.assertIn("Exceptions", editor)
        self.assertIn("Active ({count})", editor)
        self.assertIn("Inactive ({count})", editor)
        self.assertIn("_moveRowToStateSection(row)", editor)
        self.assertIn("Matching is case-sensitive", editor)
        self.assertIn("Do not add real sensitive data as an exception", editor)
        self.assertIn("Gtk.CheckButton", editor)
        self.assertNotIn("label: 'aktywna'", editor)
        self.assertIn("const enabled = row._enabled.active", editor)
        self.assertIn("rules.push({literal, risk, enabled})", editor)
        self.assertIn("exclusions.push({literal, category, enabled})", editor)
        self.assertIn("EXCLUDABLE_CATEGORIES", editor)
        self.assertIn("row._category.get_active_id()", editor)
        for forbidden in ("shell=True", "/bin/sh", "eval(", "http://", "https://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, extension + editor)

    def test_editor_is_explicit_pipe_only_and_skips_self_event(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        self.assertIn("Edit / anonymize clipboard", extension)
        self.assertNotIn("Edit / anonymize clipboard…", extension)
        self.assertIn("Gio.SubprocessFlags.STDIN_PIPE", extension)
        self.assertIn("Gio.SubprocessFlags.STDOUT_PIPE", extension)
        self.assertIn("this._clipboard.set_text", extension)
        self.assertIn("EDITOR_APPLICATION_ID", extension)
        self.assertIn("this._applyEditedClipboard(edited, false)", extension)
        self.assertIn("The change was not applied because pause is active.", extension)
        self.assertIn("this._ignoreOwnerTimeoutId", extension)
        self.assertIn("backendCommand('ui', 'redact')", editor)
        self.assertIn("Anonymize detected data", editor)
        self.assertIn("Replace clipboard", editor)
        for forbidden in ("wl-paste", "wl-copy", "setenv", "shell=True"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, extension + editor)

    def test_editor_lifecycle_clears_stale_process_and_reopens_after_failures(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        self.assertIn("_clearEditorProcess(source)", extension)
        self.assertIn("_clearEditorProcess(process)", extension)
        self.assertIn("this._editorProcess.send_signal(10)", extension)
        self.assertIn("this._window = window", editor)
        self.assertIn("this._window = null", editor)
        self.assertIn("GLibUnix.signal_add", editor)
        self.assertIn("this._window.present()", editor)
        self.assertIn("this._window.grab_focus()", editor)
        self.assertIn("if (this._window === null)", editor)

    def test_editor_lifecycle_errors_never_leak_clipboard_text(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        start = extension.index("    _launchEditor(input, suggestRedaction = false) {")
        end = extension.index("    _applyEditedClipboard", start)
        lifecycle = extension[start:end]
        self.assertIn("The editor could not be opened.", lifecycle)
        self.assertIn("The clipboard edit was not applied.", lifecycle)
        self.assertNotIn("${input}", lifecycle)
        self.assertNotIn("${edited}", lifecycle)
        self.assertNotIn("${stdout}", lifecycle)

    def test_editor_text_tools_are_on_demand_and_undoable(self):
        extension = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        for label in (
            "Quick text tools",
            "Remove formatting",
            "Remove extra spaces",
            "Tidy line breaks",
            "Join lines",
            "lowercase",
            "UPPERCASE",
            "Sentence case",
            "Remove blank lines",
            "Find",
            "Replace with",
            "Replace all",
            "Undo last change",
            "Clear clipboard",
            "Confirm clearing",
        ):
            with self.subTest(label=label):
                self.assertIn(label, editor)
        self.assertIn("enable_undo: false", editor)
        self.assertIn("this._buffer.set_enable_undo(true)", editor)
        self.assertIn("this._buffer.undo()", editor)
        self.assertIn("icon_name: 'edit-undo-symbolic'", editor)
        self.assertIn("new Gtk.Label({label: t('Undo last change')})", editor)
        self.assertIn("this._buffer.begin_user_action()", editor)
        self.assertIn("this._buffer.delete(start, end)", editor)
        self.assertIn("this._buffer.insert(start, changed, -1)", editor)
        self.assertIn("this._buffer.end_user_action()", editor)
        self.assertIn("actions.append(this._undo)", editor)
        self.assertNotIn("toolButtons.insert(this._undo", editor)
        self.assertNotIn("collapseSpaces", extension)
        self.assertNotIn("tidyLineBreaks", extension)
        self.assertNotIn("joinLines", extension)
        self.assertIn("bytes.length === 1 && bytes[0] === 0", extension)
        self.assertIn("this._applyEditedClipboard('', true)", extension)
        self.assertIn("new Uint8Array([0])", editor)

    def test_auto_clear_is_optional_persistent_and_cancels_on_new_events(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        for label in (
            "Do not clear automatically",
            "After 1 minute",
            "After 5 minutes",
            "After 15 minutes",
        ):
            self.assertIn(label, source)
        self.assertIn("['auto-clear-set', String(seconds)]", source)
        self.assertIn("this._scheduleAutoClear(sequence)", source)
        self.assertIn("sequence !== this._eventSequence", source)
        self.assertIn("this._cancelAutoClear();", source)
        self.assertIn("this._runPause('status', stdout =>", source)
        self.assertIn("this._clipboard.set_text(St.ClipboardType.CLIPBOARD, '')", source)

    def test_editor_highlights_detection_positions_without_receiving_content_back(self):
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        self.assertIn("Highlight detected data", editor)
        self.assertIn("backendCommand('ui', 'detections')", editor)
        self.assertIn("payload.detections.length > MAX_DETECTIONS", editor)
        self.assertIn("this._buffer.apply_tag(", editor)
        self.assertIn("background: '#f6d365'", editor)
        self.assertIn("background: '#ff8a8a'", editor)
        self.assertIn("new Gtk.TextTag", editor)
        self.assertIn("this._buffer.get_tag_table().add(this._mediumTag)", editor)
        self.assertIn("this._buffer.get_tag_table().add(this._criticalTag)", editor)
        self.assertNotIn("this._buffer.create_tag", editor)

    def test_editor_can_redact_only_selected_text_as_one_undoable_change(self):
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        self.assertIn("default_width: 1060", editor)
        self.assertIn("default_height: 580", editor)
        self.assertIn("Anonymize selection", editor)
        self.assertIn("this._buffer.get_selection_bounds()", editor)
        self.assertIn("this._selectionCandidateAt(x, y)", editor)
        self.assertIn("this._exclusionCandidateForSelection(start.selection)", editor)
        self.assertIn("this._selectionCandidateIsCurrent(candidate)", editor)
        self.assertIn("this._requestRedaction(candidate.text, redacted =>", editor)
        self.assertIn("this._buffer.delete(selectionStart, selectionEnd)", editor)
        self.assertIn("this._buffer.insert(insertion, redacted, -1)", editor)
        self.assertIn("Only the selected fragment was anonymized.", editor)
        self.assertEqual(editor.count("layout.append(actions)"), 1)

        actions_start = editor.index("        const actions = new Gtk.Box({")
        actions_end = editor.index("        layout.append(actions)", actions_start)
        actions = editor[actions_start:actions_end]
        self.assertIn("Anonymize detected data", actions)
        self.assertNotIn("Anonymize selection", actions)

        popover_start = editor.index("    _showSelectionPopover(")
        popover_end = editor.index("    _closeSelectionPopover()", popover_start)
        popover = editor[popover_start:popover_end]
        self.assertIn("new Gtk.Button({label: t('Anonymize selection')})", popover)
        self.assertIn("this._suggestSelectedRedaction(selectionCandidate)", popover)

    def test_editor_clicks_one_visible_exact_low_or_medium_exception(self):
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        self.assertNotIn("Exclude selection", editor)
        self.assertIn("new Gtk.GestureClick", editor)
        self.assertIn("Gtk.PropagationPhase.CAPTURE", editor)
        self.assertIn("CLICK_MOVE_TOLERANCE = 6", editor)
        self.assertIn("window_to_buffer_coords", editor)
        self.assertIn("get_iter_at_position", editor)
        self.assertNotIn("if (trailing > 0)", editor)
        self.assertIn("offset >= item.start && offset < item.end", editor)
        self.assertIn("this._buffer.select_range(start, end)", editor)
        self.assertIn("new Gtk.Popover", editor)
        self.assertIn("Exclude this detection", editor)
        self.assertIn("if (exclusionCandidate !== null)", editor)
        self.assertIn("new Gtk.MessageDialog", editor)
        self.assertIn("Add this detection to exceptions?", editor)
        self.assertIn("Add exception", editor)
        self.assertIn("Gtk.ResponseType.ACCEPT", editor)
        self.assertIn("add_css_class('destructive-action')", editor)
        self.assertIn("detection.risk !== 'low' && detection.risk !== 'medium'", editor)
        self.assertIn("item.start === selectionCandidate.start", editor)
        self.assertIn("item.end === selectionCandidate.end", editor)
        self.assertIn("backendCommand('ui', 'exclusion-add')", editor)
        self.assertIn("Gio.SubprocessFlags.STDIN_PIPE", editor)
        self.assertIn("literal: candidate.literal", editor)
        self.assertNotIn("`${candidate.literal}", editor)
        self.assertIn("Do not exclude real sensitive data", editor)

    def test_colored_banner_replaces_gnome_notifications_and_is_bounded(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        self.assertNotIn("Main.notify", source)
        self.assertIn("MAX_BRIDGE_RESULT_BYTES = 2048", source)
        self.assertIn("Gio.SubprocessFlags.STDOUT_PIPE", source)
        self.assertIn("this._parseBridgeResult(rendered)", source)
        self.assertIn("payload.categories.length > CATEGORY_LABELS.size", source)
        self.assertIn("Main.layoutManager.addChrome(this._banner", source)
        self.assertIn("Main.layoutManager.removeChrome(this._banner)", source)
        self.assertIn("this._banner = new St.BoxLayout({\n            vertical: false,\n            reactive: false,", source)
        self.assertNotIn("trackFullscreen", source)
        self.assertNotIn("affectsInputRegion", source)
        self.assertIn("Main.sessionMode.isLocked", source)
        self.assertIn("Main.sessionMode.isGreeter", source)
        self.assertIn("Main.sessionMode.connect('updated'", source)
        self.assertIn("Main.sessionMode.disconnect(this._sessionModeSignalId)", source)
        self.assertIn("const BANNER_WIDTH = 400", source)
        self.assertNotIn("BANNER_EXCLUSION_WIDTH", source)
        self.assertIn("import Pango from 'gi://Pango'", source)
        self.assertIn("this._bannerBody.clutter_text.line_wrap = true", source)
        self.assertIn("Pango.WrapMode.WORD_CHAR", source)
        self.assertIn("Pango.EllipsizeMode.NONE", source)
        self.assertIn("this._bannerEditor.visible", source)
        self.assertIn("monitor.width - 2 * BANNER_MARGIN", source)
        self.assertIn("this._banner.set_width(width)", source)
        self.assertIn("this._bannerText.set_width(textWidth)", source)
        self.assertIn("this._bannerText.get_preferred_height(textWidth)", source)
        self.assertIn("this._banner.set_height(bannerHeight)", source)
        self.assertIn("below + bannerHeight <= monitor.y + monitor.height - BANNER_MARGIN", source)
        self.assertIn("iconY - bannerHeight - 8", source)
        self.assertIn("GLib.timeout_add_seconds", source)
        self.assertIn("`CPBin: ${result.risk} risk`", source)
        self.assertIn("this._t('Open editor')", source)
        for color in ("#8a5a00", "#a61b29", "#17663b", "#245f9e"):
            with self.subTest(color=color):
                self.assertIn(color, source)

    def test_banner_uses_only_safe_category_labels_not_clipboard_text(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        start = source.index("_showRiskBanner(result)")
        end = source.index("_positionBanner()", start)
        banner = source[start:end]
        self.assertIn("CATEGORY_LABELS.get(name)", banner)
        self.assertIn("result.categories.map", banner)
        self.assertNotIn("this._bannerExclusionContent", banner)
        self.assertNotIn("TextDecoder", banner)

    def test_risk_banner_has_one_clear_editor_action(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        editor = (EXTENSION / "editor.js").read_text(encoding="utf-8")
        stylesheet = (EXTENSION / "stylesheet.css").read_text(encoding="utf-8")
        self.assertIn("Open editor", source)
        self.assertNotIn("Choose exception", source)
        self.assertNotIn("_bannerExclude", source)
        self.assertEqual(source.count("style_class: 'cpb-banner-action'"), 1)
        self.assertEqual(source.count("y_align: Clutter.ActorAlign.CENTER"), 1)
        self.assertIn(".cpb-banner-action:hover", stylesheet)
        self.assertIn(".cpb-banner-action:focus", stylesheet)
        self.assertIn(".cpb-banner-action:active", stylesheet)
        self.assertNotIn(".cpb-banner-exclude", stylesheet)
        self.assertNotIn("canChooseExclusion", source)
        self.assertIn("this._openEditor();", source)
        self.assertNotIn("_singleExclusionCandidate", source)
        self.assertNotIn("_bannerExclusionContent", source)
        self.assertIn("Exclude this detection", editor)

    def test_quit_is_confirmed_and_launcher_only_enables_event_extension(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        launcher = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("Quit CopyPasteBin", source)
        self.assertIn("Click again: Quit CopyPasteBin", source)
        self.assertIn("[GNOME_EXTENSIONS, 'disable', this._uuid]", source)
        self.assertIn("this._clearQuitResetTimeout()", source)
        self.assertIn(
            f"Exec=/usr/bin/gnome-extensions enable {PUBLIC_UUID}",
            launcher,
        )
        self.assertIn("Terminal=false", launcher)
        for forbidden in ("service start", "watch start", "wl-paste", "sudo", "sh -c"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, launcher)

    def test_language_choice_is_private_closed_and_covers_all_gui_processes(self):
        source = (EXTENSION / "extension.js").read_text(encoding="utf-8")
        catalog = (EXTENSION / "i18n.js").read_text(encoding="utf-8")
        for action in ("language", "language-set"):
            self.assertIn(f"'{action}'", source)
        for choice in ("system", "pl", "en"):
            self.assertIn(f"'{choice}'", source)
        self.assertIn("MAX_LANGUAGE_BYTES = 128", source)
        self.assertIn("payload.version !== 1", source)
        self.assertIn("`--language=${this._language}`", source)
        self.assertIn("languageFromArgs(ARGV)", (
            (EXTENSION / "editor.js").read_text(encoding="utf-8") +
            (EXTENSION / "filter-editor.js").read_text(encoding="utf-8") +
            (EXTENSION / "rules-editor.js").read_text(encoding="utf-8") +
            (EXTENSION / "recent-clipboard.js").read_text(encoding="utf-8")
        ))
        self.assertIn("['Quit CopyPasteBin', 'Wyjdź z CopyPasteBin']", catalog)
        self.assertIn("['Language — {language}', 'Język — {language}']", catalog)


if __name__ == "__main__":
    unittest.main()
