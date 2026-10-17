import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';
import {languageFromArgs, translate} from './i18n.js';

const LANGUAGE = languageFromArgs(ARGV);
const t = (message, values = {}) => translate(LANGUAGE, message, values);

const MAX_FILTERS_BYTES = 2048;
const FILTERS = new Map([
    ['EMAIL', 'E-mail'],
    ['PHONE', t('Phone number')],
    ['PESEL', 'PESEL'],
    ['IBAN', 'IBAN'],
    ['PAYMENT_CARD', t('Payment card')],
    ['RECOVERY_KEY', t('Recovery key (for example BitLocker)')],
    ['HOME_PATH', t('Home path')],
    ['IP_ADDRESS', t('IP address')],
    ['URL_CREDENTIALS', t('Credentials in a URL')],
    ['AUTHORIZATION', t('Authorization')],
    ['PRIVATE_KEY', t('Private key')],
    ['OPENAI_API_KEY', 'OpenAI API key'],
    ['ANTHROPIC_API_KEY', 'Anthropic API key'],
    ['GOOGLE_API_KEY', 'Google API key'],
    ['GITHUB_TOKEN', 'GitHub token'],
    ['SLACK_TOKEN', 'Slack token'],
    ['STRIPE_KEY', 'Stripe key'],
    ['AWS_ACCESS_KEY', 'AWS access key'],
    ['JWT', 'JWT'],
    ['DATABASE_URL', t('Database connection string')],
    ['TOKEN', 'Token'],
    ['SECRET_ASSIGNMENT', t('Secret or password')],
    ['POSSIBLE_SEED_PHRASE', t('Seed phrase')],
    ['MONEY_AMOUNT_PLN_USD', t('Traditional currency amounts')],
    ['CRYPTO_AMOUNT_BTC_XRP', t('Cryptocurrency amounts')],
    ['CUSTOM_RULE', t('Custom rules')],
]);
const ENTRY_POINT = GLib.build_filenamev([
    GLib.get_home_dir(),
    '.local',
    'share',
    'copypastebin',
    'venv',
    'bin',
    'cpb',
]);

const FilterApplication = GObject.registerClass(
class FilterApplication extends Gtk.Application {
    constructor() {
        super({application_id: 'io.github.copypastebin.FilterEditor'});
        this._process = null;
        this._checks = new Map();
        this._applying = false;
    }

    vfunc_activate() {
        this._window = new Gtk.ApplicationWindow({
            application: this,
            title: `CopyPasteBin — ${t('Detection filters')}`,
            default_width: 520,
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
            label: t('Enable or disable how CopyPasteBin responds to each type of data.'),
            wrap: true,
            xalign: 0,
        }));
        layout.append(new Gtk.Label({
            label: t('Changes are saved immediately and apply to future clipboard events.'),
            wrap: true,
            xalign: 0,
        }));

        const list = new Gtk.ListBox({selection_mode: Gtk.SelectionMode.NONE});
        for (const [category, label] of FILTERS) {
            const row = new Gtk.ListBoxRow();
            const check = new Gtk.CheckButton({
                label,
                margin_top: 8,
                margin_bottom: 8,
                margin_start: 10,
                margin_end: 10,
                sensitive: false,
            });
            check.connect('toggled', () => {
                if (!this._applying)
                    this._setFilter(category, check.active);
            });
            row.set_child(check);
            list.append(row);
            this._checks.set(category, check);
        }
        layout.append(new Gtk.ScrolledWindow({
            hexpand: true,
            vexpand: true,
            child: list,
        }));

        this._status = new Gtk.Label({
            label: t('Loading filters…'),
            wrap: true,
            xalign: 0,
        });
        layout.append(this._status);
        const close = new Gtk.Button({label: t('Close'), halign: Gtk.Align.END});
        close.connect('clicked', () => this._window.close());
        layout.append(close);

        this._window.set_child(layout);
        this._window.connect('close-request', () => {
            this._process?.force_exit();
            this.quit();
            return false;
        });
        this._window.present();
        this._run(['filters'], null);
    }

    _setBusy(busy) {
        for (const check of this._checks.values())
            check.sensitive = !busy;
    }

    _setFilter(category, enabled) {
        this._setBusy(true);
        this._status.label = t('Saving change…');
        this._run(['filter-set', category, enabled ? 'on' : 'off'], category);
    }

    _run(arguments_, changedCategory) {
        try {
            this._process = Gio.Subprocess.new(
                [ENTRY_POINT, 'ui', ...arguments_],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
            );
        } catch (_error) {
            this._failed();
            return;
        }
        this._process.communicate_utf8_async(null, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (!source.get_successful() ||
                    new TextEncoder().encode(stdout).length > MAX_FILTERS_BYTES)
                    throw new Error('closed filters failure');
                const states = this._parseFilters(stdout);
                this._apply(states);
                const enabledCount = [...states.values()].filter(value => value).length;
                this._status.label = changedCategory === null
                    ? t('Active filters: {enabled}/{total}.', {
                        enabled: enabledCount, total: FILTERS.size,
                    })
                    : `${FILTERS.get(changedCategory)}: ` +
                        `${t(states.get(changedCategory) ? 'enabled' : 'disabled')}. ` +
                        t('Active: {enabled}/{total}.', {
                            enabled: enabledCount, total: FILTERS.size,
                        });
                this._process = null;
                this._setBusy(false);
            } catch (_error) {
                this._failed();
            }
        });
    }

    _parseFilters(text) {
        const payload = JSON.parse(text);
        const expected = [...FILTERS.keys()];
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

    _apply(states) {
        this._applying = true;
        try {
            for (const [category, check] of this._checks)
                check.active = states.get(category);
        } finally {
            this._applying = false;
        }
    }

    _failed() {
        this._process = null;
        this._setBusy(true);
        this._status.label = t('Filters could not be read or saved safely.');
    }
});

const app = new FilterApplication();
System.exit(app.run([]));
