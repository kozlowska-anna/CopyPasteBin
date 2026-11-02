import GLib from 'gi://GLib';
import System from 'system';

import {BridgeWorker} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/bridge-worker.js';


const [entryPoint, timeoutText, mode = 'request'] = ARGV;
const timeout = Number.parseInt(timeoutText, 10);
if (entryPoint === undefined || !Number.isSafeInteger(timeout))
    System.exit(2);

const loop = new GLib.MainLoop(null, false);
const worker = new BridgeWorker(entryPoint, {timeoutMilliseconds: timeout});
let called = false;
worker.request(new Uint8Array([0, 0, 0, 1, 97, 120]), result => {
    called = true;
    print(result.status.toUpperCase());
    worker.destroy();
    loop.quit();
});
if (mode === 'cancel') {
    worker.cancelActive();
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.min(200, timeout), () => {
        if (!called)
            print('CANCELLED');
        worker.destroy();
        loop.quit();
        return GLib.SOURCE_REMOVE;
    });
}
loop.run();
