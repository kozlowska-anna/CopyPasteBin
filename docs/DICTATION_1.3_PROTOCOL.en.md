# CopyPasteBin 1.3 — dictation protocol and safe integration

Status: C1–C3 prototype implemented without microphone access  
Date: 2026-11-11

This document describes the current code and the boundary for further
integration. The prototype does not install an engine or model, open an audio
device, use the network, or change the clipboard without the existing explicit
confirmation button.

## Implementation status

- `dictation-session.js` validates a closed frame protocol and maintains the
  `unavailable`, `idle`, `starting`, `recording`, `stopping`, and `error`
  states.
- The editor has a visible microphone button and a local
  `Gtk.ShortcutController` for `Super+Shift+R`. The GNOME Shell extension does
  not register this shortcut globally.
- In a normal launch the control is disabled because no approved STT backend
  exists yet. The explicit developer flag `--dictation-simulation` runs only a
  fixed synthetic sequence.
- Partial text is a separate preview. A final result enters `Gtk.TextBuffer`
  as one undoable action at a moving mark. A new partial replaces the previous
  preview and does not alter manually corrected text.
- Closing the editor cancels the session and removes scheduled simulation
  results. Clipboard save, clearing, and asynchronous backend operations are
  disabled while a session is active; manual editing and Undo remain available.

## Worker result protocol

Each message is one JSON object. The implementation limits a frame to 8192
bytes, text to 4096 characters, and the session identifier to 64 safe
characters, and rejects fields outside the closed schema.

```json
{"version":1,"session_id":"session-1","sequence":1,"kind":"ready"}
{"version":1,"session_id":"session-1","sequence":2,"kind":"partial","segment":0,"text":"This is"}
{"version":1,"session_id":"session-1","sequence":3,"kind":"final","segment":0,"text":"This is a test."}
{"version":1,"session_id":"session-1","sequence":4,"kind":"stopped"}
{"version":1,"session_id":"session-1","sequence":4,"kind":"error","code":"engine"}
```

Allowed error codes are `audio-device`, `engine`, `protocol`, and `worker`.
The session identifier rejects late results from an old worker, increasing
`sequence` rejects replayed frames, and the `segment` number prevents a final
fragment from being added twice. A validation error has a fixed message that
does not contain transcript text.

A production worker should be a separate unprivileged child of the editor.
Audio should remain in memory and results should use a bounded pipe. The
process must not be a service, daemon, or child of GNOME Shell. Start/stop
commands and audio transport are not implemented yet; selecting an engine and
explicit approval for microphone access are required before adding them.

## State indicators

The current prototype makes the microphone button blue only in `recording`;
red never means recording. The `stopped` protocol event ends a session and
returns it to `idle`.

Proposed panel presentation, not implemented yet:

1. the paper sheets continue to show clipboard protection state only;
2. a separate small blue microphone appears beside the sheets during real
   recording;
3. stopping removes the microphone instead of recoloring the sheets;
4. combinations remain independent: blue sheets plus a blue microphone mean
   protection and recording, while red sheets plus a blue microphone mean
   paused monitoring and dictation in the future blank editor.

The panel icon logic should not change before a real audio session and a
reliable editor-to-extension state channel exist.

## Blank editor while monitoring is paused

The safe design separates two explicit launch modes:

- `clipboard`: the current mode, which requires active protection before it
  reads the clipboard;
- `blank`: creates an empty buffer without calling a clipboard API and may run
  while monitoring is paused.

`blank` is not implemented yet. It needs a separate result type and an
unambiguous “Copy result” control because the current “Replace clipboard” path
checks the pause state again. Explicit copying from a blank editor may be
allowed as a user action, but it must not resume monitoring, read old content,
or add text to history. This semantic change needs separate approval and tests.

## Candidate comparison

There is no benchmark result on target hardware yet, so no engine has been
selected.

| Candidate | Documentation evidence | Measurement question |
| --- | --- | --- |
| Vosk `small-pl-0.22` | 50 MB Polish model, Apache-2.0; streaming API; small models usually use about 300 MB RAM | Polish dictation accuracy and punctuation quality |
| whisper.cpp `tiny/base/small` | 75/142/466 MiB models and about 273/388/852 MB RAM; MIT; local `stream` example reruns inference every 0.5 s and is described as naive | stable-text latency, Polish quality, and CPU cost |

Vosk has semantics better aligned with partial results. Whisper is a justified
quality candidate, but its streaming example alone does not prove sufficiently
fast and stable corrections. Compatibility with Ubuntu 26.04 and Fedora 44 is
not verified. `experiments/dictation-benchmark/` is ready to score WER/CER,
latency, CPU, RSS, and model size, but does not run an engine or microphone.

Sources: [Vosk models](https://alphacephei.com/vosk/models),
[Vosk offline and streaming API](https://alphacephei.com/vosk/),
[whisper.cpp README](https://github.com/ggml-org/whisper.cpp/blob/master/README.md),
[whisper.cpp license](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE),
[OpenAI Whisper models and license](https://github.com/openai/whisper/blob/main/README.md).

## Further permissions and safeguards

The next stage needs separate approval to download engine code and models. Its
plan should list exact URLs, SHA-256 hashes, sizes, licenses, destination, and
installation commands without `sudo`. A model remains optional.

Real integration needs access only to audio input during an explicit session.
It must stop the worker on editor close, session lock, suspend, device loss,
and process failure; it must not save audio or transcripts, log content, use
the network, or copy output automatically. The simulation prototype alone does
not satisfy these cases, which require integration tests before the first
microphone-enabled package.

The eventual model manager should use a versioned allowlist containing engine,
language, version, size, HTTPS URL, SHA-256, and license. Downloads are
explicit, partial files have private permissions and a size limit, and
installation is atomic after verification. Removal does not follow symlinks
and affects only an allowlisted entry inside the user's data directory.
