import Gio from 'gi://Gio';
import GioUnix from 'gi://GioUnix?version=2.0';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';
import {backendCommand} from './backend-path.js';
import {languageFromArgs, translate} from './i18n.js';

const SUGGEST_EXCLUSION = ARGV.includes('--suggest-exclusion');
const LANGUAGE = languageFromArgs(ARGV.filter(argument =>
    argument === '--language=pl' || argument === '--language=en'
));
const t = (message, values = {}) => translate(LANGUAGE, message, values);

const MAX_RULES = 32;
const MAX_EXCLUSIONS = 32;
const MAX_RULES_BYTES = 64 * 1024;
const MAX_SUGGESTION_BYTES = 512;
const EXCLUDABLE_CATEGORIES = new Map([
    ['EMAIL', 'Email address'],
    ['PHONE', 'Phone number'],
    ['IBAN', 'IBAN'],
    ['HOME_PATH', 'Home path'],
    ['IP_ADDRESS', 'IP address'],
    ['MONEY_AMOUNT_PLN_USD', 'Currency amount'],
    ['CRYPTO_AMOUNT_BTC_XRP', 'Cryptocurrency amount'],
]);
function readSuggestedExclusion() {
    if (!SUGGEST_EXCLUSION)
        return null;
    if (ARGV.length !== 2 ||
        ARGV.some(argument => argument !== '--suggest-exclusion' &&
            argument !== '--language=pl' && argument !== '--language=en'))
        throw new Error('closed exclusion suggestion failure');
    const stream = new GioUnix.InputStream({fd: 0, close_fd: false});
    const chunks = [];
    let total = 0;
    while (true) {
        const chunk = stream.read_bytes(256, null).get_data();
        if (chunk.length === 0)
            break;
        total += chunk.length;
        if (total > MAX_SUGGESTION_BYTES)
            throw new Error('closed exclusion suggestion failure');
        chunks.push(chunk);
    }
    const input = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
        input.set(chunk, offset);
        offset += chunk.length;
    }
    const text = new TextDecoder('utf-8', {fatal: true}).decode(input);
    const payload = JSON.parse(text);
    if (payload === null || typeof payload !== 'object' ||
        Object.keys(payload).sort().join(',') !== 'category,literal' ||
        typeof payload.literal !== 'string' ||
        typeof payload.category !== 'string' ||
        !EXCLUDABLE_CATEGORIES.has(payload.category))
        throw new Error('closed exclusion suggestion failure');
    const length = Array.from(payload.literal).length;
    if (length < 3 || length > 128 || /[\p{Cc}\p{Cf}]/u.test(payload.literal))
        throw new Error('closed exclusion suggestion failure');
    return payload;
}

