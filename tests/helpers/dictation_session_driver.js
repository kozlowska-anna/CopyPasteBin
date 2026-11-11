import System from 'system';

import {
    DictationProtocolError,
    DictationSession,
    parseDictationFrame,
} from '../../gnome-extension/copypastebin@kozlowska-anna.github.io/dictation-session.js';

function frame(session, sequence, kind, extra = {}) {
    return JSON.stringify({
        version: 1,
        session_id: session,
        sequence,
        kind,
        ...extra,
    });
}

function runSession(action) {
    const states = [];
    const partials = [];
    const finals = [];
    let document = 'Początek.';
    const session = new DictationSession({
        available: true,
        onState: state => states.push(state),
        onPartial: text => partials.push(text),
        onFinal: text => {
            finals.push(text);
            document += ` ${text}`;
        },
    });
    session.start('synthetic-1');
    session.accept(frame('synthetic-1', 1, 'ready'));
    session.accept(frame('synthetic-1', 2, 'partial', {segment: 0, text: 'Ala'}));
    if (action === 'manual')
        document += ' [ręczna korekta]';
    session.accept(frame('synthetic-1', 3, 'partial', {segment: 0, text: 'Ala ma'}));
    if (action === 'cancel') {
        session.cancel();
        return {states, partials, finals, document, state: session.state};
    }
    if (action === 'error') {
        session.accept(frame('synthetic-1', 4, 'error', {code: 'engine'}));
        return {states, partials, finals, document, state: session.state};
    }
    session.accept(frame('synthetic-1', 4, 'final', {segment: 0, text: 'Ala ma kota.'}));
    session.accept(frame('synthetic-1', 4, 'final', {segment: 0, text: 'duplikat'}));
    session.accept(frame('old-session', 5, 'partial', {segment: 1, text: 'stare'}));
    session.stop();
    session.accept(frame('synthetic-1', 5, 'partial', {segment: 1, text: 'opóźnione'}));
    session.accept(frame('synthetic-1', 6, 'final', {segment: 1, text: 'Drugi segment.'}));
    session.accept(frame('synthetic-1', 7, 'stopped'));
    return {states, partials, finals, document, state: session.state};
}

try {
    const [action] = ARGV;
    if (['stream', 'manual', 'cancel', 'error'].includes(action)) {
        print(JSON.stringify(runSession(action)));
    } else if (action === 'invalid') {
        try {
            parseDictationFrame('{"version":1,"text":"private canary"}');
            throw new Error('invalid frame accepted');
        } catch (error) {
            if (!(error instanceof DictationProtocolError))
                throw error;
            print(error.message);
        }
    } else {
        throw new Error('unknown action');
    }
} catch (error) {
    printerr(error.message);
    System.exit(1);
}
