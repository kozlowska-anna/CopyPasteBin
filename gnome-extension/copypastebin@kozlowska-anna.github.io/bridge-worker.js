import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import {BACKEND_PROTOCOL_VERSION} from './backend-path.js';


export const WORKER_PROTOCOL_VERSION = 1;
export const MAX_WORKER_RESPONSE_BYTES = 2048;
export const WORKER_IO_TIMEOUT_MILLISECONDS = 5000;

const FRAME_HEADER_BYTES = 4;
const MAX_WORKER_REQUEST_BYTES = 4 + 128 + 10 * 1024 * 1024;
const PRODUCT_VERSION = /^[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}$/;


export class BridgeWorker {
    constructor(entryPoint, {
        timeoutMilliseconds = WORKER_IO_TIMEOUT_MILLISECONDS,
    } = {}) {
        if (typeof entryPoint !== 'string' || !entryPoint.startsWith('/') ||
            !Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds < 1)
            throw new Error('Invalid CopyPasteBin bridge worker.');
        this._entryPoint = entryPoint;
        this._timeoutMilliseconds = timeoutMilliseconds;
        this._generation = 0;
        this._process = null;
        this._stdin = null;
        this._stdout = null;
        this._cancellable = null;
        this._callback = null;
        this._timeoutId = 0;
        this._busy = false;
        this._destroyed = false;
    }

    request(frame, callback) {
        if (this._destroyed || this._busy || !(frame instanceof Uint8Array) ||
            frame.length < 1 || frame.length > MAX_WORKER_REQUEST_BYTES ||
            typeof callback !== 'function')
            throw new Error('Invalid CopyPasteBin bridge worker request.');
        this._busy = true;
        this._callback = callback;
        if (this._process === null)
            this._start(frame);
        else
            this._writeRequest(frame, this._generation);
    }

    get busy() {
        return this._busy;
    }

    cancelActive() {
        if (this._busy)
            this._stop();
    }

    stop() {
        this._stop();
    }

    destroy() {
        this._destroyed = true;
        this._stop();
    }

    _start(frame) {
        const generation = ++this._generation;
        this._cancellable = new Gio.Cancellable();
        try {
            this._process = Gio.Subprocess.new(
                [this._entryPoint, 'bridge', 'worker'],
                Gio.SubprocessFlags.STDIN_PIPE |
                    Gio.SubprocessFlags.STDOUT_PIPE |
                    Gio.SubprocessFlags.STDERR_SILENCE
            );
            this._stdin = this._process.get_stdin_pipe();
            this._stdout = this._process.get_stdout_pipe();
            this._process.wait_async(null, (source, result) => {
                try {
                    source.wait_finish(result);
                } catch (_error) {
                    // The closed result below is identical for every exit reason.
                }
                if (generation !== this._generation)
                    return;
                if (this._busy)
                    this._fail(generation);
                else
                    this._clearProcess(generation);
            });
        } catch (_error) {
            this._fail(generation);
            return;
        }
        this._armTimeout(generation);
        this._readDocument(generation, bytes => {
            try {
                this._parseHandshake(bytes);
            } catch (_error) {
                this._fail(generation);
                return;
            }
            this._writeRequest(frame, generation);
        });
    }

    _writeRequest(frame, generation) {
        this._armTimeout(generation);
        const request = new Uint8Array(FRAME_HEADER_BYTES + frame.length);
        request[0] = (frame.length >>> 24) & 0xff;
        request[1] = (frame.length >>> 16) & 0xff;
        request[2] = (frame.length >>> 8) & 0xff;
        request[3] = frame.length & 0xff;
        request.set(frame, FRAME_HEADER_BYTES);
        this._writeAll(request, 0, generation, () => {
            this._readDocument(generation, bytes => this._complete(generation, bytes));
        });
    }

    _writeAll(bytes, offset, generation, onComplete) {
        if (generation !== this._generation || this._stdin === null)
            return;
        this._stdin.write_bytes_async(
            new GLib.Bytes(bytes.slice(offset)),
            GLib.PRIORITY_DEFAULT,
            this._cancellable,
            (source, result) => {
                if (generation !== this._generation)
                    return;
                let written;
                try {
                    written = source.write_bytes_finish(result);
                } catch (_error) {
                    this._fail(generation);
                    return;
                }
                if (!Number.isSafeInteger(written) || written <= 0 ||
                    offset + written > bytes.length) {
                    this._fail(generation);
                    return;
                }
                const next = offset + written;
                if (next === bytes.length)
                    onComplete();
                else
                    this._writeAll(bytes, next, generation, onComplete);
            }
        );
    }

