const PROTOCOL_VERSION = 1;
const MAX_FRAME_BYTES = 8192;
const MAX_TEXT_CHARACTERS = 4096;
const MAX_SEQUENCE = 0x7fffffff;
const SESSION_ID = /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/;
const ERROR_CODES = new Set(['audio-device', 'engine', 'protocol', 'worker']);
const KINDS = new Set(['ready', 'partial', 'final', 'stopped', 'error']);

export class DictationProtocolError extends Error {
    constructor() {
        super('Invalid dictation worker response.');
        this.name = 'DictationProtocolError';
    }
}

function exactKeys(object, expected) {
    const keys = Object.keys(object).sort();
    return keys.length === expected.length &&
        keys.every((key, index) => key === expected[index]);
}

function validInteger(value, minimum = 0) {
    return Number.isSafeInteger(value) && value >= minimum && value <= MAX_SEQUENCE;
}

export function parseDictationFrame(encoded) {
    if (typeof encoded !== 'string' ||
        new TextEncoder().encode(encoded).length > MAX_FRAME_BYTES)
        throw new DictationProtocolError();
    let frame;
    try {
        frame = JSON.parse(encoded);
    } catch (_error) {
        throw new DictationProtocolError();
    }
    if (frame === null || Array.isArray(frame) || typeof frame !== 'object' ||
        frame.version !== PROTOCOL_VERSION ||
        typeof frame.session_id !== 'string' || !SESSION_ID.test(frame.session_id) ||
        !validInteger(frame.sequence, 1) ||
        typeof frame.kind !== 'string' || !KINDS.has(frame.kind))
        throw new DictationProtocolError();

    if (frame.kind === 'partial' || frame.kind === 'final') {
        if (!exactKeys(frame, ['kind', 'segment', 'sequence', 'session_id', 'text', 'version']) ||
            !validInteger(frame.segment) || typeof frame.text !== 'string' ||
            frame.text.length > MAX_TEXT_CHARACTERS || frame.text.includes('\0') ||
            (frame.kind === 'final' && frame.text.length === 0))
            throw new DictationProtocolError();
    } else if (frame.kind === 'error') {
        if (!exactKeys(frame, ['code', 'kind', 'sequence', 'session_id', 'version']) ||
            typeof frame.code !== 'string' || !ERROR_CODES.has(frame.code))
            throw new DictationProtocolError();
    } else if (!exactKeys(frame, ['kind', 'sequence', 'session_id', 'version'])) {
        throw new DictationProtocolError();
    }
    return Object.freeze({...frame});
}

export class DictationSession {
    constructor({available = false, onState, onPartial, onFinal} = {}) {
        this._available = available === true;
        this._onState = typeof onState === 'function' ? onState : () => {};
        this._onPartial = typeof onPartial === 'function' ? onPartial : () => {};
        this._onFinal = typeof onFinal === 'function' ? onFinal : () => {};
        this._state = this._available ? 'idle' : 'unavailable';
        this._sessionId = null;
        this._lastSequence = 0;
        this._lastFinalSegment = -1;
        this._partialText = '';
    }

    get state() {
        return this._state;
    }

    get partialText() {
        return this._partialText;
    }

    start(sessionId) {
        if (!this._available || !SESSION_ID.test(sessionId) ||
            !['idle', 'error'].includes(this._state))
            return false;
        this._sessionId = sessionId;
        this._lastSequence = 0;
        this._lastFinalSegment = -1;
        this._setPartial('');
        this._setState('starting');
        return true;
    }

    stop() {
        if (!['starting', 'recording'].includes(this._state))
            return false;
        this._setState('stopping');
        return true;
    }

    cancel() {
        this._setPartial('');
        this._sessionId = null;
        this._lastSequence = 0;
        this._lastFinalSegment = -1;
        this._setState(this._available ? 'idle' : 'unavailable');
    }

    fail() {
        if (this._sessionId === null)
            return;
        this._setPartial('');
        this._sessionId = null;
        this._setState('error');
    }

    accept(encoded) {
        const frame = parseDictationFrame(encoded);
        if (this._sessionId === null || frame.session_id !== this._sessionId ||
            frame.sequence <= this._lastSequence)
            return false;
        this._lastSequence = frame.sequence;

        if (frame.kind === 'ready') {
            if (this._state !== 'starting')
                return false;
            this._setState('recording');
            return true;
        }
        if (frame.kind === 'partial') {
            if (this._state !== 'recording' || frame.segment <= this._lastFinalSegment)
                return false;
            this._setPartial(frame.text);
            return true;
        }
        if (frame.kind === 'final') {
            if (!['recording', 'stopping'].includes(this._state) ||
                frame.segment <= this._lastFinalSegment)
                return false;
            this._lastFinalSegment = frame.segment;
            this._setPartial('');
            this._onFinal(frame.text, frame.segment);
            return true;
        }
        if (frame.kind === 'stopped') {
            if (!['starting', 'recording', 'stopping'].includes(this._state))
                return false;
            this.cancel();
            return true;
        }
        this._setPartial('');
        this._sessionId = null;
        this._setState('error');
        return true;
    }

    _setState(state) {
        if (this._state === state)
            return;
        this._state = state;
        this._onState(state);
    }

    _setPartial(text) {
        if (this._partialText === text)
            return;
        this._partialText = text;
        this._onPartial(text);
    }
}
