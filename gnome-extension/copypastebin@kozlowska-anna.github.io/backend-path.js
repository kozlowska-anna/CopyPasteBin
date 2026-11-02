import GLib from 'gi://GLib';

export const SYSTEM_BACKEND_PATH = '/usr/bin/cpb';
export const BACKEND_PROTOCOL_VERSION = 2;
export const MAX_CAPABILITIES_BYTES = 512;

const PRODUCT_VERSION = /^[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}$/;

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
        !GLib.file_test(path, GLib.FileTest.IS_SYMLINK) &&
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

export function parseBackendCapabilities(rendered, {
    expectedProtocol = BACKEND_PROTOCOL_VERSION,
} = {}) {
    if (typeof rendered !== 'string' ||
        new TextEncoder().encode(rendered).length > MAX_CAPABILITIES_BYTES)
        throw new Error('Invalid CopyPasteBin backend capabilities.');
    let payload;
    try {
        payload = JSON.parse(rendered);
    } catch (_error) {
        throw new Error('Invalid CopyPasteBin backend capabilities.');
    }
    if (payload === null || typeof payload !== 'object' ||
        Array.isArray(payload) ||
        Object.keys(payload).sort().join(',') !==
            'document_version,product_version,protocol_version' ||
        payload.document_version !== 1 ||
        typeof payload.product_version !== 'string' ||
        !PRODUCT_VERSION.test(payload.product_version) ||
        !Number.isSafeInteger(payload.protocol_version) ||
        payload.protocol_version < 1 ||
        !Number.isSafeInteger(expectedProtocol) || expectedProtocol < 1)
        throw new Error('Invalid CopyPasteBin backend capabilities.');
    return {
        compatible: payload.protocol_version === expectedProtocol,
        productVersion: payload.product_version,
        protocolVersion: payload.protocol_version,
    };
}
