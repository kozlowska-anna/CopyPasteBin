import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {translate} from './i18n.js';

const ACTIVE = 'CopyPasteBin pause: ACTIVE\n';
const INDEFINITE = 'CopyPasteBin pause: PAUSED_INDEFINITE\n';
const TIMED = /^CopyPasteBin pause: PAUSED_TIMED remaining_seconds=([0-9]+)\n$/;
const MAX_STATUS_BYTES = 128;
const MAX_FILTERS_BYTES = 2048;
const MAX_AUTO_CLEAR_BYTES = 128;
const MAX_LANGUAGE_BYTES = 128;
const MAX_BRIDGE_RESULT_BYTES = 2048;
const MAX_DETECTIONS_BYTES = 64 * 1024;
const MAX_DETECTIONS = 1000;
const MAX_INPUT_BYTES = 10 * 1024 * 1024;
const MAX_RECENT_CLIPBOARD_ENTRIES = 15;
const MAX_RECENT_CLIPBOARD_ITEM_BYTES = 256 * 1024;
const MAX_RECENT_CLIPBOARD_TOTAL_BYTES = 2 * 1024 * 1024;
const CLIPBOARD_FLASH_MILLISECONDS = 200;
const BANNER_WIDTH = 400;
const BANNER_MARGIN = 12;
const BANNER_PADDING = 12;
const BANNER_SPACING = 10;
const BANNER_BORDER_WIDTH = 2;
const GNOME_EXTENSIONS = '/usr/bin/gnome-extensions';
const TEXT_MIMES = ['text/plain;charset=utf-8', 'text/plain'];
const APPLICATION_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const RISKS = new Set(['none', 'low', 'medium', 'high', 'critical']);
const EDITOR_APPLICATION_ID = 'io.github.copypastebin.Editor';
const SAFE_PASTE_KEY = 'safe-paste';
const CATEGORY_LABELS = new Map([
    ['EMAIL', 'e-mail'],
    ['PHONE', 'phone number'],
    ['PESEL', 'PESEL'],
    ['IBAN', 'IBAN'],
    ['PAYMENT_CARD', 'payment card'],
    ['RECOVERY_KEY', 'recovery key'],
    ['HOME_PATH', 'home path'],
    ['IP_ADDRESS', 'IP address'],
    ['URL_CREDENTIALS', 'credentials in a URL'],
    ['AUTHORIZATION', 'authorization'],
    ['PRIVATE_KEY', 'private key'],
    ['OPENAI_API_KEY', 'OpenAI API key'],
    ['ANTHROPIC_API_KEY', 'Anthropic API key'],
    ['GOOGLE_API_KEY', 'Google API key'],
    ['GITHUB_TOKEN', 'GitHub token'],
    ['SLACK_TOKEN', 'Slack token'],
    ['STRIPE_KEY', 'Stripe key'],
    ['AWS_ACCESS_KEY', 'AWS access key'],
    ['JWT', 'JWT'],
    ['DATABASE_URL', 'database connection string'],
    ['TOKEN', 'token'],
    ['SECRET_ASSIGNMENT', 'secret'],
    ['POSSIBLE_SEED_PHRASE', 'seed phrase'],
    ['MONEY_AMOUNT_PLN_USD', 'traditional currency amounts'],
    ['CRYPTO_AMOUNT_BTC_XRP', 'cryptocurrency amounts'],
    ['CUSTOM_RULE', 'custom rule'],
]);

function systemLanguage() {
    const languages = GLib.get_language_names();
    return languages.some(name => name.toLowerCase().startsWith('pl')) ? 'pl' : 'en';
}

function clearRecentClipboardState(state) {
    for (const entry of state.entries)
        entry.text = '';
    state.entries.length = 0;
    state.totalBytes = 0;
}

