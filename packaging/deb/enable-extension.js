import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';

const UUID = 'copypastebin@kozlowska-anna.github.io';
const polish = (GLib.getenv('LANG') ?? '').toLowerCase().startsWith('pl');

function hasUserExtension() {
    const home = GLib.get_home_dir();
    if (home === null || home === '' || home === '/')
        return true;
    const extension = Gio.File.new_for_path(GLib.build_filenamev([
        home, '.local', 'share', 'gnome-shell', 'extensions', UUID,
    ]));
    try {
        extension.query_info(
            'standard::type,standard::is-symlink',
            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
            null
        );
        return true;
    } catch (error) {
        if (error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
            return false;
        return true;
    }
}

function message(successful, conflict) {
    if (conflict) {
        return polish
            ? [
                'Najpierw usuń kod instalacji archiwalnej',
                'Wykryto użytkownikowe rozszerzenie CopyPasteBin o tym samym identyfikatorze. Uruchom bieżący uninstall.sh z pakietu archiwalnego; ustawienia i historia zostaną zachowane. Następnie wyloguj się, zaloguj ponownie i ponów tę akcję.',
            ]
            : [
                'Remove the offline installation code first',
                'A user-local CopyPasteBin extension with the same identifier exists. Run the current archive uninstall.sh; settings and history will be preserved. Then log out, log back in, and retry this action.',
            ];
    }
    if (successful) {
        return polish
            ? ['CopyPasteBin włączony', 'Rozszerzenie włączono wyłącznie dla bieżącego konta.']
            : ['CopyPasteBin enabled', 'The extension was enabled only for the current account.'];
    }
    return polish
        ? ['Nie udało się włączyć CopyPasteBin', 'Wyloguj się, zaloguj ponownie do GNOME Wayland i spróbuj jeszcze raz.']
        : ['CopyPasteBin could not be enabled', 'Log out, log back in to GNOME Wayland, and try again.'];
}

const application = new Gtk.Application({
    application_id: 'io.github.copypastebin.Enable',
});

application.connect('activate', () => {
    application.hold();
    const conflict = hasUserExtension();
    let successful = false;
    if (!conflict) {
        try {
            const process = Gio.Subprocess.new(
                ['/usr/bin/gnome-extensions', 'enable', UUID],
                Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE
            );
            successful = process.wait_check(null);
        } catch (_error) {
            successful = false;
        }
    }
    const [title, detail] = message(successful, conflict);
    const dialog = new Gtk.MessageDialog({
        modal: true,
        message_type: successful ? Gtk.MessageType.INFO : Gtk.MessageType.ERROR,
        buttons: Gtk.ButtonsType.CLOSE,
        text: title,
        secondary_text: detail,
    });
    dialog.connect('response', () => {
        dialog.destroy();
        application.release();
    });
    dialog.present();
});

System.exit(application.run([]));
