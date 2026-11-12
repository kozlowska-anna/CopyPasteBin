#!/usr/bin/env python3
"""Feed a PCM WAV file to libvosk and emit the CopyPasteBin frame protocol."""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import time
import wave
from pathlib import Path


MAX_RESULT_BYTES = 64 * 1024
MAX_TEXT_CHARS = 4096


def emit(session: str, sequence: int, kind: str, **extra: object) -> None:
    print(json.dumps({"version": 1, "session_id": session, "sequence": sequence,
                      "kind": kind, **extra}, ensure_ascii=False), flush=True)


def iter_audio_chunks(
    audio,
    frames_per_chunk: int,
    feed_mode: str,
    *,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    """Yield PCM chunks immediately or when they would become available live."""
    started = monotonic()
    frames_sent = 0
    while data := audio.readframes(frames_per_chunk):
        frames_sent += len(data) // 2
        if feed_mode == "realtime":
            remaining = started + frames_sent / 16000 - monotonic()
            if remaining > 0:
                sleep(remaining)
        yield data, frames_sent


def _result(function, key: str) -> str:
    raw = function()
    if not raw or len(raw) > MAX_RESULT_BYTES:
        raise RuntimeError("engine result exceeded the safe limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("engine returned invalid JSON") from error
    if not isinstance(payload, dict) or set(payload) != {key} or \
            not isinstance(payload[key], str) or len(payload[key]) > MAX_TEXT_CHARS or \
            "\0" in payload[key]:
        raise RuntimeError("engine returned an invalid result")
    return payload[key].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--chunk-ms", type=int, default=100)
    parser.add_argument("--feed-mode", choices=("file", "realtime"), required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}", args.session):
        parser.error("invalid session identifier")
    if not 20 <= args.chunk_ms <= 1000:
        parser.error("chunk size is outside the safe range")

    library = ctypes.CDLL(str(args.library.resolve()))
    library.vosk_set_log_level.argtypes = [ctypes.c_int]
    library.vosk_model_new.argtypes = [ctypes.c_char_p]
    library.vosk_model_new.restype = ctypes.c_void_p
    library.vosk_model_free.argtypes = [ctypes.c_void_p]
    library.vosk_recognizer_new.argtypes = [ctypes.c_void_p, ctypes.c_float]
    library.vosk_recognizer_new.restype = ctypes.c_void_p
    library.vosk_recognizer_free.argtypes = [ctypes.c_void_p]
    library.vosk_recognizer_accept_waveform.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    library.vosk_recognizer_accept_waveform.restype = ctypes.c_int
    for name in ("vosk_recognizer_partial_result", "vosk_recognizer_result",
                 "vosk_recognizer_final_result"):
        function = getattr(library, name)
        function.argtypes = [ctypes.c_void_p]
        function.restype = ctypes.c_char_p
    library.vosk_set_log_level(-1)

    model = library.vosk_model_new(str(args.model.resolve()).encode())
    if not model:
        raise RuntimeError("model initialization failed")
    recognizer = None
    sequence, segment = 1, 0
    last_partial = ""
    try:
        recognizer = library.vosk_recognizer_new(model, 16000.0)
        if not recognizer:
            raise RuntimeError("recognizer initialization failed")
        emit(args.session, sequence, "ready")
        with wave.open(str(args.audio), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                    audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise RuntimeError("audio must be mono 16-bit PCM WAV at 16 kHz")
            frames_per_chunk = 16000 * args.chunk_ms // 1000
            frames_sent = 0
            for data, frames_sent in iter_audio_chunks(
                    audio, frames_per_chunk, args.feed_mode):
                accepted = library.vosk_recognizer_accept_waveform(
                    recognizer, data, len(data))
                payload_name = "vosk_recognizer_result" if accepted else "vosk_recognizer_partial_result"
                result_key = "text" if accepted else "partial"
                text = _result(
                    lambda: getattr(library, payload_name)(recognizer), result_key)
                audio_position_ms = round(frames_sent / 16, 3)
                if accepted and text:
                    sequence += 1
                    emit(args.session, sequence, "final", segment=segment, text=text,
                         audio_position_ms=audio_position_ms)
                    segment += 1
                    last_partial = ""
                elif not accepted and text != last_partial:
                    sequence += 1
                    emit(args.session, sequence, "partial", segment=segment, text=text,
                         audio_position_ms=audio_position_ms)
                    last_partial = text
        text = _result(lambda: library.vosk_recognizer_final_result(recognizer), "text")
        audio_position_ms = round(frames_sent / 16, 3)
        if text:
            sequence += 1
            emit(args.session, sequence, "final", segment=segment, text=text,
                 audio_position_ms=audio_position_ms)
        sequence += 1
        emit(args.session, sequence, "stopped", audio_position_ms=audio_position_ms)
    finally:
        if recognizer:
            library.vosk_recognizer_free(recognizer)
        library.vosk_model_free(model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
