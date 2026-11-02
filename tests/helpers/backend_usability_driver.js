Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import System from 'system';

import {isUsableBackend} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/backend-path.js';

const [path] = ARGV;
if (path === undefined)
    System.exit(2);
print(isUsableBackend(path) ? 'USABLE' : 'UNUSABLE');