const CopyPasteBinIndicator = GObject.registerClass(
class CopyPasteBinIndicator extends PanelMenu.Button {
    constructor(uuid, entryPoint, editorPath, filterEditorPath, rulesEditorPath,
        recentClipboardPath, aboutPath,
        activeIconPath, pausedIconPath, copyingIconPath, languageStatus,
        recentClipboardState, onLanguageChanged) {
        super(0.0, 'CopyPasteBin');
        this._uuid = uuid;
        this._entryPoint = entryPoint;
        this._editorPath = editorPath;
        this._filterEditorPath = filterEditorPath;
        this._rulesEditorPath = rulesEditorPath;
        this._recentClipboardPath = recentClipboardPath;
        this._aboutPath = aboutPath;
        this._language = languageStatus.effective;
        this._languageChoice = languageStatus.choice;
        this._recentClipboardState = recentClipboardState;
        this._onLanguageChanged = onLanguageChanged;
        this._activeIcon = new Gio.FileIcon({
            file: Gio.File.new_for_path(activeIconPath),
        });
        this._pausedIcon = new Gio.FileIcon({
            file: Gio.File.new_for_path(pausedIconPath),
        });
        this._copyingIcon = new Gio.FileIcon({
            file: Gio.File.new_for_path(copyingIconPath),
        });
        this._timeoutId = 0;
        this._clipboardFlashTimeoutId = 0;
        this._mode = 'unknown';
        this._ownerChangeSequence = 0;
        this._eventSequence = 0;
        this._filterSequence = 0;
        this._autoClearSettingSequence = 0;
        this._languageSequence = 0;
        this._recentClipboardSequence = 0;
        this._safePasteSequence = 0;
        this._transferCancellable = null;
        this._editorProcess = null;
        this._filterEditorProcess = null;
        this._rulesProcess = null;
        this._recentClipboardProcess = null;
        this._aboutProcess = null;
        this._safePasteProcess = null;
        this._ignoreNextOwnerChange = false;
        this._ignoreOwnerTimeoutId = 0;
        this._clipboard = St.Clipboard.get_default();
        this._selection = global.display.get_selection();
        this._selectionSignalId = 0;
        this._sessionModeSignalId = 0;
        this._bannerTimeoutId = 0;
        this._quitResetTimeoutId = 0;
        this._quitArmed = false;
        this._autoClearSeconds = 0;
        this._autoClearTimeoutId = 0;
        this._lastClipboardDigest = null;
        this._pendingClipboardDigest = null;

        this._panelIcon = new St.Icon({
            gicon: this._pausedIcon,
            style_class: 'system-status-icon',
        });
        this.add_child(this._panelIcon);
        this._buildBanner();

        this._statusItem = new PopupMenu.PopupMenuItem(this._t('Status: checking…'), {
            reactive: false,
        });
        this.menu.addMenuItem(this._statusItem);
        this._recentClipboardItem = new PopupMenu.PopupMenuItem('');
        this._recentClipboardItem.connect('activate', () => this._openRecentClipboard());
        this.menu.addMenuItem(this._recentClipboardItem);
        this._updateRecentClipboardLabel();
        this._filterStates = new Map();
        this._filtersItem = new PopupMenu.PopupMenuItem(
            this._t('Detection filters — loading…')
        );
        this._filtersItem.connect('activate', () => this._openFilterEditor());
        this.menu.addMenuItem(this._filtersItem);
        this._rulesItem = new PopupMenu.PopupMenuItem(this._t('Custom rules and exceptions'));
        this._rulesItem.connect('activate', () => this._openRulesEditor());
        this.menu.addMenuItem(this._rulesItem);
        this._buildAutoClearMenu();
        this._buildLanguageMenu();
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addEditorAction();
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addAction(this._t('Pause for 30 minutes'), '30m');
        this._addAction(this._t('Pause for 1 hour'), '1h');
        this._addAction(this._t('Pause until resumed'), 'until-resumed');
        this._addAction(this._t('Resume now'), 'resume');
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addQuitAction();
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addAboutAction();

        this._selectionSignalId = this._selection.connect(
            'owner-changed',
            this._onOwnerChanged.bind(this)
        );
        this._sessionModeSignalId = Main.sessionMode.connect('updated', () => {
            if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter) {
                this._ownerChangeSequence++;
                this._eventSequence++;
                this._transferCancellable?.cancel();
                this._transferCancellable = null;
                this._cancelAutoClear();
                this._resetClipboardIdentity();
                this._hideBanner(true);
                this._safePasteSequence++;
                this._safePasteProcess?.force_exit();
                this._safePasteProcess = null;
            }
        });
        this._menuSignalId = this.menu.connect('open-state-changed', (_menu, open) => {
            if (open) {
                this._updateRecentClipboardLabel();
                this._refreshFilters();
                this._refreshAutoClear();
                this._refreshLanguage();
                this._matchSubmenuBackgrounds();
            }
        });
        this._refresh(false);
        this._refreshAutoClear();
        this._refreshLanguage();
    }

    _t(message, values = {}) {
        return translate(this._language, message, values);
    }

    _addAction(label, action) {
        const item = new PopupMenu.PopupMenuItem(label);
        item.connect('activate', () => this._run(action, false));
        this.menu.addMenuItem(item);
    }

    _buildAutoClearMenu() {
        this._autoClearItems = new Map();
        this._autoClearMenu = new PopupMenu.PopupSubMenuMenuItem(
            this._t('Automatic clearing — loading…')
        );
        const choices = [
            [0, this._t('Do not clear automatically')],
            [60, this._t('After 1 minute')],
            [300, this._t('After 5 minutes')],
            [900, this._t('After 15 minutes')],
        ];
        for (const [seconds, label] of choices) {
            const item = new PopupMenu.PopupMenuItem(label);
            item.connect('activate', () => this._setAutoClear(seconds));
            this._autoClearMenu.menu.addMenuItem(item);
            this._autoClearItems.set(seconds, item);
        }
        this.menu.addMenuItem(this._autoClearMenu);
    }

    _buildLanguageMenu() {
        this._languageItems = new Map();
        this._languageMenu = new PopupMenu.PopupSubMenuMenuItem(
            this._t('Language — {language}', {
                language: this._language === 'pl' ? this._t('Polish') : this._t('English'),
            })
        );
        const choices = [
            ['system', this._t('System language')],
            ['pl', this._t('Polish')],
            ['en', this._t('English')],
        ];
        for (const [choice, label] of choices) {
            const item = new PopupMenu.PopupMenuItem(label);
            item.connect('activate', () => this._setLanguage(choice));
            this._languageMenu.menu.addMenuItem(item);
            this._languageItems.set(choice, item);
        }
        this.menu.addMenuItem(this._languageMenu);
        this._applyLanguageStatus({
            choice: this._languageChoice,
            effective: this._language,
        });
    }

    _refreshLanguage() {
        this._runLanguageCommand(['language']);
    }

    _setLanguage(choice) {
        if (!this._languageItems.has(choice))
            return;
        this._languageMenu.label.text =
            this._t('Language — {language}', {language: this._t('saving…')});
        this._runLanguageCommand(['language-set', choice]);
    }

    _runLanguageCommand(arguments_) {
        const sequence = ++this._languageSequence;
        let process;
        try {
            process = Gio.Subprocess.new(
                [this._entryPoint, 'ui', ...arguments_],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._showLanguageError();
            return;
        }
        process.communicate_utf8_async(null, null, (source, result) => {
            if (sequence !== this._languageSequence)
                return;
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_LANGUAGE_BYTES)
                    throw new Error('closed language failure');
                const status = this._parseLanguage(stdout);
                if (status.choice !== this._languageChoice ||
                    status.effective !== this._language) {
                    this._onLanguageChanged(status);
                    return;
                }
                this._applyLanguageStatus(status);
            } catch (_error) {
                this._showLanguageError();
            }
        });
    }

    _parseLanguage(stdout) {
        const payload = JSON.parse(stdout);
        if (payload === null || typeof payload !== 'object' ||
            Object.keys(payload).sort().join(',') !== 'choice,effective,version' ||
            payload.version !== 1 ||
            !['system', 'pl', 'en'].includes(payload.choice) ||
            !['pl', 'en'].includes(payload.effective))
            throw new Error('closed language failure');
        return {choice: payload.choice, effective: payload.effective};
    }

    _applyLanguageStatus(status) {
        for (const [choice, item] of this._languageItems)
            item.setOrnament(
                choice === status.choice
                    ? PopupMenu.Ornament.CHECK
                    : PopupMenu.Ornament.NONE
            );
        const label = status.effective === 'pl' ? this._t('Polish') : this._t('English');
        this._languageMenu.label.text = this._t('Language — {language}', {language: label});
    }

    _showLanguageError() {
        this._languageMenu.label.text = this._t('Language — {language}', {
            language: this._t('unavailable'),
        });
    }

    _addEditorAction() {
        const item = new PopupMenu.PopupMenuItem(this._t('Edit / anonymize clipboard'));
        item.connect('activate', () => this._openEditor());
        this.menu.addMenuItem(item);
    }

    _addQuitAction() {
        this._quitItem = new PopupMenu.PopupMenuItem(this._t('Quit CopyPasteBin'));
        this._quitItem.connect('activate', () => {
            if (!this._quitArmed) {
                this._quitArmed = true;
                this._quitItem.label.text = this._t('Click again: Quit CopyPasteBin');
                this._showBanner(
                    'warning',
                    this._t('CopyPasteBin: confirm quit'),
                    this._t('Open the menu again and select “Quit” to stop protection.')
                );
                this._quitResetTimeoutId = GLib.timeout_add_seconds(
                    GLib.PRIORITY_DEFAULT,
                    8,
                    () => {
                        this._quitResetTimeoutId = 0;
                        this._resetQuitConfirmation();
                        return GLib.SOURCE_REMOVE;
                    }
                );
                return;
            }
            this._clearQuitResetTimeout();
            try {
                Gio.Subprocess.new(
                    [GNOME_EXTENSIONS, 'disable', this._uuid],
                    Gio.SubprocessFlags.STDOUT_SILENCE |
                        Gio.SubprocessFlags.STDERR_SILENCE
                );
            } catch (_error) {
                this._resetQuitConfirmation();
                this._showBanner(
                    'error',
                    this._t('CopyPasteBin: error'),
                    this._t('CopyPasteBin could not be stopped.')
                );
            }
        });
        this.menu.addMenuItem(this._quitItem);
    }

    _addAboutAction() {
        const item = new PopupMenu.PopupMenuItem(this._t('About CopyPasteBin'));
        item.connect('activate', () => this._openAbout());
        this.menu.addMenuItem(item);
    }

    _openAbout() {
        if (this._aboutProcess !== null) {
            try {
                this._aboutProcess.send_signal(10);
                this._showBanner(
                    'info',
                    'CopyPasteBin',
                    this._t('About CopyPasteBin is already open.')
                );
                return;
            } catch (_error) {
                this._aboutProcess = null;
            }
        }
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        try {
            this._aboutProcess = Gio.Subprocess.new(
                ['/usr/bin/gjs', '-m', this._aboutPath, `--language=${this._language}`],
                Gio.SubprocessFlags.STDOUT_SILENCE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._aboutProcess = null;
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('About CopyPasteBin could not be opened.')
            );
            return;
        }
        this._aboutProcess.wait_async(null, (source, result) => {
            try {
                source.wait_finish(result);
                if (!source.get_successful())
                    throw new Error('closed about failure');
            } catch (_error) {
                this._showBanner(
                    'error',
                    this._t('CopyPasteBin: error'),
                    this._t('About CopyPasteBin closed with an error.')
                );
            } finally {
                if (this._aboutProcess === source)
                    this._aboutProcess = null;
            }
        });
    }

    _resetQuitConfirmation() {
        this._quitArmed = false;
        if (this._quitItem !== undefined)
            this._quitItem.label.text = this._t('Quit CopyPasteBin');
    }

    _clearQuitResetTimeout() {
        if (this._quitResetTimeoutId !== 0) {
            GLib.source_remove(this._quitResetTimeoutId);
            this._quitResetTimeoutId = 0;
        }
    }

    _buildBanner() {
        this._banner = new St.BoxLayout({
            vertical: false,
            reactive: false,
            visible: false,
            opacity: 0,
            width: BANNER_WIDTH,
            style: 'border-radius: 12px; padding: 12px; spacing: 10px;',
        });
        const text = new St.BoxLayout({
            vertical: true,
            x_expand: true,
            style: 'spacing: 4px;',
        });
        this._bannerText = text;
        this._bannerTitle = new St.Label({
            text: 'CopyPasteBin',
            style: 'font-weight: bold; font-size: 1.05em;',
        });
        this._bannerBody = new St.Label({
            text: '',
            x_expand: true,
        });
        this._bannerBody.clutter_text.line_wrap = true;
        this._bannerBody.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
        this._bannerBody.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
        text.add_child(this._bannerTitle);
        text.add_child(this._bannerBody);
        this._banner.add_child(text);

        this._bannerEditor = new St.Button({
            label: this._t('Open editor'),
            can_focus: true,
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'cpb-banner-action',
        });
        this._bannerEditor.connect('clicked', () => {
            this._hideBanner(true);
            this._openEditor();
        });
        this._banner.add_child(this._bannerEditor);
        this._bannerClose = new St.Button({
            label: '×',
            can_focus: true,
            accessible_name: this._t('Close CopyPasteBin notification'),
            style: 'padding: 4px 7px; font-size: 1.2em; font-weight: bold;',
        });
        this._bannerClose.connect('clicked', () => this._hideBanner(true));
        this._banner.add_child(this._bannerClose);
        Main.layoutManager.addChrome(this._banner);
    }

    _showBanner(kind, title, message, allowEditor = false) {
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        this._clearBannerTimeout();
        this._banner.remove_all_transitions();
        const styles = {
            low: 'background-color: #245f9e; color: #ffffff; border: 2px solid #78b7f2;',
            medium: 'background-color: #8a5a00; color: #ffffff; border: 2px solid #f2b84b;',
            warning: 'background-color: #8a5a00; color: #ffffff; border: 2px solid #f2b84b;',
            high: 'background-color: #a61b29; color: #ffffff; border: 2px solid #ff7b86;',
            critical: 'background-color: #67101b; color: #ffffff; border: 2px solid #ff334d;',
            success: 'background-color: #17663b; color: #ffffff; border: 2px solid #63d394;',
            info: 'background-color: #245f9e; color: #ffffff; border: 2px solid #78b7f2;',
            error: 'background-color: #7f1d2a; color: #ffffff; border: 2px solid #ff7b86;',
        };
        this._banner.set_style(
            'border-radius: 12px; padding: 12px; spacing: 10px; ' +
            (styles[kind] ?? styles.info)
        );
        this._bannerTitle.text = title;
        this._bannerBody.text = message;
        this._bannerEditor.label = this._t('Open editor');
        this._bannerEditor.visible = allowEditor;
        this._banner.opacity = 0;
        this._banner.show();
        this._positionBanner();
        this._banner.ease({
            opacity: 255,
            duration: 180,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
        });
        this._bannerTimeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            6,
            () => {
                this._bannerTimeoutId = 0;
                this._hideBanner(false);
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _showRiskBanner(result) {
        const labels = result.categories.map(([name, count]) =>
            count === 1
                ? this._t(CATEGORY_LABELS.get(name))
                : `${this._t(CATEGORY_LABELS.get(name))} ×${count}`
        );
        this._showBanner(
            result.risk,
            this._t(`CPBin: ${result.risk} risk`),
            this._t('Detected: {labels}.', {labels: labels.join(', ')}),
            true
        );
    }

    _positionBanner() {
        const monitor = Main.layoutManager.primaryMonitor;
        const [iconX, iconY] = this.get_transformed_position();
        const [iconWidth, iconHeight] = this.get_transformed_size();
        const width = Math.min(
            BANNER_WIDTH,
            Math.max(1, monitor.width - 2 * BANNER_MARGIN)
        );
        this._banner.set_width(width);
        const sideActors = [this._bannerEditor, this._bannerClose]
            .filter(actor => actor.visible);
        let sideWidth = 0;
        let sideHeight = 0;
        for (const actor of sideActors) {
            const [, actorWidth] = actor.get_preferred_width(-1);
            const [, actorHeight] = actor.get_preferred_height(actorWidth);
            sideWidth += actorWidth;
            sideHeight = Math.max(sideHeight, actorHeight);
        }
        const chrome = 2 * (BANNER_PADDING + BANNER_BORDER_WIDTH);
        const textWidth = Math.max(
            1,
            width - chrome - sideWidth - BANNER_SPACING * sideActors.length
        );
        this._bannerText.set_width(textWidth);
        const [, textHeight] = this._bannerText.get_preferred_height(textWidth);
        const bannerHeight = Math.ceil(Math.max(textHeight, sideHeight) + chrome);
        this._banner.set_height(bannerHeight);
        const x = Math.max(
            monitor.x + BANNER_MARGIN,
            Math.min(
                iconX + iconWidth - width,
                monitor.x + monitor.width - width - BANNER_MARGIN
            )
        );
        const below = iconY + iconHeight + 8;
        const y = below + bannerHeight <= monitor.y + monitor.height - BANNER_MARGIN
            ? below
            : Math.max(monitor.y + BANNER_MARGIN, iconY - bannerHeight - 8);
        this._banner.set_position(Math.round(x), Math.round(y));
    }

    _hideBanner(immediate) {
        this._clearBannerTimeout();
        this._banner.remove_all_transitions();
        if (!this._banner.visible)
            return;
        if (immediate) {
            this._banner.hide();
            this._banner.opacity = 0;
            return;
        }
        this._banner.ease({
            opacity: 0,
            duration: 180,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => this._banner.hide(),
        });
    }

    _clearBannerTimeout() {
        if (this._bannerTimeoutId !== 0) {
            GLib.source_remove(this._bannerTimeoutId);
            this._bannerTimeoutId = 0;
        }
    }

    _run(action, automaticCheck) {
        if (action !== 'status') {
            this._cancelAutoClear();
            this._mode = 'transition';
            this._setProtectionIcon(false);
            this._statusItem.label.text = this._t('Status: changing…');
        }
        this._runPause(action, stdout => this._applyStatus(stdout, automaticCheck));
    }

    _runPause(action, onSuccess) {
        let process;
        try {
            process = Gio.Subprocess.new(
                [this._entryPoint, 'pause', action],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._showError();
            return;
        }
        process.communicate_utf8_async(null, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() || stdout.length > MAX_STATUS_BYTES)
                    throw new Error('closed status failure');
                onSuccess(stdout);
            } catch (_error) {
                this._showError();
            }
        });
    }

    _onOwnerChanged(_selection, selectionType) {
        if (selectionType !== Meta.SelectionType.SELECTION_CLIPBOARD)
            return;
        const ownerSequence = ++this._ownerChangeSequence;
        if (this._ignoreNextOwnerChange) {
            this._ignoreNextOwnerChange = false;
            this._clearIgnoreOwnerTimeout();
            return;
        }
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        if (this._mode === 'transition' || this._mode === 'timed' ||
            this._mode === 'indefinite' || this._mode === 'error')
            return;
        const sourceApplication = this._sourceApplication();
        if (sourceApplication === EDITOR_APPLICATION_ID)
            return;
        this._runPause('status', stdout => {
            if (ownerSequence !== this._ownerChangeSequence)
                return;
            this._applyStatus(stdout, false);
            if (stdout !== ACTIVE)
                return;
            this._transferText(ownerSequence, sourceApplication);
        });
    }

    _sourceApplication() {
        const window = global.display.get_focus_window();
        if (window === null)
            return 'unknown';
        const app = Shell.WindowTracker.get_default().get_window_app(window);
        const candidates = [
            window.get_sandboxed_app_id?.(),
            window.get_gtk_application_id?.(),
            app?.get_id(),
            window.get_wm_class?.(),
        ];
        for (const candidate of candidates) {
            if (typeof candidate === 'string' && APPLICATION_ID.test(candidate))
                return candidate;
        }
        return 'unknown';
    }

    _transferText(ownerSequence, sourceApplication) {
        const mimetypes = this._selection.get_mimetypes(
            Meta.SelectionType.SELECTION_CLIPBOARD
        );
        const mimetype = TEXT_MIMES.find(value => mimetypes?.includes(value));
        if (mimetype === undefined) {
            if (ownerSequence === this._ownerChangeSequence)
                this._acceptNonTextClipboard();
            return;
        }
        this._transferCancellable?.cancel();
        const cancellable = new Gio.Cancellable();
        const output = Gio.MemoryOutputStream.new_resizable();
        this._transferCancellable = cancellable;
        this._selection.transfer_async(
            Meta.SelectionType.SELECTION_CLIPBOARD,
            mimetype,
            MAX_INPUT_BYTES + 1,
            output,
            cancellable,
            (selection, result) => {
                let digest = null;
                let eventAccepted = false;
                if (this._transferCancellable === cancellable)
                    this._transferCancellable = null;
                if (ownerSequence !== this._ownerChangeSequence)
                    return;
                try {
                    if (!selection.transfer_finish(result))
                        throw new Error('closed transfer failure');
                    output.close(null);
                    const bytes = output.steal_as_bytes().get_data();
                    digest = this._clipboardDigest(bytes);
                    if (digest === this._lastClipboardDigest ||
                        digest === this._pendingClipboardDigest)
                        return;
                    this._cancelAutoClear();
                    const sequence = ++this._eventSequence;
                    eventAccepted = true;
                    this._pendingClipboardDigest = digest;
                    this._flashClipboardChange();
                    if (bytes.length === 0) {
                        this._markClipboardProcessed(digest);
                        this._showEmptyClipboard();
                        return;
                    }
                    if (bytes.length > MAX_INPUT_BYTES)
                        throw new Error('closed transfer failure');
                    this._sendToBridge(sequence, sourceApplication, bytes, digest);
                } catch (_error) {
                    if (!cancellable.is_cancelled()) {
                        this._cancelAutoClear();
                        if (!eventAccepted)
                            this._eventSequence++;
                        this._resetClipboardIdentity();
                        this._showError();
                    }
                }
            }
        );
    }

    _clipboardDigest(content) {
        return GLib.compute_checksum_for_bytes(
            GLib.ChecksumType.SHA256,
            new GLib.Bytes(content)
        );
    }

    _markClipboardProcessed(digest) {
        this._lastClipboardDigest = digest;
        if (this._pendingClipboardDigest === digest)
            this._pendingClipboardDigest = null;
    }

    _clearPendingClipboardDigest(digest) {
        if (this._pendingClipboardDigest === digest)
            this._pendingClipboardDigest = null;
    }

    _resetClipboardIdentity() {
        this._lastClipboardDigest = null;
        this._pendingClipboardDigest = null;
    }

    _acceptNonTextClipboard() {
        const digest = 'non-text';
        if (digest === this._lastClipboardDigest ||
            digest === this._pendingClipboardDigest)
            return;
        this._cancelAutoClear();
        this._eventSequence++;
        this._lastClipboardDigest = digest;
        this._pendingClipboardDigest = null;
    }

    _rememberOwnClipboardText(text) {
        this._lastClipboardDigest = this._clipboardDigest(new TextEncoder().encode(text));
        this._pendingClipboardDigest = null;
    }

    _sendToBridge(sequence, sourceApplication, content, digest) {
        const frame = new Uint8Array(4 + sourceApplication.length + content.length);
        const length = sourceApplication.length;
        frame[0] = (length >>> 24) & 0xff;
        frame[1] = (length >>> 16) & 0xff;
        frame[2] = (length >>> 8) & 0xff;
        frame[3] = length & 0xff;
        for (let index = 0; index < length; index++)
            frame[4 + index] = sourceApplication.charCodeAt(index);
        frame.set(content, 4 + length);

        let process;
        try {
            process = Gio.Subprocess.new(
                [this._entryPoint, 'bridge', 'observe'],
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._clearPendingClipboardDigest(digest);
            this._showError();
            return;
        }
        process.communicate_async(new GLib.Bytes(frame), null, (source, result) => {
            if (sequence !== this._eventSequence)
                return;
            try {
                const [, stdout] = source.communicate_finish(result);
                if (!source.get_successful())
                    throw new Error('closed bridge failure');
                const bytes = stdout.get_data();
                if (bytes.length === 0 || bytes.length > MAX_BRIDGE_RESULT_BYTES)
                    throw new Error('closed bridge failure');
                const rendered = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
                const bridgeResult = this._parseBridgeResult(rendered);
                this._markClipboardProcessed(digest);
                this._rememberRecentClipboard(content);
                if (bridgeResult.risk !== 'none') {
                    this._showRiskBanner(bridgeResult);
                    this._scheduleAutoClear(sequence);
                }
            } catch (_error) {
                this._clearPendingClipboardDigest(digest);
                this._showError();
            }
        });
    }

    _parseBridgeResult(rendered) {
        const payload = JSON.parse(rendered);
        if (payload === null || typeof payload !== 'object' ||
            payload.version !== 1 || !RISKS.has(payload.risk) ||
            !Array.isArray(payload.categories) ||
            payload.categories.length > CATEGORY_LABELS.size)
            throw new Error('closed bridge result failure');
        let previous = '';
        const categories = payload.categories.map(item => {
            if (!Array.isArray(item) || item.length !== 2 ||
                typeof item[0] !== 'string' || !CATEGORY_LABELS.has(item[0]) ||
                item[0] <= previous || !Number.isSafeInteger(item[1]) ||
                item[1] <= 0 || item[1] > 1000)
                throw new Error('closed bridge result failure');
            previous = item[0];
            return [item[0], item[1]];
        });
        if (payload.risk === 'none' && categories.length !== 0)
            throw new Error('closed bridge result failure');
        if (payload.risk !== 'none' && categories.length === 0)
            throw new Error('closed bridge result failure');
        return {risk: payload.risk, categories};
    }

    _refreshFilters() {
        this._runFilterCommand(['filters']);
    }

    _refreshAutoClear() {
        this._runAutoClearCommand(['auto-clear']);
    }

    _setAutoClear(seconds) {
        if (!this._autoClearItems.has(seconds))
            return;
        this._autoClearMenu.label.text = this._t('Automatic clearing — saving…');
        this._runAutoClearCommand(['auto-clear-set', String(seconds)]);
    }

    _runAutoClearCommand(arguments_) {
        const sequence = ++this._autoClearSettingSequence;
        let process;
        try {
            process = Gio.Subprocess.new(
                [this._entryPoint, 'ui', ...arguments_],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._showAutoClearError();
            return;
        }
        process.communicate_utf8_async(null, null, (source, result) => {
            if (sequence !== this._autoClearSettingSequence)
                return;
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_AUTO_CLEAR_BYTES)
                    throw new Error('closed auto-clear failure');
                const seconds = this._parseAutoClear(stdout);
                this._applyAutoClear(seconds);
                if (arguments_[0] === 'auto-clear-set')
                    this._showBanner(
                        'success',
                        this._t('CopyPasteBin: automatic clearing'),
                        seconds === 0
                            ? this._t('Automatic clearing has been disabled.')
                            : this._t('A clipboard item with a warning will be cleared after {minutes} min.', {
                                minutes: seconds / 60,
                            })
                    );
            } catch (_error) {
                this._showAutoClearError();
            }
        });
    }

    _parseAutoClear(stdout) {
        const payload = JSON.parse(stdout);
        const choices = new Set([0, 60, 300, 900]);
        if (payload === null || typeof payload !== 'object' ||
            Object.keys(payload).length !== 2 || payload.version !== 1 ||
            !Number.isSafeInteger(payload.seconds) || !choices.has(payload.seconds))
            throw new Error('closed auto-clear failure');
        return payload.seconds;
    }

    _applyAutoClear(seconds) {
        const changed = seconds !== this._autoClearSeconds;
        this._autoClearSeconds = seconds;
        if (changed)
            this._cancelAutoClear();
        for (const [value, item] of this._autoClearItems)
            item.setOrnament(
                value === seconds ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE
            );
        const labels = new Map([
            [0, this._t('off')],
            [60, '1 min'],
            [300, '5 min'],
            [900, '15 min'],
        ]);
        this._autoClearMenu.label.text = this._t('Automatic clearing — {value}', {
            value: labels.get(seconds),
        });
    }

    _showAutoClearError() {
        this._autoClearMenu.label.text = this._t('Automatic clearing — unavailable');
        this._showBanner(
            'error',
            this._t('CopyPasteBin: settings unavailable'),
            this._t('Automatic clearing could not be read or saved.')
        );
    }

    _scheduleAutoClear(sequence) {
        this._cancelAutoClear();
        if (this._autoClearSeconds === 0 || sequence !== this._eventSequence)
            return;
        this._autoClearTimeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            this._autoClearSeconds,
            () => {
                this._autoClearTimeoutId = 0;
                if (sequence !== this._eventSequence)
                    return GLib.SOURCE_REMOVE;
                this._runPause('status', stdout => {
                    this._applyStatus(stdout, false);
                    if (stdout !== ACTIVE || sequence !== this._eventSequence)
                        return;
                    this._eventSequence++;
                    this._armIgnoredOwnerChange();
                    this._rememberOwnClipboardText('');
                    this._clipboard.set_text(St.ClipboardType.CLIPBOARD, '');
                    this._showBanner(
                        'info',
                        this._t('CopyPasteBin: clipboard cleared'),
                        this._t('The selected time for data marked with a warning has elapsed.')
                    );
                });
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _cancelAutoClear() {
        if (this._autoClearTimeoutId !== 0) {
            GLib.source_remove(this._autoClearTimeoutId);
            this._autoClearTimeoutId = 0;
        }
    }

    _runFilterCommand(arguments_) {
        const sequence = ++this._filterSequence;
        let process;
        try {
            process = Gio.Subprocess.new(
                [this._entryPoint, 'ui', ...arguments_],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._showFiltersError();
            return;
        }
        process.communicate_utf8_async(null, null, (source, result) => {
            if (sequence !== this._filterSequence)
                return;
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_FILTERS_BYTES)
                    throw new Error('closed filters failure');
                this._applyFilters(this._parseFilters(stdout));
            } catch (_error) {
                this._showFiltersError();
            }
        });
    }

    _parseFilters(stdout) {
        const payload = JSON.parse(stdout);
        const expected = [...CATEGORY_LABELS.keys()];
        if (payload === null || typeof payload !== 'object' ||
            payload.version !== 1 || !Array.isArray(payload.filters) ||
            payload.filters.length !== expected.length)
            throw new Error('closed filters failure');
        const states = new Map();
        for (let index = 0; index < expected.length; index++) {
            const item = payload.filters[index];
            if (!Array.isArray(item) || item.length !== 2 ||
                item[0] !== expected[index] || typeof item[1] !== 'boolean')
                throw new Error('closed filters failure');
            states.set(item[0], item[1]);
        }
        return states;
    }

    _applyFilters(states) {
        this._filterStates = states;
        const enabledCount = [...states.values()].filter(enabled => enabled).length;
        this._filtersItem.label.text =
            this._t('Detection filters — {enabled}/{total}', {
                enabled: enabledCount, total: CATEGORY_LABELS.size,
            });
    }

    _showFiltersError() {
        this._filtersItem.label.text = this._t('Detection filters — unavailable');
        this._showBanner(
            'error',
            this._t('CopyPasteBin: settings unavailable'),
            this._t('Filters could not be read or saved.')
        );
    }

    _matchSubmenuBackgrounds() {
        const background = this.menu.actor.get_theme_node().get_background_color();
        const style = `background-color: rgba(${background.red}, ${background.green}, ` +
            `${background.blue}, ${background.alpha / 255});`;
        for (const submenu of [this._autoClearMenu, this._languageMenu])
            submenu.menu.actor.set_style(style);
    }

    _openFilterEditor() {
        if (this._filterEditorProcess !== null) {
            this._showBanner(
                'info',
                'CopyPasteBin',
                this._t('Filter settings are already open.')
            );
            return;
        }
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        try {
            this._filterEditorProcess = Gio.Subprocess.new(
                ['/usr/bin/gjs', '-m', this._filterEditorPath, `--language=${this._language}`],
                Gio.SubprocessFlags.STDOUT_SILENCE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._filterEditorProcess = null;
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('Filter settings could not be opened.')
            );
            return;
        }
        this._filterEditorProcess.wait_async(null, (source, result) => {
            try {
                source.wait_finish(result);
                if (!source.get_successful())
                    throw new Error('closed filter editor failure');
            } catch (_error) {
                this._showBanner(
                    'error',
                    this._t('CopyPasteBin: error'),
                    this._t('Filter settings closed with an error.')
                );
            } finally {
                this._filterEditorProcess = null;
                this._refreshFilters();
            }
        });
    }

    _openRulesEditor(suggestedExclusion = null) {
        if (this._rulesProcess !== null) {
            this._showBanner(
                'info',
                'CopyPasteBin',
                this._t('Rule management is already open.')
            );
            return;
        }
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        try {
            const arguments_ = [
                '/usr/bin/gjs', '-m', this._rulesEditorPath,
                `--language=${this._language}`,
            ];
            let flags = Gio.SubprocessFlags.STDOUT_SILENCE |
                Gio.SubprocessFlags.STDERR_SILENCE;
            if (suggestedExclusion !== null) {
                arguments_.push('--suggest-exclusion');
                flags |= Gio.SubprocessFlags.STDIN_PIPE;
            }
            this._rulesProcess = Gio.Subprocess.new(arguments_, flags);
        } catch (_error) {
            this._rulesProcess = null;
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('Rule management could not be opened.')
            );
            return;
        }
        const finish = (source, result) => {
            try {
                if (suggestedExclusion === null)
                    source.wait_finish(result);
                else
                    source.communicate_utf8_finish(result);
                if (!source.get_successful())
                    throw new Error('closed rules editor failure');
            } catch (_error) {
                this._showBanner(
                    'error',
                    this._t('CopyPasteBin: error'),
                    this._t('Rule management closed with an error.')
                );
            } finally {
                this._rulesProcess = null;
            }
        };
        if (suggestedExclusion === null)
            this._rulesProcess.wait_async(null, finish);
        else
            this._rulesProcess.communicate_utf8_async(
                JSON.stringify(suggestedExclusion), null, finish
            );
    }

    _rememberRecentClipboard(content) {
        if (!(content instanceof Uint8Array) || content.length === 0 ||
            content.length > MAX_RECENT_CLIPBOARD_ITEM_BYTES)
            return;
        let text;
        try {
            text = new TextDecoder('utf-8', {fatal: true}).decode(content);
        } catch (_error) {
            return;
        }
        const state = this._recentClipboardState;
        let id = state.nextId;
        while (state.entries.some(entry => entry.id === id))
            id = id === 0xffffffff ? 1 : id + 1;
        state.nextId = id === 0xffffffff ? 1 : id + 1;
        state.entries.unshift({
            id,
            text,
            byteLength: content.length,
            createdAt: Date.now(),
        });
        state.totalBytes += content.length;
        while (state.entries.length > MAX_RECENT_CLIPBOARD_ENTRIES ||
            state.totalBytes > MAX_RECENT_CLIPBOARD_TOTAL_BYTES) {
            const removed = state.entries.pop();
            state.totalBytes -= removed.byteLength;
            removed.text = '';
        }
        this._updateRecentClipboardLabel();
    }

    _updateRecentClipboardLabel() {
        this._recentClipboardItem.label.text = this._t(
            'Recent clipboard — {count}/{limit}', {
                count: this._recentClipboardState.entries.length,
                limit: MAX_RECENT_CLIPBOARD_ENTRIES,
            }
        );
    }

    _recentClipboardInput() {
        const encoded = this._recentClipboardState.entries.map(entry => ({
            entry,
            content: new TextEncoder().encode(entry.text),
        }));
        let size = 5;
        for (const {entry, content} of encoded) {
            if (entry.id < 1 || entry.id > 0xffffffff ||
                content.length !== entry.byteLength ||
                content.length === 0 || content.length > MAX_RECENT_CLIPBOARD_ITEM_BYTES)
                throw new Error('closed recent clipboard failure');
            size += 12 + content.length;
        }
        if (encoded.length === 0 || encoded.length > MAX_RECENT_CLIPBOARD_ENTRIES ||
            size > MAX_RECENT_CLIPBOARD_TOTAL_BYTES + 101)
            throw new Error('closed recent clipboard failure');
        const payload = new Uint8Array(size);
        payload.set([0x43, 0x50, 0x42, 0x31], 0);
        payload[4] = encoded.length;
        let offset = 5;
        const writeUint32 = value => {
            payload[offset++] = (value >>> 24) & 0xff;
            payload[offset++] = (value >>> 16) & 0xff;
            payload[offset++] = (value >>> 8) & 0xff;
            payload[offset++] = value & 0xff;
        };
        for (const {entry, content} of encoded) {
            writeUint32(entry.id);
            writeUint32(Math.floor(entry.createdAt / 1000));
            writeUint32(content.length);
            payload.set(content, offset);
            offset += content.length;
        }
        return payload;
    }

    _openRecentClipboard() {
        if (this._recentClipboardProcess !== null) {
            try {
                this._recentClipboardProcess.send_signal(10);
                this._showBanner(
                    'info',
                    'CopyPasteBin',
                    this._t('The recent clipboard window is already open and has been restored.')
                );
                return;
            } catch (_error) {
                this._recentClipboardProcess = null;
            }
        }
        if (this._recentClipboardState.entries.length === 0) {
            this._showBanner(
                'info',
                'CopyPasteBin',
                this._t('No recent clipboard items.')
            );
            return;
        }
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        this._runPause('status', stdout => {
            this._applyStatus(stdout, false);
            if (stdout !== ACTIVE) {
                this._showBanner(
                    'warning',
                    this._t('CopyPasteBin: pause active'),
                    this._t('Resume protection before opening the recent clipboard.')
                );
                return;
            }
            this._launchRecentClipboard();
        });
    }

    _launchRecentClipboard() {
        const sequence = ++this._recentClipboardSequence;
        let input;
        let process;
        try {
            input = this._recentClipboardInput();
            process = Gio.Subprocess.new(
                ['/usr/bin/gjs', '-m', this._recentClipboardPath,
                    `--language=${this._language}`],
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
            this._recentClipboardProcess = process;
        } catch (_error) {
            this._recentClipboardProcess = null;
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('The recent clipboard could not be opened.')
            );
            return;
        }
        try {
            process.communicate_async(new GLib.Bytes(input), null, (source, result) => {
                if (sequence !== this._recentClipboardSequence)
                    return;
                try {
                    const [, stdout] = source.communicate_finish(result);
                    const bytes = stdout.get_data();
                    if (!source.get_successful() ||
                        (bytes.length !== 0 && bytes.length !== 5))
                        throw new Error('closed recent clipboard failure');
                    if (bytes.length === 0)
                        return;
                    const id = (((bytes[1] << 24) >>> 0) |
                        (bytes[2] << 16) | (bytes[3] << 8) | bytes[4]) >>> 0;
                    if (bytes[0] === 1) {
                        const entry = this._recentClipboardState.entries.find(
                            candidate => candidate.id === id
                        );
                        if (entry === undefined) {
                            this._showBanner(
                                'info',
                                'CopyPasteBin',
                                this._t('The selected recent item is no longer available.')
                            );
                            return;
                        }
                        this._restoreRecentClipboard(entry);
                        return;
                    }
                    if (bytes[0] === 2 && id === 0) {
                        this._clearRecentClipboard();
                        return;
                    }
                    throw new Error('closed recent clipboard failure');
                } catch (_error) {
                    this._showBanner(
                        'error',
                        this._t('CopyPasteBin: error'),
                        this._t('The recent clipboard action was not applied.')
                    );
                } finally {
                    if (this._recentClipboardProcess === source)
                        this._recentClipboardProcess = null;
                }
            });
        } catch (_error) {
            process.force_exit();
            this._recentClipboardProcess = null;
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('The recent clipboard could not be opened.')
            );
        }
    }

    _restoreRecentClipboard(entry) {
        if (!this._recentClipboardState.entries.includes(entry) ||
            Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        this._runPause('status', stdout => {
            this._applyStatus(stdout, false);
            if (stdout !== ACTIVE ||
                !this._recentClipboardState.entries.includes(entry) ||
                Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
                return;
            this._cancelAutoClear();
            this._eventSequence++;
            this._armIgnoredOwnerChange();
            this._rememberOwnClipboardText(entry.text);
            this._clipboard.set_text(St.ClipboardType.CLIPBOARD, entry.text);
            const entries = this._recentClipboardState.entries;
            entries.splice(entries.indexOf(entry), 1);
            entry.createdAt = Date.now();
            entries.unshift(entry);
            this._updateRecentClipboardLabel();
            this._showBanner(
                'success',
                'CopyPasteBin',
                this._t('The selected recent item was restored to the clipboard.')
            );
        });
    }

    _clearRecentClipboard() {
        clearRecentClipboardState(this._recentClipboardState);
        this._updateRecentClipboardLabel();
        this._showBanner(
            'success',
            'CopyPasteBin',
            this._t('Recent clipboard items were cleared from memory.')
        );
    }

    _openEditor() {
        this._cancelAutoClear();
        if (this._editorProcess !== null) {
            try {
                // The editor owns the GTK window. Ask it to present/focus it.
                this._editorProcess.send_signal(10);
                this._showBanner(
                    'info',
                    'CopyPasteBin',
                    this._t('The clipboard editor is already open and has been restored.')
                );
                return;
            } catch (_error) {
                this._editorProcess = null;
            }
        }
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        this._runPause('status', stdout => {
            this._applyStatus(stdout, false);
            if (stdout !== ACTIVE) {
                this._showBanner(
                    'warning',
                    this._t('CopyPasteBin: pause active'),
                    this._t('Resume protection before opening the editor.')
                );
                return;
            }
            this._clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clipboard, text) => {
                try {
                    if (typeof text !== 'string' || text.includes('\0'))
                        throw new Error('closed clipboard failure');
                    if (text.length === 0) {
                        this._showEmptyClipboard();
                        return;
                    }
                    const input = new TextEncoder().encode(text);
                    if (input.length > MAX_INPUT_BYTES)
                        throw new Error('closed clipboard failure');
                    this._launchEditor(input);
                } catch (_error) {
                    this._showBanner(
                        'error',
                        this._t('CopyPasteBin: no text'),
                        this._t('The current clipboard does not contain supported text.')
                    );
                }
            });
        });
    }

    safePaste() {
        this._cancelAutoClear();
        if (Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        if (this._editorProcess !== null) {
            this._showBanner(
                'info',
                'CopyPasteBin',
                this._t('The clipboard editor is already open.')
            );
            return;
        }
        const sequence = ++this._safePasteSequence;
        this._safePasteProcess?.force_exit();
        this._safePasteProcess = null;
        this._runPause('status', stdout => {
            this._applyStatus(stdout, false);
            if (sequence !== this._safePasteSequence)
                return;
            if (stdout !== ACTIVE) {
                this._showBanner(
                    'warning',
                    this._t('CopyPasteBin: pause active'),
                    this._t('Resume protection before using Safe Paste.')
                );
                return;
            }
            this._clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clipboard, text) => {
                if (sequence !== this._safePasteSequence ||
                    Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
                    return;
                try {
                    if (typeof text !== 'string' || text.includes('\0'))
                        throw new Error('closed safe paste failure');
                    if (text.length === 0) {
                        this._showEmptyClipboard();
                        return;
                    }
                    const input = new TextEncoder().encode(text);
                    if (input.length > MAX_INPUT_BYTES)
                        throw new Error('closed safe paste failure');
                    this._analyzeSafePaste(sequence, input, Array.from(text).length);
                } catch (_error) {
                    this._showBanner(
                        'error',
                        this._t('CopyPasteBin: Safe Paste failed'),
                        this._t('The clipboard could not be checked safely.')
                    );
                }
            });
        });
    }

    _analyzeSafePaste(sequence, input, textLength) {
        let process;
        try {
            process = Gio.Subprocess.new(
                [this._entryPoint, 'ui', 'detections'],
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
            this._safePasteProcess = process;
        } catch (_error) {
            this._showSafePasteError();
            return;
        }
        process.communicate_async(new GLib.Bytes(input), null, (source, result) => {
            if (this._safePasteProcess === source)
                this._safePasteProcess = null;
            if (sequence !== this._safePasteSequence)
                return;
            try {
                const [, stdout] = source.communicate_finish(result);
                const bytes = stdout.get_data();
                if (!source.get_successful() || bytes.length === 0 ||
                    bytes.length > MAX_DETECTIONS_BYTES)
                    throw new Error('closed safe paste failure');
                const rendered = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
                const risk = this._safePasteRisk(rendered, textLength);
                this._finishSafePaste(sequence, input, risk);
            } catch (_error) {
                this._showSafePasteError();
            }
        });
    }

    _safePasteRisk(rendered, textLength) {
        const payload = JSON.parse(rendered);
        if (payload === null || typeof payload !== 'object' ||
            Object.keys(payload).sort().join(',') !== 'detections,version' ||
            payload.version !== 1 || !Array.isArray(payload.detections) ||
            payload.detections.length > MAX_DETECTIONS)
            throw new Error('closed safe paste failure');
        const priorities = new Map([
            ['none', 0], ['low', 1], ['medium', 2], ['high', 3], ['critical', 4],
        ]);
        let highest = 'none';
        for (const item of payload.detections) {
            if (item === null || typeof item !== 'object' ||
                Object.keys(item).sort().join(',') !== 'category,end,risk,start' ||
                !Number.isSafeInteger(item.start) || !Number.isSafeInteger(item.end) ||
                item.start < 0 || item.end <= item.start || item.end > textLength ||
                typeof item.category !== 'string' || !CATEGORY_LABELS.has(item.category) ||
                !priorities.has(item.risk))
                throw new Error('closed safe paste failure');
            if (priorities.get(item.risk) > priorities.get(highest))
                highest = item.risk;
        }
        return highest;
    }

    _finishSafePaste(sequence, input, risk) {
        this._runPause('status', stdout => {
            this._applyStatus(stdout, false);
            if (sequence !== this._safePasteSequence || stdout !== ACTIVE ||
                Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
                return;
            if (risk === 'none') {
                this._showBanner(
                    'success',
                    this._t('CopyPasteBin: Safe Paste'),
                    this._t('No known sensitive pattern was detected. The clipboard was not changed.')
                );
                return;
            }
            this._showBanner(
                risk,
                this._t(`CPBin: ${risk} risk`),
                risk === 'high' || risk === 'critical'
                    ? this._t('High-risk data was detected. Review the redacted proposal before replacing the clipboard.')
                    : this._t('Sensitive data was detected. Review the redacted proposal before replacing the clipboard.')
            );
            this._launchEditor(input, true);
        });
    }

    _showSafePasteError() {
        this._showBanner(
            'error',
            this._t('CopyPasteBin: Safe Paste failed'),
            this._t('The clipboard could not be checked safely.')
        );
    }

    _launchEditor(input, suggestRedaction = false) {
        let process;
        try {
            const arguments_ = [
                '/usr/bin/gjs', '-m', this._editorPath,
                `--language=${this._language}`,
            ];
            if (suggestRedaction)
                arguments_.push('--suggest-redaction');
            process = Gio.Subprocess.new(
                arguments_,
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
            this._editorProcess = process;
        } catch (_error) {
            this._editorProcess = null;
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('The editor could not be opened.')
            );
            return;
        }
        try {
            process.communicate_async(
                new GLib.Bytes(input),
                null,
                (source, result) => {
                    try {
                        const [, stdout] = source.communicate_finish(result);
                        const bytes = stdout.get_data();
                        if (!source.get_successful())
                            throw new Error('closed editor failure');
                        if (bytes.length === 0)
                            return;
                        if (bytes.length > MAX_INPUT_BYTES)
                            throw new Error('closed editor failure');
                        if (bytes.length === 1 && bytes[0] === 0) {
                            this._applyEditedClipboard('', true);
                            return;
                        }
                        const edited = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
                        if (edited.length === 0 || edited.includes('\0'))
                            throw new Error('closed editor failure');
                        this._applyEditedClipboard(edited, false);
                    } catch (_error) {
                        this._showBanner(
                            'error',
                            this._t('CopyPasteBin: error'),
                            this._t('The clipboard edit was not applied.')
                        );
                    } finally {
                        this._clearEditorProcess(source);
                    }
                }
            );
        } catch (_error) {
            this._clearEditorProcess(process);
            this._showBanner(
                'error',
                this._t('CopyPasteBin: error'),
                this._t('The editor could not be opened.')
            );
        }
    }

    _clearEditorProcess(process) {
        if (this._editorProcess === process)
            this._editorProcess = null;
    }

    _applyEditedClipboard(edited, cleared) {
        this._cancelAutoClear();
        this._runPause('status', stdout => {
            this._applyStatus(stdout, false);
            if (stdout !== ACTIVE) {
                this._showBanner(
                    'warning',
                    this._t('CopyPasteBin: pause active'),
                    this._t('The change was not applied because pause is active.')
                );
                return;
            }
            this._eventSequence++;
            this._armIgnoredOwnerChange();
            this._rememberOwnClipboardText(edited);
            this._clipboard.set_text(St.ClipboardType.CLIPBOARD, edited);
            this._showBanner(
                'success',
                'CopyPasteBin',
                cleared
                    ? this._t('The clipboard was cleared after your confirmation.')
                    : this._t('The clipboard was replaced after your confirmation.')
            );
        });
    }

    _clearIgnoreOwnerTimeout() {
        if (this._ignoreOwnerTimeoutId !== 0) {
            GLib.source_remove(this._ignoreOwnerTimeoutId);
            this._ignoreOwnerTimeoutId = 0;
        }
    }

    _armIgnoredOwnerChange() {
        this._ignoreNextOwnerChange = true;
        this._clearIgnoreOwnerTimeout();
        this._ignoreOwnerTimeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            1,
            () => {
                this._ignoreOwnerTimeoutId = 0;
                this._ignoreNextOwnerChange = false;
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _refresh(automaticCheck) {
        this._run('status', automaticCheck);
    }

    _applyStatus(stdout, automaticCheck) {
        const previousMode = this._mode;
        this._clearTimeout();
        if (stdout === ACTIVE) {
            this._mode = 'active';
            this._setProtectionIcon(true);
            this._statusItem.label.text = this._t('Status: active');
            if (automaticCheck && previousMode === 'timed')
                this._showBanner(
                    'success',
                    'CopyPasteBin',
                    this._t('Clipboard protection has resumed.')
                );
            return;
        }
        if (stdout === INDEFINITE) {
            this._mode = 'indefinite';
            this._setProtectionIcon(false);
            this._statusItem.label.text = this._t('Status: paused until resumed');
            return;
        }
        const match = TIMED.exec(stdout);
        if (match === null) {
            this._showError();
            return;
        }
        const remaining = Number.parseInt(match[1], 10);
        if (!Number.isSafeInteger(remaining) || remaining <= 0 || remaining > 3600) {
            this._showError();
            return;
        }
        this._mode = 'timed';
        this._setProtectionIcon(false);
        const minutes = Math.max(1, Math.ceil(remaining / 60));
        this._statusItem.label.text = this._t('Status: paused — {minutes} min', {minutes});
        const delay = Math.max(1, Math.min(remaining, 60));
        this._timeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            delay,
            () => {
                this._timeoutId = 0;
                this._refresh(true);
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _showError() {
        const showBanner = this._mode !== 'error';
        this._clearTimeout();
        this._mode = 'error';
        this._setProtectionIcon(false);
        this._statusItem.label.text = this._t('Status: error — protection unconfirmed');
        if (showBanner)
            this._showBanner(
                'error',
                this._t('CopyPasteBin: protection error'),
                this._t('Clipboard protection could not be confirmed.')
            );
    }

    _showEmptyClipboard() {
        this._showBanner(
            'info',
            this._t('CopyPasteBin: empty clipboard'),
            this._t('The clipboard contains no text to analyze.')
        );
    }

    _setProtectionIcon(active) {
        if (!active)
            this._clearClipboardFlash();
        if (active && this._clipboardFlashTimeoutId !== 0)
            return;
        this._panelIcon.gicon = active ? this._activeIcon : this._pausedIcon;
    }

    _flashClipboardChange() {
        this._clearClipboardFlash();
        this._panelIcon.gicon = this._copyingIcon;
        this._clipboardFlashTimeoutId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            CLIPBOARD_FLASH_MILLISECONDS,
            () => {
                this._clipboardFlashTimeoutId = 0;
                this._setProtectionIcon(this._mode === 'active');
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _clearClipboardFlash() {
        if (this._clipboardFlashTimeoutId !== 0) {
            GLib.source_remove(this._clipboardFlashTimeoutId);
            this._clipboardFlashTimeoutId = 0;
        }
    }

    _clearTimeout() {
        if (this._timeoutId !== 0) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
    }

    destroy() {
        this._ownerChangeSequence++;
        this._eventSequence++;
        this._filterSequence++;
        this._autoClearSettingSequence++;
        this._languageSequence++;
        this._recentClipboardSequence++;
        this._transferCancellable?.cancel();
        this._transferCancellable = null;
        this._editorProcess?.force_exit();
        this._editorProcess = null;
        this._filterEditorProcess?.force_exit();
        this._filterEditorProcess = null;
        this._rulesProcess?.force_exit();
        this._rulesProcess = null;
        this._recentClipboardProcess?.force_exit();
        this._recentClipboardProcess = null;
        this._aboutProcess?.force_exit();
        this._aboutProcess = null;
        this._safePasteSequence++;
        this._safePasteProcess?.force_exit();
        this._safePasteProcess = null;
        this._clearQuitResetTimeout();
        this._clearBannerTimeout();
        this._banner.remove_all_transitions();
        Main.layoutManager.removeChrome(this._banner);
        this._banner.destroy();
        this._clearIgnoreOwnerTimeout();
        this._cancelAutoClear();
        this._resetClipboardIdentity();
        this._clearClipboardFlash();
        if (this._selectionSignalId !== 0) {
            this._selection.disconnect(this._selectionSignalId);
            this._selectionSignalId = 0;
        }
        if (this._sessionModeSignalId !== 0) {
            Main.sessionMode.disconnect(this._sessionModeSignalId);
            this._sessionModeSignalId = 0;
        }
        if (this._menuSignalId !== 0) {
            this.menu.disconnect(this._menuSignalId);
            this._menuSignalId = 0;
        }
        this._clearTimeout();
        super.destroy();
    }
});

export default class CopyPasteBinExtension extends Extension {
    enable() {
        this._recentClipboardState = {entries: [], totalBytes: 0, nextId: 1};
        this._paths = {
            entryPoint: GLib.build_filenamev([
            GLib.get_home_dir(),
            '.local',
            'share',
            'copypastebin',
            'venv',
            'bin',
            'cpb',
            ]),
            editorPath: GLib.build_filenamev([this.path, 'editor.js']),
            filterEditorPath: GLib.build_filenamev([this.path, 'filter-editor.js']),
            rulesEditorPath: GLib.build_filenamev([this.path, 'rules-editor.js']),
            recentClipboardPath: GLib.build_filenamev([this.path, 'recent-clipboard.js']),
            aboutPath: GLib.build_filenamev([this.path, 'about.js']),
            activeIconPath: GLib.build_filenamev([this.path, 'icon-active.svg']),
            pausedIconPath: GLib.build_filenamev([this.path, 'icon-paused.svg']),
            copyingIconPath: GLib.build_filenamev([this.path, 'icon-copying.svg']),
        };
        this._createIndicator({choice: 'system', effective: systemLanguage()});
        this._settings = this.getSettings();
        Main.wm.addKeybinding(
            SAFE_PASTE_KEY,
            this._settings,
            Meta.KeyBindingFlags.IGNORE_AUTOREPEAT,
            Shell.ActionMode.NORMAL,
            () => this._indicator?.safePaste()
        );
    }

    _createIndicator(languageStatus) {
        const paths = this._paths;
        this._indicator = new CopyPasteBinIndicator(
            this.uuid,
            paths.entryPoint,
            paths.editorPath,
            paths.filterEditorPath,
            paths.rulesEditorPath,
            paths.recentClipboardPath,
            paths.aboutPath,
            paths.activeIconPath,
            paths.pausedIconPath,
            paths.copyingIconPath,
            languageStatus,
            this._recentClipboardState,
            status => this._replaceIndicator(status)
        );
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    _replaceIndicator(languageStatus) {
        GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._indicator?.destroy();
            this._indicator = null;
            if (this._paths !== null)
                this._createIndicator(languageStatus);
            return GLib.SOURCE_REMOVE;
        });
    }

    disable() {
        Main.wm.removeKeybinding(SAFE_PASTE_KEY);
        this._settings = null;
        this._paths = null;
        this._indicator?.destroy();
        this._indicator = null;
        if (this._recentClipboardState !== null)
            clearRecentClipboardState(this._recentClipboardState);
        this._recentClipboardState = null;
    }
}
