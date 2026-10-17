import GioUnix from 'gi://GioUnix?version=2.0';
import GLib from 'gi://GLib';
import GLibUnix from 'gi://GLibUnix?version=2.0';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';
import Pango from 'gi://Pango';
import System from 'system';
import {languageFromArgs, translate} from './i18n.js';

const LANGUAGE = languageFromArgs(ARGV);
const t = (message, values = {}) => translate(LANGUAGE, message, values);

const MAX_ENTRIES = 15;
const MAX_ITEM_BYTES = 256 * 1024;
const MAX_TOTAL_BYTES = 2 * 1024 * 1024;
const MAX_PROTOCOL_BYTES = MAX_TOTAL_BYTES + 185;
const PREVIEW_CHARACTERS = 64;

function readInput() {
    const stream = new GioUnix.InputStream({fd: 0, close_fd: false});
    const chunks = [];
    let total = 0;
    while (true) {
        const chunk = stream.read_bytes(64 * 1024, null).get_data();
        if (chunk.length === 0)
            break;
        total += chunk.length;
        if (total > MAX_PROTOCOL_BYTES)
            throw new Error('closed recent clipboard input failure');
        chunks.push(chunk);
    }
    const input = new Uint8Array(total);
    let target = 0;
    for (const chunk of chunks) {
        input.set(chunk, target);
        target += chunk.length;
    }
    return parseInput(input);
}

function parseInput(input) {
    if (input.length < 5 || input[0] !== 0x43 || input[1] !== 0x50 ||
        input[2] !== 0x42 || input[3] !== 0x31 ||
        input[4] < 1 || input[4] > MAX_ENTRIES)
        throw new Error('closed recent clipboard input failure');
    let offset = 5;
    const readUint32 = () => {
        if (offset + 4 > input.length)
            throw new Error('closed recent clipboard input failure');
        const value = (((input[offset] << 24) >>> 0) |
            (input[offset + 1] << 16) |
            (input[offset + 2] << 8) |
            input[offset + 3]) >>> 0;
        offset += 4;
        return value;
    };
    const ids = new Set();
    const entries = [];
    let contentBytes = 0;
    for (let index = 0; index < input[4]; index++) {
        const id = readUint32();
        const createdAtSeconds = readUint32();
        const length = readUint32();
        if (id === 0 || ids.has(id) || createdAtSeconds === 0 ||
            length === 0 || length > MAX_ITEM_BYTES ||
            offset + length > input.length)
            throw new Error('closed recent clipboard input failure');
        ids.add(id);
        contentBytes += length;
        if (contentBytes > MAX_TOTAL_BYTES)
            throw new Error('closed recent clipboard input failure');
        const text = new TextDecoder('utf-8', {fatal: true}).decode(
            input.slice(offset, offset + length)
        );
        if (text.length === 0 || text.includes('\0'))
            throw new Error('closed recent clipboard input failure');
        entries.push({id, createdAt: createdAtSeconds * 1000, text});
        offset += length;
    }
    if (offset !== input.length)
        throw new Error('closed recent clipboard input failure');
    return entries;
}

function safeDisplayText(text, limit = null) {
    let rendered = '';
    let characters = 0;
    let truncated = false;
    for (const character of text) {
        if (limit !== null && characters === limit) {
            truncated = true;
            break;
        }
        const code = character.codePointAt(0);
        if (character === '\n' || character === '\r' || character === '\t')
            rendered += limit === null ? character : ' ';
        else if (code < 0x20 || (code >= 0x7f && code <= 0x9f) ||
            (code >= 0x202a && code <= 0x202e) ||
            (code >= 0x2066 && code <= 0x2069))
            rendered += '�';
        else
            rendered += character;
        characters++;
    }
    if (limit !== null)
        rendered = rendered.replace(/\s+/gu, ' ').trim();
    return `${rendered}${truncated ? '…' : ''}`;
}

function writeAction(action, id) {
    const output = new GioUnix.OutputStream({fd: 1, close_fd: false});
    const bytes = new Uint8Array([
        action,
        (id >>> 24) & 0xff,
        (id >>> 16) & 0xff,
        (id >>> 8) & 0xff,
        id & 0xff,
    ]);
    const [writtenAll, written] = output.write_all(bytes, null);
    if (!writtenAll || written !== bytes.length)
        throw new Error('closed recent clipboard output failure');
    output.flush(null);
}