    _readDocument(generation, onDocument) {
        this._readExact(FRAME_HEADER_BYTES, generation, header => {
            const length = (
                header[0] * 0x1000000 +
                header[1] * 0x10000 +
                header[2] * 0x100 +
                header[3]
            );
            if (!Number.isSafeInteger(length) || length < 1 ||
                length > MAX_WORKER_RESPONSE_BYTES) {
                this._fail(generation);
                return;
            }
            this._readExact(length, generation, onDocument);
        });
    }

    _readExact(length, generation, onComplete, chunks = [], received = 0) {
        if (generation !== this._generation || this._stdout === null)
            return;
        this._stdout.read_bytes_async(
            length - received,
            GLib.PRIORITY_DEFAULT,
            this._cancellable,
            (source, result) => {
                if (generation !== this._generation)
                    return;
                let bytes;
                try {
                    bytes = source.read_bytes_finish(result).get_data();
                } catch (_error) {
                    this._fail(generation);
                    return;
                }
                if (bytes.length < 1 || received + bytes.length > length) {
                    this._fail(generation);
                    return;
                }
                chunks.push(bytes);
                const next = received + bytes.length;
                if (next !== length) {
                    this._readExact(length, generation, onComplete, chunks, next);
                    return;
                }
                const joined = new Uint8Array(length);
                let offset = 0;
                for (const chunk of chunks) {
                    joined.set(chunk, offset);
                    offset += chunk.length;
                }
                onComplete(joined);
            }
        );
    }

    _parseHandshake(bytes) {
        if (bytes.some(byte => byte > 0x7f))
            throw new Error('Invalid CopyPasteBin bridge worker handshake.');
        const rendered = String.fromCharCode(...bytes);
        const payload = JSON.parse(rendered);
        if (payload === null || typeof payload !== 'object' ||
            Array.isArray(payload) ||
            Object.keys(payload).sort().join(',') !==
                'document_version,product_version,protocol_version,worker_protocol_version' ||
            payload.document_version !== 1 ||
            typeof payload.product_version !== 'string' ||
            !PRODUCT_VERSION.test(payload.product_version) ||
            payload.protocol_version !== BACKEND_PROTOCOL_VERSION ||
            payload.worker_protocol_version !== WORKER_PROTOCOL_VERSION)
            throw new Error('Invalid CopyPasteBin bridge worker handshake.');
    }

    _armTimeout(generation) {
        this._clearTimeout();
        this._timeoutId = GLib.timeout_add(
            GLib.PRIORITY_DEFAULT,
            this._timeoutMilliseconds,
            () => {
                this._timeoutId = 0;
                this._fail(generation);
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _clearTimeout() {
        if (this._timeoutId !== 0) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
    }

    _complete(generation, bytes) {
        if (generation !== this._generation)
            return;
        this._clearTimeout();
        this._busy = false;
        const callback = this._callback;
        this._callback = null;
        callback?.({status: 'ok', bytes});
    }

    _fail(generation) {
        if (generation !== this._generation)
            return;
        const callback = this._callback;
        this._stop();
        callback?.({status: 'error'});
    }

    _clearProcess(generation) {
        if (generation !== this._generation)
            return;
        this._clearTimeout();
        this._process = null;
        this._stdin = null;
        this._stdout = null;
        this._cancellable = null;
    }

    _stop() {
        this._generation++;
        this._clearTimeout();
        this._callback = null;
        this._busy = false;
        this._cancellable?.cancel();
        try {
            this._stdin?.close(null);
        } catch (_error) {
            // A concurrent worker exit is harmless.
        }
        try {
            this._process?.force_exit();
        } catch (_error) {
            // A concurrent worker exit is harmless.
        }
        this._process = null;
        this._stdin = null;
        this._stdout = null;
        this._cancellable = null;
    }
}
