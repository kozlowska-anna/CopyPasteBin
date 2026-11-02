Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import GLib from 'gi://GLib';
import System from 'system';

import {BridgeWorker} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/bridge-worker.js';


const [entryPoint] = ARGV;
if (entryPoint === undefined)
    System.exit(2);

function frame(text) {
    const application = 'synthetic.gjs-worker';
    const app = new TextEncoder().encode(application);
    const content = new TextEncoder().encode(text);
    const payload = new Uint8Array(4 + app.length + content.length);
    payload[0] = (app.length >>> 24) & 0xff;
    payload[1] = (app.length >>> 16) & 0xff;
    payload[2] = (app.length >>> 8) & 0xff;
    payload[3] = app.length & 0xff;
    payload.set(app, 4);
    payload.set(content, 4 + app.length);
    return payload;
}

function document(result) {
    if (result.status !== 'ok')
        throw new Error('closed worker failure');
    return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(result.bytes));
}

const loop = new GLib.MainLoop(null, false);
const worker = new BridgeWorker(entryPoint);
worker.request(frame('person@example.invalid'), firstResult => {
    try {
        const first = document(firstResult);
        worker.request(frame('ordinary synthetic sentence'), secondResult => {
            try {
                const second = document(secondResult);
                print(JSON.stringify({first: first.risk, second: second.risk}));
                worker.destroy();
                GLib.timeout_add(GLib.PRIORITY_DEFAULT, 25, () => {
                    loop.quit();
                    return GLib.SOURCE_REMOVE;
                });
            } catch (_error) {
                worker.destroy();
                loop.quit();
                System.exit(1);
            }
        });
    } catch (_error) {
        worker.destroy();
        loop.quit();
        System.exit(1);
    }
});
loop.run();
