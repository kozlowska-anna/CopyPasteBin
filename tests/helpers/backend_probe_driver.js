Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import GLib from 'gi://GLib';
import System from 'system';

import {BackendProbe} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/backend-probe.js';

const [entryPoint, timeoutText, mode = 'run'] = ARGV;
const timeoutMilliseconds = Number(timeoutText);
if (entryPoint === undefined || !Number.isSafeInteger(timeoutMilliseconds))
    System.exit(2);

const loop = GLib.MainLoop.new(null, false);
let callbackCalled = false;
const probe = new BackendProbe(
    entryPoint,
    result => {
        callbackCalled = true;
        print(JSON.stringify(result));
        loop.quit();
    },
    {timeoutMilliseconds}
);
probe.start();

if (mode === 'destroy') {
    probe.destroy();
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
        print(callbackCalled ? 'CALLBACK' : 'DESTROYED');
        loop.quit();
        return GLib.SOURCE_REMOVE;
    });
}

loop.run();
