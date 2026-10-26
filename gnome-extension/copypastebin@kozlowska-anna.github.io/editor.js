import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix?version=2.0';
import Gdk from 'gi://Gdk?version=4.0';
import GLib from 'gi://GLib';
import GLibUnix from 'gi://GLibUnix?version=2.0';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';
import {backendCommand} from './backend-path.js';
import {languageFromArgs, translate} from './i18n.js';

const SUGGEST_REDACTION = ARGV.includes('--suggest-redaction');
if (ARGV.some(argument => argument !== '--suggest-redaction' &&
    argument !== '--language=pl' && argument !== '--language=en'))
    System.exit(1);
const LANGUAGE = languageFromArgs(ARGV.filter(argument =>
    argument === '--language=pl' || argument === '--language=en'
));
const t = (message, values = {}) => translate(LANGUAGE, message, values);

const MAX_INPUT_BYTES = 10 * 1024 * 1024;
const MAX_DETECTIONS_BYTES = 64 * 1024;
const MAX_DETECTIONS = 1000;
const MAX_EXCLUSION_REQUEST_BYTES = 2048;
const CLICK_MOVE_TOLERANCE = 6;
const EXCLUDABLE_CATEGORY_LABELS = new Map([
    ['EMAIL', 'Email address'],
    ['PHONE', 'Phone number'],
    ['IBAN', 'IBAN'],
    ['HOME_PATH', 'Home path'],
    ['IP_ADDRESS', 'IP address'],
    ['MONEY_AMOUNT_PLN_USD', 'Currency amount'],
    ['CRYPTO_AMOUNT_BTC_XRP', 'Cryptocurrency amount'],
]);
function readStdin() {
    const stream = new GioUnix.InputStream({fd: 0, close_fd: false});
    const chunks = [];
    let total = 0;
    while (true) {
        const bytes = stream.read_bytes(
            Math.min(64 * 1024, MAX_INPUT_BYTES + 1 - total),
            null
        ).get_data();
        if (bytes.length === 0)
            break;
        total += bytes.length;
        if (total > MAX_INPUT_BYTES)
            throw new Error('closed input failure');
        chunks.push(bytes);
    }
    const combined = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
        combined.set(chunk, offset);
        offset += chunk.length;
    }
    const text = new TextDecoder('utf-8', {fatal: true}).decode(combined);
    if (text.length === 0 || text.includes('\0'))
        throw new Error('closed input failure');
    return text;
}

function bufferText(buffer) {
    const [start, end] = buffer.get_bounds();
    return buffer.get_text(start, end, true);
}

function collapseSpaces(text) {
    return text
        .split(/\r\n|\r|\n/)
        .map(line => line.replace(/[\t\f\v ]+/g, ' ').trim())
        .join('\n');
}