const RulesApplication = GObject.registerClass(
class RulesApplication extends Gtk.Application {
    constructor(suggestedExclusion) {
        super({application_id: 'io.github.copypastebin.RulesEditor'});
        this._suggestedExclusion = suggestedExclusion;
        this._process = null;
        this._rows = [];
        this._sections = {};
        this._available = false;
        this._saving = false;
    }

    vfunc_activate() {
        this._window = new Gtk.ApplicationWindow({
            application: this,
            title: `CopyPasteBin — ${t('Rules and exceptions')}`,
            default_width: 1180,
            default_height: 620,
        });
        const layout = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 10,
            margin_top: 14,
            margin_bottom: 14,
            margin_start: 14,
            margin_end: 14,
        });
        layout.append(new Gtk.Label({
            label: t('A rule reacts to the exact text you enter. Do not enter a real password, key, or other secret here — rules are stored locally.'),
            wrap: true,
            xalign: 0,
        }));
        layout.append(new Gtk.Label({
            label: t('Use stable, non-secret markers, such as an internal document label.'),
            wrap: true,
            xalign: 0,
        }));
        layout.append(new Gtk.Label({
            label: t('An exception suppresses only a match with exactly the same text and range. Matching is case-sensitive. Do not add real sensitive data as an exception.'),
            wrap: true,
            xalign: 0,
        }));

        const columns = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 16,
            hexpand: true,
            vexpand: true,
        });
        columns.append(this._createColumn('rule', t('Custom rules')));
        columns.append(this._createColumn('exclusion', t('Exceptions')));
        layout.append(columns);

        this._status = new Gtk.Label({
            label: t('Loading rules…'),
            wrap: true,
            xalign: 0,
        });
        layout.append(this._status);

        const actions = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 8,
        });
        const spacer = new Gtk.Box({hexpand: true});
        actions.append(spacer);
        const cancel = new Gtk.Button({label: t('Close')});
        cancel.connect('clicked', () => this._window.close());
        actions.append(cancel);
        this._save = new Gtk.Button({label: t('Save'), sensitive: false});
        this._save.add_css_class('suggested-action');
        this._save.connect('clicked', () => this._saveRules());
        actions.append(this._save);
        layout.append(actions);

        this._window.set_child(layout);
        this._window.connect('close-request', () => {
            this._process?.force_exit();
            this.quit();
            return false;
        });
        this._window.present();
        this._loadRules();
    }

    _createColumn(kind, title) {
        const column = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 8,
            hexpand: true,
            vexpand: true,
        });
        const heading = new Gtk.Label({label: title, xalign: 0});
        heading.add_css_class('title-3');
        column.append(heading);

        const content = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 6,
        });
        const activeLabel = new Gtk.Label({label: t('Active ({count})', {count: 0}), xalign: 0});
        activeLabel.add_css_class('heading');
        const activeList = new Gtk.ListBox({
            selection_mode: Gtk.SelectionMode.NONE,
        });
        const inactiveLabel = new Gtk.Label({
            label: t('Inactive ({count})', {count: 0}),
            xalign: 0,
            margin_top: 6,
        });
        inactiveLabel.add_css_class('heading');
        const inactiveList = new Gtk.ListBox({
            selection_mode: Gtk.SelectionMode.NONE,
        });
        content.append(activeLabel);
        content.append(activeList);
        content.append(new Gtk.Separator({
            orientation: Gtk.Orientation.HORIZONTAL,
        }));
        content.append(inactiveLabel);
        content.append(inactiveList);
        const scroller = new Gtk.ScrolledWindow({
            hexpand: true,
            vexpand: true,
            child: content,
        });
        column.append(scroller);

        const add = new Gtk.Button({
            label: t(kind === 'rule' ? 'Add rule' : 'Add an exception'),
            sensitive: false,
        });
        if (kind === 'rule') {
            this._add = add;
            add.connect(
                'clicked',
                () => this._appendRule('', 'medium', true, true)
            );
        } else {
            this._addExclusion = add;
            add.connect(
                'clicked',
                () => this._appendExclusion('', 'EMAIL', true, true)
            );
        }
        column.append(add);
        this._sections[kind] = {
            active: {label: activeLabel, list: activeList},
            inactive: {label: inactiveLabel, list: inactiveList},
        };
        return column;
    }

    _refreshInteractivity() {
        const rules = this._rows.filter(row => row._kind === 'rule').length;
        const exclusions = this._rows.filter(
            row => row._kind === 'exclusion'
        ).length;
        this._add.sensitive = this._available && rules < MAX_RULES;
        this._addExclusion.sensitive =
            this._available && exclusions < MAX_EXCLUSIONS;
        this._save.sensitive = this._available;
        const controls = [this._add, this._addExclusion, this._save];
        for (const row of this._rows) {
            row._enabled.sensitive = this._available;
            row._literal.sensitive = this._available;
            if (row._risk)
                row._risk.sensitive = this._available;
            if (row._category)
                row._category.sensitive = this._available;
            row._remove.sensitive = this._available;
            controls.push(
                row._enabled,
                row._literal,
                row._risk ?? row._category,
                row._remove
            );
        }
        const interactive = this._available && !this._saving;
        for (const control of controls) {
            control.can_target = interactive;
            control.focusable = interactive;
        }
    }

    _setAvailable(available) {
        this._available = available;
        this._refreshInteractivity();
    }

    _setSaving(saving) {
        this._saving = saving;
        this._refreshInteractivity();
    }

    _loadRules() {
        this._setAvailable(false);
        try {
            this._process = Gio.Subprocess.new(
                backendCommand('ui', 'rules'),
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._loadFailed();
            return;
        }
        this._process.communicate_utf8_async(null, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_RULES_BYTES)
                    throw new Error('closed rules failure');
                const customization = this._parseRules(stdout);
                for (const rule of customization.rules)
                    this._appendRule(rule.literal, rule.risk, rule.enabled, false);
                for (const exclusion of customization.exclusions)
                    this._appendExclusion(
                        exclusion.literal,
                        exclusion.category,
                        exclusion.enabled,
                        false
                    );
                this._process = null;
                this._setAvailable(true);
                this._applySuggestedExclusion();
            } catch (_error) {
                this._loadFailed();
            }
        });
    }

    _applySuggestedExclusion() {
        if (this._suggestedExclusion === null) {
            this._updateStatus(t('Loaded'));
            return;
        }
        const {literal, category} = this._suggestedExclusion;
        this._suggestedExclusion = null;
        const existing = this._rows.find(row => row._literal.text === literal);
        if (existing !== undefined) {
            if (existing._kind === 'rule') {
                existing._literal.grab_focus();
                this._updateStatus(t('The proposed value already exists as a custom rule and cannot also be an exception.'));
                return;
            }
            if (!existing._enabled.active)
                existing._enabled.active = true;
            existing._literal.grab_focus();
            this._updateStatus(t('This exception already exists. Review it and click Save if its state changed.'));
            return;
        }
        const exclusions = this._rows.filter(row => row._kind === 'exclusion').length;
        if (exclusions >= MAX_EXCLUSIONS) {
            this._updateStatus(t('The exception limit has been reached. Remove an entry before adding another one.'));
            return;
        }
        this._appendExclusion(literal, category, true, true);
        this._updateStatus(t('A proposed exception was added to the form. Review the exact value and click Save to stop future warnings for it.'));
    }

    _parseRules(text) {
        const payload = JSON.parse(text);
        if (payload === null || typeof payload !== 'object' ||
            Object.keys(payload).sort().join(',') !==
                'exclusions,max_exclusions,max_rules,rules,version' ||
            payload.version !== 3 || payload.max_rules !== MAX_RULES ||
            payload.max_exclusions !== MAX_EXCLUSIONS ||
            !Array.isArray(payload.rules) || payload.rules.length > MAX_RULES ||
            !Array.isArray(payload.exclusions) ||
            payload.exclusions.length > MAX_EXCLUSIONS)
            throw new Error('closed rules failure');
        const literals = new Set();
        const rules = payload.rules.map(rule => {
            if (rule === null || typeof rule !== 'object' ||
                Object.keys(rule).sort().join(',') !== 'enabled,literal,risk' ||
                typeof rule.literal !== 'string' ||
                rule.literal.length < 3 || rule.literal.length > 128 ||
                !['low', 'medium', 'high', 'critical'].includes(rule.risk) ||
                typeof rule.enabled !== 'boolean' ||
                literals.has(rule.literal))
                throw new Error('closed rules failure');
            literals.add(rule.literal);
            return {literal: rule.literal, risk: rule.risk, enabled: rule.enabled};
        });
        const exclusions = payload.exclusions.map(exclusion => {
            if (exclusion === null || typeof exclusion !== 'object' ||
                Object.keys(exclusion).sort().join(',') !== 'category,enabled,literal' ||
                typeof exclusion.literal !== 'string' ||
                exclusion.literal.length < 3 || exclusion.literal.length > 128 ||
                typeof exclusion.category !== 'string' ||
                !EXCLUDABLE_CATEGORIES.has(exclusion.category) ||
                typeof exclusion.enabled !== 'boolean' ||
                literals.has(exclusion.literal))
                throw new Error('closed rules failure');
            literals.add(exclusion.literal);
            return {
                literal: exclusion.literal,
                category: exclusion.category,
                enabled: exclusion.enabled,
            };
        });
        return {rules, exclusions};
    }

    _appendRule(literal, risk, enabled, focus) {
        this._appendRow('rule', literal, risk, enabled, focus);
    }

    _appendExclusion(literal, category, enabled, focus) {
        this._appendRow('exclusion', literal, category, enabled, focus);
    }

    _appendRow(kind, literal, risk, enabled, focus) {
        const limit = kind === 'rule' ? MAX_RULES : MAX_EXCLUSIONS;
        const count = this._rows.filter(row => row._kind === kind).length;
        if (count >= limit) {
            const label = t(kind === 'rule' ? 'rules' : 'exceptions');
            this._status.label = t('You can save at most {limit} {kind}.', {
                limit, kind: label,
            });
            return;
        }
        const row = new Gtk.ListBoxRow();
        row._kind = kind;
        const content = new Gtk.Box({
            orientation: Gtk.Orientation.HORIZONTAL,
            spacing: 8,
            margin_top: 6,
            margin_bottom: 6,
            margin_start: 6,
            margin_end: 6,
        });
        row._enabled = new Gtk.CheckButton({
            active: enabled,
            tooltip_text: kind === 'rule'
                ? t('Uncheck to keep the rule without detecting it')
                : t('Uncheck to keep the exception without applying it'),
        });
        row._enabled.connect(
            'toggled',
            () => this._moveRowToStateSection(row)
        );
        row._literal = new Gtk.Entry({
            text: literal,
            placeholder_text: kind === 'rule'
                ? t('Detected text (3–128 characters)')
                : t('Exception text (3–128 characters)'),
            hexpand: true,
        });
        row._risk = null;
        row._category = null;
        let kindControl = null;
        if (kind === 'rule') {
            row._risk = new Gtk.ComboBoxText();
            row._risk.append('low', t('low risk'));
            row._risk.append('medium', t('medium risk'));
            row._risk.append('high', t('high risk'));
            row._risk.append('critical', t('critical risk'));
            row._risk.set_active_id(risk);
            kindControl = row._risk;
        } else {
            row._category = new Gtk.ComboBoxText();
            for (const [identifier, label] of EXCLUDABLE_CATEGORIES)
                row._category.append(identifier, t(label));
            row._category.set_active_id(risk);
            kindControl = row._category;
        }
        row._remove = new Gtk.Button({label: t('Remove')});
        row._remove.add_css_class('destructive-action');
        row._remove.connect('clicked', () => this._removeRule(row));
        content.append(row._enabled);
        content.append(row._literal);
        if (kindControl)
            content.append(kindControl);
        content.append(row._remove);
        row.set_child(content);
        row._state = enabled ? 'active' : 'inactive';
        this._sections[kind][row._state].list.append(row);
        this._rows.push(row);
        this._refreshInteractivity();
        this._updateStatus();
        if (focus)
            row._literal.grab_focus();
    }

    _removeRule(row) {
        const index = this._rows.indexOf(row);
        if (index < 0)
            return;
        this._rows.splice(index, 1);
        this._sections[row._kind][row._state].list.remove(row);
        this._refreshInteractivity();
        this._updateStatus();
    }

    _moveRowToStateSection(row) {
        const state = row._enabled.active ? 'active' : 'inactive';
        if (state === row._state)
            return;
        this._sections[row._kind][row._state].list.remove(row);
        this._sections[row._kind][state].list.append(row);
        row._state = state;
        this._updateStatus();
    }

    _updateStatus(prefix = '') {
        const rules = this._rows.filter(row => row._kind === 'rule').length;
        const exclusions = this._rows.filter(
            row => row._kind === 'exclusion'
        ).length;
        for (const kind of ['rule', 'exclusion']) {
            const active = this._rows.filter(
                row => row._kind === kind && row._enabled.active
            ).length;
            const inactive = this._rows.filter(
                row => row._kind === kind && !row._enabled.active
            ).length;
            this._sections[kind].active.label.label =
                t('Active ({count})', {count: active});
            this._sections[kind].inactive.label.label =
                t('Inactive ({count})', {count: inactive});
        }
        const lead = prefix ? `${prefix}. ` : '';
        this._status.label =
            lead + t('Rules: {rules}/{maxRules}; exceptions: {exceptions}/{maxExceptions}.', {
                rules, maxRules: MAX_RULES, exceptions: exclusions,
                maxExceptions: MAX_EXCLUSIONS,
            });
    }

    _collectRules() {
        const rules = [];
        const exclusions = [];
        const literals = new Set();
        for (const row of this._rows) {
            const literal = row._literal.text;
            const enabled = row._enabled.active;
            if (literal.length < 3 || literal.length > 128 ||
                /[\p{Cc}\p{Cf}]/u.test(literal))
                throw new Error(t('Each entry must contain 3 to 128 ordinary characters.'));
            if (literals.has(literal))
                throw new Error(t('Each detected or exception text can appear only once.'));
            literals.add(literal);
            if (row._kind === 'rule') {
                const risk = row._risk.get_active_id();
                if (!['low', 'medium', 'high', 'critical'].includes(risk))
                    throw new Error(t('Select a risk level for every rule.'));
                rules.push({literal, risk, enabled});
            } else {
                const category = row._category.get_active_id();
                if (!EXCLUDABLE_CATEGORIES.has(category))
                    throw new Error(t('Select a category for every exception.'));
                exclusions.push({literal, category, enabled});
            }
        }
        return {rules, exclusions};
    }

    _saveRules() {
        let rules;
        let exclusions;
        let payload;
        try {
            ({rules, exclusions} = this._collectRules());
            payload = JSON.stringify({version: 3, rules, exclusions});
            if (new TextEncoder().encode(payload).length > MAX_RULES_BYTES)
                throw new Error(t('The combined rules are too large.'));
        } catch (error) {
            this._status.label = error.message;
            return;
        }
        this._setSaving(true);
        this._status.label = t('Saving rules…');
        try {
            this._process = Gio.Subprocess.new(
                backendCommand('ui', 'rules-save'),
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._saveFailed();
            return;
        }
        this._process.communicate_utf8_async(payload, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_RULES_BYTES)
                    throw new Error('closed rules failure');
                const saved = this._parseRules(stdout);
                if (JSON.stringify(saved) !==
                    JSON.stringify({rules, exclusions}))
                    throw new Error('closed rules failure');
                this._process = null;
                this._setSaving(false);
                this._updateStatus(t('Saved'));
            } catch (_error) {
                this._saveFailed();
            }
        });
    }

    _loadFailed() {
        this._process = null;
        this._setAvailable(false);
        this._status.label = t('Rules could not be loaded safely.');
    }

    _saveFailed() {
        this._process = null;
        this._setSaving(false);
        this._status.label = t('Rules could not be saved safely.');
    }
});

let suggestedExclusion;
try {
    suggestedExclusion = readSuggestedExclusion();
} catch (_error) {
    System.exit(1);
}
const app = new RulesApplication(suggestedExclusion);
System.exit(app.run([]));
