import GLib from 'gi://GLib';

export const SYSTEM_BACKEND_PATH = '/usr/bin/cpb';

export function userBackendPath() {
    return GLib.build_filenamev([
        GLib.get_home_dir(),
        '.local',
        'share',
        'copypastebin',
        'venv',
        'bin',
        'cpb',
    ]);
}

export function isUsableBackend(path) {
    return typeof path === 'string' && path.startsWith('/') &&
        GLib.file_test(path, GLib.FileTest.IS_REGULAR) &&
        GLib.file_test(path, GLib.FileTest.IS_EXECUTABLE);
}

export function resolveBackendPath({
    systemPath = SYSTEM_BACKEND_PATH,
    userPath = userBackendPath(),
    isUsable = isUsableBackend,
} = {}) {
    if (isUsable(systemPath))
        return systemPath;
    if (isUsable(userPath))
        return userPath;
    return null;
}

export function backendCommand(...arguments_) {
    const path = resolveBackendPath();
    if (path === null)
        throw new Error('CopyPasteBin backend is unavailable.');
    return [path, ...arguments_];
}
