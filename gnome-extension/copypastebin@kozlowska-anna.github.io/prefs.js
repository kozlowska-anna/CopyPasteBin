import Adw from 'gi://Adw';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';
import {translate} from './i18n.js';

const EDITOR_SHORTCUT_KEY = 'open-editor';
const SHORTCUT_VALUES = [[], ['<Super><Shift>e']];

function systemLanguage() {
    return GLib.get_language_names().some(name =>
        name.toLowerCase().startsWith('pl')) ? 'pl' : 'en';
}

export default class CopyPasteBinPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const language = systemLanguage();
        const t = message => translate(language, message);
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({
            title: t('Keyboard shortcut'),
            description: t('No shortcut is enabled by default.'),
        });
        const row = new Adw.ComboRow({
            title: t('Open clipboard editor'),
            subtitle: t('Enable the recommended Super+Shift+E only after checking that it does not conflict with another action.'),
            model: Gtk.StringList.new([
                t('Disabled'),
                'Super+Shift+E',
            ]),
        });

        const configured = settings.get_strv(EDITOR_SHORTCUT_KEY);
        const selected = SHORTCUT_VALUES.findIndex(value =>
            value.length === configured.length &&
            value.every((shortcut, index) => shortcut === configured[index]));
        row.selected = selected < 0 ? 0 : selected;

        row.connect('notify::selected', () => {
            const selected = SHORTCUT_VALUES[row.selected] ?? [];
            settings.set_strv(EDITOR_SHORTCUT_KEY, selected);
        });
        group.add(row);
        page.add(group);
        window.add(page);
    }
}
