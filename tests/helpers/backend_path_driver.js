import System from 'system';

import {resolveBackendPath} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/backend-path.js';

const [systemPath, userPath, ...available] = ARGV;
if (systemPath === undefined || userPath === undefined)
    System.exit(2);

const availablePaths = new Set(available);
const resolved = resolveBackendPath({
    systemPath,
    userPath,
    isUsable: path => availablePaths.has(path),
});
print(resolved ?? 'NONE');
