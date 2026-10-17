import GLib from 'gi://GLib';
import GLibUnix from 'gi://GLibUnix?version=2.0';
import GObject from 'gi://GObject';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';
import {languageFromArgs, translate} from './i18n.js';

const LANGUAGE = languageFromArgs(ARGV);
const t = (message, values = {}) => translate(LANGUAGE, message, values);
const VERSION = '1.0.0';

function informationLabel(label, options = {}) {
    return new Gtk.Label({
        label,
        wrap: true,
        justify: Gtk.Justification.CENTER,
        xalign: 0.5,
        selectable: options.selectable ?? false,
        margin_top: options.marginTop ?? 0,
    });
}

const AboutApplication = GObject.registerClass(
class AboutApplication extends Gtk.Application {
    constructor() {
        super({application_id: 'io.github.copypastebin.About'});
        this._window = null;
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
        if (this._window !== null) {
            this._window.present();
            return;
        }
        const window = new Gtk.ApplicationWindow({
            application: this,
            title: t('About CopyPasteBin'),
            default_width: 560,
            resizable: false,
        });
        this._window = window;
        const layout = new Gtk.Box({
            orientation: Gtk.Orientation.VERTICAL,
            spacing: 10,
            margin_top: 24,
            margin_bottom: 20,
            margin_start: 28,
            margin_end: 28,
        });
        layout.append(new Gtk.Image({
            icon_name: 'copypastebin',
            pixel_size: 72,
            margin_bottom: 4,
        }));
        const name = informationLabel('CopyPasteBin');
        name.add_css_class('title-1');
        layout.append(name);
        layout.append(informationLabel(t('Version {version}', {version: VERSION})));
        layout.append(informationLabel(
            t('CopyPasteBin helps stop sensitive text before it is shared with the wrong recipient.'),
            {marginTop: 8}
        ));
        layout.append(informationLabel(
            t('Works locally, without cloud services or telemetry.')
        ));
        layout.append(new Gtk.Separator({
            orientation: Gtk.Orientation.HORIZONTAL,
            margin_top: 8,
            margin_bottom: 4,
        }));
        layout.append(informationLabel(t('Author: Anna Kozłowska'), {selectable: true}));
        layout.append(informationLabel('Copyright © 2026 Anna Kozłowska', {
            selectable: true,
        }));
        layout.append(informationLabel(t('License: GPL-3.0-or-later'), {
            selectable: true,
        }));
        layout.append(informationLabel(
            t('The complete license text is included with the distribution.')
        ));
        layout.append(informationLabel(
            t('Development supported using ChatGPT and Codex from OpenAI.')
        ));
        layout.append(informationLabel(
            t('CopyPasteBin is an independent project. It is not an official OpenAI product and is not sponsored by OpenAI.')
        ));
        layout.append(informationLabel(
            t('Supported environment: GNOME Shell 50 on Wayland.'),
            {marginTop: 8}
        ));
        const limitation = informationLabel(
            t('The absence of a warning does not guarantee that text is safe.')
        );
        limitation.add_css_class('dim-label');
        layout.append(limitation);
        const warranty = informationLabel(
            t('This program comes with no warranty, to the extent permitted by law.')
        );
        warranty.add_css_class('dim-label');
        layout.append(warranty);
        const close = new Gtk.Button({
            label: t('Close'),
            halign: Gtk.Align.END,
            margin_top: 10,
        });
        close.connect('clicked', () => window.close());
        layout.append(close);
        window.set_child(layout);
        window.connect('close-request', () => {
            this._window = null;
            this.quit();
            return false;
        });
        window.present();
    }

    vfunc_shutdown() {
        if (this._presentSignalId !== 0) {
            GLib.source_remove(this._presentSignalId);
            this._presentSignalId = 0;
        }
        super.vfunc_shutdown();
    }
});

const application = new AboutApplication();
const status = application.run([]);
System.exit(status);
