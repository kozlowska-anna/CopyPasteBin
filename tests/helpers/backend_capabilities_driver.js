Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import System from 'system';

import {parseBackendCapabilities} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/backend-path.js';

const [expectedProtocolText, rendered] = ARGV;
const expectedProtocol = Number(expectedProtocolText);
if (expectedProtocolText === undefined || rendered === undefined)
    System.exit(2);

try {
    const result = parseBackendCapabilities(rendered, {expectedProtocol});
    print(JSON.stringify(result));
} catch (_error) {
    print('INVALID');
}
