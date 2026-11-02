import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

export const EXTENSION_UUID = 'copypastebin@kozlowska-anna.github.io';
export const SYSTEM_EXTENSION_PATH =
    `/usr/share/gnome-shell/extensions/${EXTENSION_UUID}`;

export function userExtensionPath(home = GLib.get_home_dir()) {
    if (typeof home !== 'string' || !home.startsWith('/') || home === '/')
        return null;
    return GLib.build_filenamev([
        home, '.local', 'share', 'gnome-shell', 'extensions', EXTENSION_UUID,
    ]);
}

function pathState(path) {
    const file = Gio.File.new_for_path(path);
    try {
        file.query_info(
            'standard::type,standard::is-symlink',
            Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS,
            null
        );
        return 'present';
    } catch (error) {
        if (error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
            return 'absent';
        return 'error';
    }
}

export function detectExtensionChannelState({
    systemPath = SYSTEM_EXTENSION_PATH,
    userPath = userExtensionPath(),
} = {}) {
    if (typeof systemPath !== 'string' || !systemPath.startsWith('/') ||
        typeof userPath !== 'string' || !userPath.startsWith('/') ||
        systemPath === userPath)
        return {status: 'error'};
    const system = pathState(systemPath);
    const user = pathState(userPath);
    if (system === 'error' || user === 'error')
        return {status: 'error'};
    return {
        status: system === 'present' && user === 'present'
            ? 'conflict'
            : 'clear',
    };
}