function tidyLineBreaks(text) {
    return text
        .replace(/\r\n|\r/g, '\n')
        .replace(/[\t ]+\n/g, '\n')
        .replace(/\n[\t ]+/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

function joinLines(text) {
    return text
        .split(/\r\n|\r|\n/)
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .join(' ')
        .replace(/[\t\f\v ]+/g, ' ');
}

function removeBlankLines(text) {
    return text
        .split(/\r\n|\r|\n/)
        .filter(line => line.trim().length > 0)
        .join('\n');
}

function sentenceCase(text) {
    const lower = text.toLocaleLowerCase();
    return lower.replace(/(^|[.!?]\s+)(\p{L})/gu,
        (_match, prefix, letter) => prefix + letter.toLocaleUpperCase());
}

const EditorApplication = GObject.registerClass(
class EditorApplication extends Gtk.Application {
    constructor(initialText) {
        super({application_id: 'io.github.copypastebin.Editor'});
        this._initialText = initialText;
        this._process = null;
        this._window = null;
        this._clearArmed = false;
        this._currentDetections = [];
        this._selectionPopover = null;
        this._clickStart = null;
        this._presentSignalId = GLibUnix.signal_add(
            GLib.PRIORITY_DEFAULT,
            10,
            () => {
                if (this._window === null) {
                    this.quit();
                    return GLib.SOURCE_REMOVE;
                }
                try {
                    this._window.present();
                    this._window.grab_focus();
                } catch (_error) {
                    this.quit();
                    return GLib.SOURCE_REMOVE;
                }
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    vfunc_activate() {
        const window = new Gtk.ApplicationWindow({
            application: this,
            title: `CopyPasteBin — ${t('Clipboard editor')}`,
            default_width: 1060,
            default_height: 580,
        });
        this._window = window;
        const layout = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 10,
            margin_top: 14,
            margin_bottom: 14,
            margin_start: 14,
            margin_end: 14,
        });
        const explanation = new Gtk.Label({
            label: t('Edit the text or use an anonymization suggestion. The clipboard changes only after you save.'),
            wrap: true,
            xalign: 0,
        });
        layout.append(explanation);
        layout.append(new Gtk.Label({
            label: t('Select a fragment and click it to anonymize it. A highlighted low- or medium-risk value also offers an exact exception.'),
            wrap: true,
            xalign: 0,
        }));

        this._buffer = new Gtk.TextBuffer({enable_undo: false});
        this._buffer.set_text(this._initialText, -1);
        this._buffer.set_enable_undo(true);
        this._buffer.set_max_undo_levels(50);
        this._lowTag = new Gtk.TextTag({
            name: 'cpb-low',
            background: '#9ecbff',
            foreground: '#1f1f1f',
        });
        this._mediumTag = new Gtk.TextTag({
            name: 'cpb-medium',
            background: '#f6d365',
            foreground: '#1f1f1f',
        });
        this._highTag = new Gtk.TextTag({
            name: 'cpb-high',
            background: '#ff8a8a',
            foreground: '#1f1f1f',
            weight: 700,
        });
        this._criticalTag = new Gtk.TextTag({
            name: 'cpb-critical',
            background: '#b21f32',
            foreground: '#ffffff',
            weight: 800,
        });
        this._buffer.get_tag_table().add(this._lowTag);
        this._buffer.get_tag_table().add(this._mediumTag);
        this._buffer.get_tag_table().add(this._highTag);
        this._buffer.get_tag_table().add(this._criticalTag);
        this._textRevision = 0;
        this._buffer.connect('changed', () => {
            this._textRevision++;
            this._clearDetectionMarks();
        });
        const view = new Gtk.TextView({
            buffer: this._buffer,
            wrap_mode: Gtk.WrapMode.WORD_CHAR,
            monospace: true,
            top_margin: 8,
            bottom_margin: 8,
            left_margin: 8,
            right_margin: 8,
        });
        this._view = view;
        const detectionClick = new Gtk.GestureClick({button: Gdk.BUTTON_PRIMARY});
        detectionClick.set_propagation_phase(Gtk.PropagationPhase.CAPTURE);
        detectionClick.connect('pressed', (_gesture, presses, x, y) => {
            this._clickStart = presses === 1
                ? {x, y, selection: this._selectionCandidateAt(x, y)}
                : null;
        });
        detectionClick.connect('released', (_gesture, presses, x, y) => {
            const start = this._clickStart;
            this._clickStart = null;
            if (presses !== 1 || start === null)
                return;
            if (Math.hypot(x - start.x, y - start.y) > CLICK_MOVE_TOLERANCE)
                return;
            if (start.selection !== null) {
                this._closeSelectionPopover();
                const exclusionCandidate =
                    this._exclusionCandidateForSelection(start.selection);
                this._showSelectionPopover(
                    start.selection,
                    exclusionCandidate,
                    x,
                    y
                );
                return;
            }
            this._handleDetectionClick(x, y);
        });
        detectionClick.connect('stopped', () => {
            this._clickStart = null;
        });
        view.add_controller(detectionClick);
        const scroller = new Gtk.ScrolledWindow({
            hexpand: true,
            vexpand: true,
            child: view,
        });
        layout.append(scroller);

        const tools = new Gtk.Expander({
            label: t('Quick text tools'),
            expanded: false,
        });
        const toolLayout = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 8,
            margin_top: 8,
        });
        const toolButtons = new Gtk.FlowBox({
            selection_mode: Gtk.SelectionMode.NONE,
            column_spacing: 6,
            row_spacing: 6,
            max_children_per_line: 4,
        });
        this._appendTool(toolButtons, t('Remove formatting'), () => {
            this._status.label = t('After saving, the clipboard will contain plain text only.');
        });
        this._appendTool(toolButtons, t('Remove extra spaces'), () => {
            this._transform(collapseSpaces, t('Extra spaces removed.'));
        });
        this._appendTool(toolButtons, t('Tidy line breaks'), () => {
            this._transform(tidyLineBreaks, t('Line breaks tidied.'));
        });
        this._appendTool(toolButtons, t('Join lines'), () => {
            this._transform(joinLines, t('Lines joined.'));
        });
        this._appendTool(toolButtons, t('lowercase'), () => {
            this._transform(text => text.toLocaleLowerCase(), t('Text changed to lowercase.'));
        });
        this._appendTool(toolButtons, t('UPPERCASE'), () => {
            this._transform(text => text.toLocaleUpperCase(), t('Text changed to uppercase.'));
        });
        this._appendTool(toolButtons, t('Sentence case'), () => {
            this._transform(sentenceCase, t('Text changed to sentence case.'));
        });
        this._appendTool(toolButtons, t('Remove blank lines'), () => {
            this._transform(removeBlankLines, t('Blank lines removed.'));
        });
        const undoContent = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 6,
        });
        undoContent.append(new Gtk.Image({icon_name: 'edit-undo-symbolic'}));
        undoContent.append(new Gtk.Label({label: t('Undo last change')}));
        this._undo = new Gtk.Button({
            child: undoContent,
            tooltip_text: t('Undo last change'),
        });
        this._undo.sensitive = this._buffer.get_can_undo();
        this._undo.connect('clicked', () => {
            if (this._buffer.get_can_undo()) {
                this._buffer.undo();
                this._status.label = t('Last change undone.');
            }
        });
        this._buffer.connect('notify::can-undo', () => {
            this._undo.sensitive = this._buffer.get_can_undo();
        });
        toolLayout.append(toolButtons);

        const replaceRow = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 6,
        });
        this._find = new Gtk.Entry({placeholder_text: t('Find'), hexpand: true});
        this._replace = new Gtk.Entry({placeholder_text: t('Replace with'), hexpand: true});
        const replaceButton = new Gtk.Button({label: t('Replace all')});
        replaceButton.connect('clicked', () => this._replaceAll());
        replaceRow.append(this._find);
        replaceRow.append(this._replace);
        replaceRow.append(replaceButton);
        toolLayout.append(replaceRow);
        tools.set_child(toolLayout);
        layout.append(tools);

        this._status = new Gtk.Label({label: '', wrap: true, xalign: 0});
        layout.append(this._status);

        const actions = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 8,
            halign: Gtk.Align.END,
        });
        this._anonymize = new Gtk.Button({label: t('Anonymize detected data')});
        this._anonymize.connect('clicked', () => this._suggestRedaction());
        actions.append(this._anonymize);
        this._inspect = new Gtk.Button({label: t('Highlight detected data')});
        this._inspect.connect('clicked', () => this._inspectDetections(false));
        actions.append(this._inspect);
        actions.append(this._undo);
        this._clear = new Gtk.Button({label: t('Clear clipboard')});
        this._clear.add_css_class('destructive-action');
        this._clear.connect('clicked', () => this._confirmClear());
        actions.append(this._clear);
        const cancel = new Gtk.Button({label: t('Cancel')});
        cancel.connect('clicked', () => window.close());
        actions.append(cancel);
        this._save = new Gtk.Button({label: t('Replace clipboard')});
        this._save.add_css_class('suggested-action');
        this._save.connect('clicked', () => this._writeResult());
        actions.append(this._save);
        layout.append(actions);

        window.set_child(layout);
        window.connect('close-request', () => {
            this._window = null;
            this._closeSelectionPopover();
            this._process?.force_exit();
            this.quit();
            return false;
        });
        window.present();
        view.grab_focus();
        GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            if (SUGGEST_REDACTION)
                this._suggestRedaction();
            else
                this._inspectDetections(true);
            return GLib.SOURCE_REMOVE;
        });
    }

    _appendTool(container, label, action) {
        const button = new Gtk.Button({label});
        button.connect('clicked', action);
        container.insert(button, -1);
    }

    _transform(operation, successMessage) {
        const original = bufferText(this._buffer);
        const changed = operation(original);
        if (changed === original) {
            this._status.label = t('The text does not need this change.');
            return;
        }
        const [start, end] = this._buffer.get_bounds();
        this._buffer.begin_user_action();
        this._buffer.delete(start, end);
        this._buffer.insert(start, changed, -1);
        this._buffer.end_user_action();
        this._status.label = successMessage;
    }

    _replaceAll() {
        const searched = this._find.text;
        if (searched.length === 0) {
            this._status.label = t('Enter text in the “Find” field.');
            this._find.grab_focus();
            return;
        }
        const original = bufferText(this._buffer);
        const occurrences = original.split(searched).length - 1;
        if (occurrences === 0) {
            this._status.label = t('The specified text was not found.');
            return;
        }
        const replacement = this._replace.text;
        this._transform(
            text => text.split(searched).join(replacement),
            t('Replacements: {count}.', {count: occurrences})
        );
    }

    _setBusy(busy) {
        this._anonymize.sensitive = !busy;
        this._inspect.sensitive = !busy;
        this._clear.sensitive = !busy;
        this._save.sensitive = !busy;
    }

    _clearDetectionMarks() {
        this._closeSelectionPopover();
        const [start, end] = this._buffer.get_bounds();
        this._buffer.remove_tag(this._lowTag, start, end);
        this._buffer.remove_tag(this._mediumTag, start, end);
        this._buffer.remove_tag(this._highTag, start, end);
        this._buffer.remove_tag(this._criticalTag, start, end);
        this._currentDetections = [];
    }

    _inspectDetections(automatic) {
        const text = bufferText(this._buffer);
        const encoded = new TextEncoder().encode(text);
        if (encoded.length === 0 || encoded.length > MAX_INPUT_BYTES || text.includes('\0')) {
            if (!automatic)
                this._status.label = t('The text is empty or exceeds the safe limit.');
            return;
        }
        this._setBusy(true);
        this._status.label = t('Checking detected data…');
        try {
            this._process = Gio.Subprocess.new(
                backendCommand('ui', 'detections'),
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._process = null;
            this._setBusy(false);
            this._status.label = t('Detected data could not be highlighted.');
            return;
        }
        this._process.communicate_utf8_async(text, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_DETECTIONS_BYTES)
                    throw new Error('closed detections failure');
                const detections = this._parseDetections(stdout, Array.from(text).length);
                this._clearDetectionMarks();
                this._currentDetections = detections;
                const counts = {low: 0, medium: 0, high: 0, critical: 0};
                const tags = {
                    low: this._lowTag,
                    medium: this._mediumTag,
                    high: this._highTag,
                    critical: this._criticalTag,
                };
                for (const item of detections) {
                    const start = this._buffer.get_iter_at_offset(item.start);
                    const end = this._buffer.get_iter_at_offset(item.end);
                    this._buffer.apply_tag(
                        tags[item.risk],
                        start,
                        end
                    );
                    counts[item.risk]++;
                }
                this._status.label = detections.length === 0
                    ? t('No data covered by active filters was detected.')
                    : t('Highlighted: {critical} critical, {high} high, {medium} medium, {low} low.', counts);
            } catch (_error) {
                this._status.label = t('Detected data could not be highlighted.');
            } finally {
                this._process = null;
                this._setBusy(false);
            }
        });
    }

    _parseDetections(stdout, textLength) {
        const payload = JSON.parse(stdout);
        if (payload === null || typeof payload !== 'object' ||
            Object.keys(payload).length !== 2 || payload.version !== 1 ||
            !Array.isArray(payload.detections) ||
            payload.detections.length > MAX_DETECTIONS)
            throw new Error('closed detections failure');
        let previousEnd = 0;
        return payload.detections.map(item => {
            if (item === null || typeof item !== 'object' ||
                Object.keys(item).length !== 4 ||
                !Number.isSafeInteger(item.start) ||
                !Number.isSafeInteger(item.end) || item.start < previousEnd ||
                item.start < 0 || item.end <= item.start || item.end > textLength ||
                typeof item.category !== 'string' ||
                !/^[A-Z_]{2,64}$/.test(item.category) ||
                !['low', 'medium', 'high', 'critical'].includes(item.risk))
                throw new Error('closed detections failure');
            previousEnd = item.end;
            return item;
        });
    }

    _confirmClear() {
        if (!this._clearArmed) {
            this._clearArmed = true;
            this._clear.label = t('Confirm clearing');
            this._status.label = t('Click again to permanently clear the current clipboard.');
            return;
        }
        try {
            const output = new GioUnix.OutputStream({fd: 1, close_fd: false});
            const marker = new Uint8Array([0]);
            const [writtenAll, written] = output.write_all(marker, null);
            if (!writtenAll || written !== marker.length)
                throw new Error('closed output failure');
            output.flush(null);
            this.quit();
        } catch (_error) {
            this._clearArmed = false;
            this._clear.label = t('Clear clipboard');
            this._status.label = t('The clipboard could not be cleared.');
        }
    }

    _suggestRedaction() {
        const text = bufferText(this._buffer);
        this._requestRedaction(text, redacted => {
            this._transform(
                () => redacted,
                t('Suggestion inserted. You can edit it before saving.')
            );
        });
    }

    _suggestSelectedRedaction(candidate) {
        if (!this._selectionCandidateIsCurrent(candidate)) {
            this._status.label = t('The text changed during analysis. Select the fragment again.');
            return;
        }
        this._requestRedaction(candidate.text, redacted => {
            if (!this._selectionCandidateIsCurrent(candidate)) {
                this._status.label = t('The text changed during analysis. Select the fragment again.');
                return;
            }
            if (redacted === candidate.text) {
                this._status.label = t('No data to anonymize was detected in the selection.');
                return;
            }
            const selectionStart = this._buffer.get_iter_at_offset(candidate.start);
            const selectionEnd = this._buffer.get_iter_at_offset(candidate.end);
            this._buffer.begin_user_action();
            this._buffer.delete(selectionStart, selectionEnd);
            const insertion = this._buffer.get_iter_at_offset(candidate.start);
            this._buffer.insert(insertion, redacted, -1);
            this._buffer.end_user_action();
            this._status.label = t('Only the selected fragment was anonymized.');
        });
    }

    _handleDetectionClick(x, y) {
        this._closeSelectionPopover();
        const [bufferX, bufferY] = this._view.window_to_buffer_coords(
            Gtk.TextWindowType.WIDGET,
            Math.floor(x),
            Math.floor(y)
        );
        const [found, iter] = this._view.get_iter_at_position(
            bufferX,
            bufferY
        );
        if (!found)
            return;
        const offset = iter.get_offset();
        const detection = this._currentDetections.find(item =>
            offset >= item.start && offset < item.end
        );
        if (detection === undefined)
            return;
        const start = this._buffer.get_iter_at_offset(detection.start);
        const end = this._buffer.get_iter_at_offset(detection.end);
        const literal = this._buffer.get_text(start, end, true);
        this._buffer.select_range(start, end);
        const selectionCandidate = {
            text: literal,
            start: detection.start,
            end: detection.end,
            revision: this._textRevision,
        };
        const exclusionCandidate =
            this._exclusionCandidateForSelection(selectionCandidate);
        this._showSelectionPopover(selectionCandidate, exclusionCandidate, x, y);
    }

    _selectionCandidateAt(x, y) {
        const [hasSelection, start, end] = this._buffer.get_selection_bounds();
        if (!hasSelection || start.equal(end))
            return null;
        const [bufferX, bufferY] = this._view.window_to_buffer_coords(
            Gtk.TextWindowType.WIDGET,
            Math.floor(x),
            Math.floor(y)
        );
        const [found, iter] = this._view.get_iter_at_position(bufferX, bufferY);
        if (!found || iter.get_offset() < start.get_offset() ||
            iter.get_offset() >= end.get_offset())
            return null;
        return {
            text: this._buffer.get_text(start, end, true),
            start: start.get_offset(),
            end: end.get_offset(),
            revision: this._textRevision,
        };
    }

    _exclusionCandidateForSelection(selectionCandidate) {
        const detection = this._currentDetections.find(item =>
            item.start === selectionCandidate.start &&
            item.end === selectionCandidate.end
        );
        const length = Array.from(selectionCandidate.text).length;
        if (detection === undefined ||
            (detection.risk !== 'low' && detection.risk !== 'medium') ||
            !EXCLUDABLE_CATEGORY_LABELS.has(detection.category) ||
            length < 3 || length > 128 ||
            /[\p{Cc}\p{Cf}]/u.test(selectionCandidate.text))
            return null;
        return {
            literal: selectionCandidate.text,
            category: detection.category,
            risk: detection.risk,
            start: selectionCandidate.start,
            end: selectionCandidate.end,
            revision: selectionCandidate.revision,
        };
    }

    _showSelectionPopover(selectionCandidate, exclusionCandidate, x, y) {
        const popover = new Gtk.Popover({
            autohide: true,
            has_arrow: true,
        });
        const content = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 6,
            margin_top: 8,
            margin_bottom: 8,
            margin_start: 8,
            margin_end: 8,
        });
        content.append(new Gtk.Label({
            label: t('Selected fragment'),
            xalign: 0,
        }));
        const anonymize = new Gtk.Button({label: t('Anonymize selection')});
        anonymize.connect('clicked', () => {
            this._closeSelectionPopover();
            this._suggestSelectedRedaction(selectionCandidate);
        });
        content.append(anonymize);
        if (exclusionCandidate !== null) {
            const exclude = new Gtk.Button({label: t('Exclude this detection')});
            exclude.add_css_class('destructive-action');
            exclude.connect('clicked', () => {
                this._closeSelectionPopover();
                if (!this._detectionCandidateIsCurrent(exclusionCandidate)) {
                    this._status.label = t('The detection changed. Click the highlighted value again.');
                    return;
                }
                this._confirmDetectionExclusion(exclusionCandidate);
            });
            content.append(exclude);
        }
        popover.set_child(content);
        popover.set_parent(this._view);
        popover.set_pointing_to(new Gdk.Rectangle({
            x: Math.round(x),
            y: Math.round(y),
            width: 1,
            height: 1,
        }));
        popover.connect('closed', () => {
            if (this._selectionPopover === popover)
                this._selectionPopover = null;
            if (popover.get_parent() !== null)
                popover.unparent();
        });
        this._selectionPopover = popover;
        popover.popup();
    }

    _closeSelectionPopover() {
        const popover = this._selectionPopover;
        this._selectionPopover = null;
        if (popover === null)
            return;
        popover.popdown();
        if (popover.get_parent() !== null)
            popover.unparent();
    }

    _selectionCandidateIsCurrent(candidate) {
        if (candidate === null || candidate.revision !== this._textRevision)
            return false;
        const start = this._buffer.get_iter_at_offset(candidate.start);
        const end = this._buffer.get_iter_at_offset(candidate.end);
        return this._buffer.get_text(start, end, true) === candidate.text;
    }

    _detectionCandidateIsCurrent(candidate) {
        if (candidate.revision !== this._textRevision)
            return false;
        const detection = this._currentDetections.find(item =>
            item.start === candidate.start && item.end === candidate.end &&
            item.category === candidate.category && item.risk === candidate.risk
        );
        if (detection === undefined)
            return false;
        const start = this._buffer.get_iter_at_offset(candidate.start);
        const end = this._buffer.get_iter_at_offset(candidate.end);
        return this._buffer.get_text(start, end, true) === candidate.literal;
    }

    _confirmDetectionExclusion(candidate) {
        const dialog = new Gtk.MessageDialog({
            transient_for: this._window,
            modal: true,
            message_type: Gtk.MessageType.WARNING,
            buttons: Gtk.ButtonsType.NONE,
            text: t('Add this detection to exceptions?'),
            secondary_text: t(
                'This detected {category} will stop producing this exact warning. Do not exclude real sensitive data.',
                {category: t(EXCLUDABLE_CATEGORY_LABELS.get(candidate.category))}
            ),
        });
        dialog.add_button(t('Cancel'), Gtk.ResponseType.CANCEL);
        dialog.add_button(t('Add exception'), Gtk.ResponseType.ACCEPT);
        dialog.set_default_response(Gtk.ResponseType.CANCEL);
        dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT)
            ?.add_css_class('destructive-action');
        dialog.connect('response', (_source, response) => {
            dialog.destroy();
            if (response !== Gtk.ResponseType.ACCEPT) {
                this._status.label = t('The exception was not added.');
                return;
            }
            if (!this._detectionCandidateIsCurrent(candidate)) {
                this._status.label = t('The detection changed. Click the highlighted value again.');
                return;
            }
            this._saveSelectedExclusion(candidate);
        });
        dialog.present();
    }

    _saveSelectedExclusion(candidate) {
        const payload = JSON.stringify({
            version: 1,
            literal: candidate.literal,
            category: candidate.category,
        });
        if (new TextEncoder().encode(payload).length > MAX_EXCLUSION_REQUEST_BYTES) {
            this._status.label = t('This value cannot be stored as an exception.');
            return;
        }
        this._setBusy(true);
        this._status.label = t('Saving exception…');
        try {
            this._process = Gio.Subprocess.new(
                backendCommand('ui', 'exclusion-add'),
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._process = null;
            this._setBusy(false);
            this._status.label = t('The exception could not be saved safely.');
            return;
        }
        this._process.communicate_utf8_async(payload, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > 128)
                    throw new Error('closed exclusion save failure');
                const response = JSON.parse(stdout);
                if (response === null || typeof response !== 'object' ||
                    Object.keys(response).sort().join(',') !== 'status,version' ||
                    response.version !== 1 ||
                    !['added', 'enabled', 'exists', 'conflict', 'limit'].includes(response.status))
                    throw new Error('closed exclusion save failure');
                const messages = {
                    added: 'The exact selected value was added to exceptions.',
                    enabled: 'The existing exception was enabled.',
                    exists: 'This exact exception is already active.',
                    conflict: 'The selected value already exists as another rule or exception.',
                    limit: 'The exception limit has been reached.',
                };
                if (['added', 'enabled', 'exists'].includes(response.status)) {
                    const markStart = this._buffer.get_iter_at_offset(candidate.start);
                    const markEnd = this._buffer.get_iter_at_offset(candidate.end);
                    const tags = {
                        low: this._lowTag,
                        medium: this._mediumTag,
                    };
                    this._buffer.remove_tag(tags[candidate.risk], markStart, markEnd);
                    this._currentDetections = this._currentDetections.filter(item =>
                        !(item.start === candidate.start && item.end === candidate.end &&
                            item.category === candidate.category)
                    );
                }
                this._status.label = t(messages[response.status]);
            } catch (_error) {
                this._status.label = t('The exception could not be saved safely.');
            } finally {
                this._process = null;
                this._setBusy(false);
            }
        });
    }

    _requestRedaction(text, onSuccess) {
        const encoded = new TextEncoder().encode(text);
        if (encoded.length === 0 || encoded.length > MAX_INPUT_BYTES || text.includes('\0')) {
            this._status.label = t('The text is empty or exceeds the safe limit.');
            return;
        }
        this._setBusy(true);
        this._status.label = t('Preparing suggestion…');
        try {
            this._process = Gio.Subprocess.new(
                backendCommand('ui', 'redact'),
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._process = null;
            this._setBusy(false);
            this._status.label = t('The suggestion could not be prepared.');
            return;
        }
        this._process.communicate_async(
            new GLib.Bytes(encoded),
            null,
            (source, result) => {
                try {
                    const [, stdout] = source.communicate_finish(result);
                    const bytes = stdout.get_data();
                    if (!source.get_successful() || bytes.length === 0 ||
                        bytes.length > MAX_INPUT_BYTES)
                        throw new Error('closed redact failure');
                    const redacted = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
                    if (redacted.includes('\0'))
                        throw new Error('closed redact failure');
                    onSuccess(redacted);
                } catch (_error) {
                    this._status.label = t('The suggestion could not be prepared.');
                } finally {
                    this._process = null;
                    this._setBusy(false);
                }
            }
        );
    }

    _writeResult() {
        const text = bufferText(this._buffer);
        const bytes = new TextEncoder().encode(text);
        if (bytes.length === 0 || bytes.length > MAX_INPUT_BYTES || text.includes('\0')) {
            this._status.label = t('The text is empty or exceeds the safe limit.');
            return;
        }
        try {
            const output = new GioUnix.OutputStream({fd: 1, close_fd: false});
            const [writtenAll, written] = output.write_all(bytes, null);
            if (!writtenAll || written !== bytes.length)
                throw new Error('closed output failure');
            output.flush(null);
            this.quit();
        } catch (_error) {
            this._status.label = t('The change could not be saved.');
        }
    }
});

let initialText;
try {
    initialText = readStdin();
} catch (_error) {
    System.exit(1);
}

const application = new EditorApplication(initialText);
application.run([System.programInvocationName]);
