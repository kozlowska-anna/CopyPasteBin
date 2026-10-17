'use strict';

const {Gio} = imports.gi;

const UUID = 'copypastebin@kozlowska-anna.github.io';
const LEGACY_UUID = 'copypastebin@local';
const KEY = 'enabled-extensions';

const settings = new Gio.Settings({schema_id: 'org.gnome.shell'});
if (!settings.is_writable(KEY))
    throw new Error('GNOME extension enablement is not writable');

const enabled = settings.get_strv(KEY);
const updated = enabled.filter(value => value !== UUID && value !== LEGACY_UUID);
updated.push(UUID);

if (!settings.set_strv(KEY, updated))
    throw new Error('GNOME extension enablement was not saved');

Gio.Settings.sync();
