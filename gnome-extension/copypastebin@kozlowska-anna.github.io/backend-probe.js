Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {
    MAX_CAPABILITIES_BYTES,
    parseBackendCapabilities,
} from './backend-path.js';

export const BACKEND_PROBE_TIMEOUT_MILLISECONDS = 3000;

export class BackendProbe {
    constructor(entryPoint, onResult, {
        timeoutMilliseconds = BACKEND_PROBE_TIMEOUT_MILLISECONDS,
    } = {}) {
        if (typeof entryPoint !== 'string' || !entryPoint.startsWith('/') ||
            typeof onResult !== 'function' ||
            !Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds < 1)
            throw new Error('Invalid CopyPasteBin backend probe.');
        this._entryPoint = entryPoint;
        this._onResult = onResult;
        this._timeoutMilliseconds = timeoutMilliseconds;
        this._process = null;
        this._cancellable = null;
        this._stdout = null;
        this._output = [];
        this._timeoutId = 0;
        this._started = false;
        this._completed = false;
    }

    start() {
        if (this._started || this._completed)
            throw new Error('CopyPasteBin backend probe already started.');
        this._started = true;
        this._cancellable = new Gio.Cancellable();
        try {
            this._process = Gio.Subprocess.new(
                [this._entryPoint, 'bridge', 'capabilities'],
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
            this._process.get_stdin_pipe().close(null);
            this._stdout = this._process.get_stdout_pipe();
        } catch (_error) {
            this._terminateProcess();
            this._finish({status: 'error'});
            return;
        }
        this._timeoutId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            this._timeoutMilliseconds,
            () => {
                this._timeoutId = 0;
                this._terminateProcess();
                this._finish({status: 'error'});
                return GLib.SOURCE_REMOVE;
            }
        );
        this._readNextChunk();
    }

    _readNextChunk() {
        const remaining = MAX_CAPABILITIES_BYTES + 1 - this._output.length;
        this._stdout.read_bytes_async(
            remaining,
            GLib.PRIORITY_DEFAULT,
            this._cancellable,
            (source, result) => {
                if (this._completed)
                    return;
                let bytes;
                try {
                    bytes = source.read_bytes_finish(result).get_data();
                } catch (_error) {
                    this._terminateProcess();
                    this._finish({status: 'error'});
                    return;
                }
                if (bytes.length === 0) {
                    this._waitForExit();
                    return;
                }
                for (const byte of bytes)
                    this._output.push(byte);
                if (this._output.length > MAX_CAPABILITIES_BYTES) {
                    this._terminateProcess();
                    this._finish({status: 'error'});
                    return;
                }
                this._readNextChunk();
            }
        );
    }

    _waitForExit() {
        this._process.wait_check_async(this._cancellable, (source, result) => {
            if (this._completed)
                return;
            try {
                if (!source.wait_check_finish(result) ||
                    this._output.some(byte => byte > 0x7f))
                    throw new Error('Closed backend probe failure.');
                const rendered = String.fromCharCode(...this._output);
                const capabilities = parseBackendCapabilities(rendered);
                this._finish({
                    status: capabilities.compatible ? 'compatible' : 'incompatible',
                    productVersion: capabilities.productVersion,
                    protocolVersion: capabilities.protocolVersion,
                });
            } catch (_error) {
                this._finish({status: 'error'});
            }
        });
    }

    _terminateProcess() {
        this._cancellable?.cancel();
        try {
            this._process?.force_exit();
        } catch (_error) {
            // The process may already have exited between callbacks.
        }
    }

    _clearTimeout() {
        if (this._timeoutId !== 0) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
    }

    _finish(result) {
        if (this._completed)
            return;
        this._completed = true;
        this._clearTimeout();
        this._stdout = null;
        this._process = null;
        this._cancellable = null;
        const callback = this._onResult;
        this._onResult = null;
        callback?.(result);
    }

    destroy() {
        if (this._completed)
            return;
        this._completed = true;
        this._onResult = null;
        this._clearTimeout();
        this._terminateProcess();
        this._stdout = null;
        this._process = null;
        this._cancellable = null;
        this._output.length = 0;
    }
}