const RecentClipboardApplication = GObject.registerClass(
class RecentClipboardApplication extends Gtk.Application {
    constructor(entries) {
        super({application_id: 'io.github.copypastebin.RecentClipboard'});
        this._entries = entries;
        this._window = null;
        this._selected = null;
        this._clearArmed = false;
        this._presentSignalId = GLibUnix.signal_add(
            GLib.PRIORITY_DEFAULT,
            10,
            () => {
                if (this._window === null) {
                    this.quit();
                    return GLib.SOURCE_REMOVE;
                }
                this._window.present();
                this._window.grab_focus();
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    vfunc_activate() {
        const window = new Gtk.ApplicationWindow({
            application: this,
            title: `CopyPasteBin — ${t('Recent clipboard')}`,
            default_width: 1020,
            default_height: 700,
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
        layout.append(new Gtk.Label({
            label: t('CopyPasteBin keeps up to 15 recently copied text items only in temporary memory. Locking the screen, logging out, or stopping the program clears the list.'),
            wrap: true,
            xalign: 0,
        }));
        layout.append(new Gtk.Label({
            label: t('Select an item to preview it. Restoring replaces the current clipboard.'),
            wrap: true,
            xalign: 0,
        }));

        const content = new Gtk.Paned({orientation: Gtk.Orientation.HORIZONTAL});
        const list = new Gtk.ListBox({
            selection_mode: Gtk.SelectionMode.SINGLE,
            width_request: 320,
        });
        this._list = list;
        let firstRow = null;
        for (const entry of this._entries) {
            const time = new Date(entry.createdAt).toLocaleTimeString(
                LANGUAGE === 'pl' ? 'pl-PL' : 'en-GB', {
                    hour: '2-digit',
                    minute: '2-digit',
                }
            );
            const preview = safeDisplayText(entry.text, PREVIEW_CHARACTERS) ||
                t('Whitespace-only text');
            const row = new Gtk.ListBoxRow();
            row._entry = entry;
            const rowLayout = new Gtk.Box({
                orientation: Gtk.Orientation.VERTICAL,
                spacing: 3,
                margin_top: 8,
                margin_bottom: 8,
                margin_start: 8,
                margin_end: 8,
            });
            rowLayout.append(new Gtk.Label({label: time, xalign: 0}));
            rowLayout.append(new Gtk.Label({
                label: preview,
                xalign: 0,
                ellipsize: Pango.EllipsizeMode.END,
                max_width_chars: 42,
            }));
            row.set_child(rowLayout);
            list.append(row);
            firstRow ??= row;
        }
        this._preview = new Gtk.TextBuffer();
        const previewView = new Gtk.TextView({
            buffer: this._preview,
            editable: false,
            cursor_visible: false,
            monospace: true,
            wrap_mode: Gtk.WrapMode.WORD_CHAR,
            top_margin: 8,
            bottom_margin: 8,
            left_margin: 8,
            right_margin: 8,
        });
        const listScroller = new Gtk.ScrolledWindow({
            child: list,
            vexpand: true,
        });
        const previewScroller = new Gtk.ScrolledWindow({
            child: previewView,
            hexpand: true,
            vexpand: true,
        });
        content.set_start_child(listScroller);
        content.set_end_child(previewScroller);
        content.set_position(320);
        layout.append(content);

        this._status = new Gtk.Label({
            label: t('Preview: control characters are displayed safely.'),
            wrap: true,
            xalign: 0,
        });
        layout.append(this._status);
        const actions = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 8,
            halign: Gtk.Align.END,
        });
        this._clear = new Gtk.Button({label: t('Clear all')});
        this._clear.add_css_class('destructive-action');
        this._clear.connect('clicked', () => this._confirmClear());
        actions.append(this._clear);
        const close = new Gtk.Button({label: t('Close')});
        close.connect('clicked', () => window.close());
        actions.append(close);
        this._restore = new Gtk.Button({label: t('Restore to clipboard')});
        this._restore.add_css_class('suggested-action');
        this._restore.sensitive = false;
        this._restore.connect('clicked', () => this._restoreSelected());
        actions.append(this._restore);
        layout.append(actions);

        list.connect('row-selected', (_list, row) => {
            this._selected = row?._entry ?? null;
            this._restore.sensitive = this._selected !== null;
            this._preview.set_text(
                this._selected === null ? '' : safeDisplayText(this._selected.text),
                -1
            );
        });
        window.set_child(layout);
        window.connect('close-request', () => {
            this._window = null;
            this.quit();
            return false;
        });
        window.present();
        if (firstRow !== null)
            list.select_row(firstRow);
    }

    _restoreSelected() {
        if (this._selected === null)
            return;
        try {
            writeAction(1, this._selected.id);
            this.quit();
        } catch (_error) {
            this._status.label = t('The recent clipboard action could not be returned safely.');
        }
    }

    _confirmClear() {
        if (!this._clearArmed) {
            this._clearArmed = true;
            this._clear.label = t('Click again: Clear all');
            this._status.label = t('Click again to clear all recent items from memory.');
            return;
        }
        try {
            writeAction(2, 0);
            this.quit();
        } catch (_error) {
            this._clearArmed = false;
            this._clear.label = t('Clear all');
            this._status.label = t('The recent clipboard action could not be returned safely.');
        }
    }
});

let entries;
try {
    entries = readInput();
} catch (_error) {
    System.exit(1);
}

const application = new RecentClipboardApplication(entries);
System.exit(application.run([]));
