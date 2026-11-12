#!/usr/bin/env python3
"""Run pinned whisper-cli in batch mode and emit bounded benchmark frames."""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import signal
import subprocess
import tempfile
import wave
from pathlib import Path


MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024
MAX_SEGMENTS = 10_000
MAX_TEXT_CHARS = 4096
SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}")
LOAD_TIME = re.compile(rb"\bload time\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*ms\b")


class AdapterError(Exception):
    pass


def emit(session: str, sequence: int, kind: str, **extra: object) -> None:
    print(json.dumps({"version": 1, "session_id": session, "sequence": sequence,
                      "kind": kind, **extra}, ensure_ascii=False), flush=True)


def _audio_duration_ms(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                audio.getcomptype()) != (1, 2, 16000, "NONE"):
            raise AdapterError("audio must be mono 16-bit PCM WAV at 16 kHz")
        return round(audio.getnframes() / 16, 3)


def _limit_output_files() -> None:
    limit = max(MAX_JSON_BYTES, MAX_STDERR_BYTES) + 1
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))


def _read_bounded(stream, limit: int, label: str) -> bytes:
    size = os.fstat(stream.fileno()).st_size
    if size > limit:
        raise AdapterError(f"whisper-cli {label} exceeded the safe limit")
    stream.seek(0)
    return stream.read(limit + 1)


def _kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _run_cli(command: list[str], stdout, stderr, timeout_seconds: int) -> int:
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
        start_new_session=True, preexec_fn=_limit_output_files,
    )
    try:
        return process.wait(timeout=timeout_seconds)
    except BaseException:
        _kill_process_group(process)
        raise


def _parse_output(payload: bytes) -> str:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterError("whisper-cli emitted invalid JSON") from error
    if not isinstance(document, dict) or not isinstance(document.get("transcription"), list):
        raise AdapterError("whisper-cli JSON has an invalid shape")
    segments = document["transcription"]
    if not 1 <= len(segments) <= MAX_SEGMENTS:
        raise AdapterError("whisper-cli returned an invalid segment count")
    texts = []
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise AdapterError("whisper-cli returned an invalid segment")
        text = " ".join(segment["text"].split())
        if not text or "\0" in text:
            raise AdapterError("whisper-cli returned invalid text")
        texts.append(text)
    transcript = " ".join(texts)
    if len(transcript) > MAX_TEXT_CHARS:
        raise AdapterError("whisper-cli transcript exceeded the protocol limit")
    return transcript


def _parse_model_init_ms(stderr: bytes) -> float:
    matches = LOAD_TIME.findall(stderr)
    if len(matches) != 1:
        raise AdapterError("whisper-cli did not report one model load time")
    value = float(matches[0])
    if value < 0:
        raise AdapterError("whisper-cli reported an invalid model load time")
    return round(value, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    if not SESSION.fullmatch(args.session):
        parser.error("invalid session identifier")
    if args.binary != Path("/engine/whisper-cli") or args.model != Path("/model") or \
            args.audio != Path("/audio/input.wav"):
        parser.error("paths do not match the controlled isolation profile")
    if not 1 <= args.threads <= 64 or not 1 <= args.timeout_seconds <= 3600:
        parser.error("resource limit is outside the safe range")

    duration_ms = _audio_duration_ms(args.audio)
    command = [
        str(args.binary), "--model", str(args.model), "--file", str(args.audio),
        "--language", "pl", "--threads", str(args.threads), "--processors", "1",
        "--no-gpu", "--output-json", "--output-file", "-",
    ]
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            returncode = _run_cli(command, stdout, stderr, args.timeout_seconds)
        except subprocess.TimeoutExpired as error:
            raise AdapterError("whisper-cli timed out") from error
        output = _read_bounded(stdout, MAX_JSON_BYTES, "JSON output")
        diagnostics = _read_bounded(stderr, MAX_STDERR_BYTES, "diagnostics")
    if returncode != 0:
        raise AdapterError("whisper-cli failed")
    transcript = _parse_output(output)
    model_init_ms = _parse_model_init_ms(diagnostics)
    emit(args.session, 1, "ready", model_init_ms=model_init_ms)
    emit(args.session, 2, "final", segment=0, text=transcript,
         audio_position_ms=duration_ms)
    emit(args.session, 3, "stopped", audio_position_ms=duration_ms)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AdapterError, OSError, wave.Error) as error:
        raise SystemExit(f"whisper adapter failed: {error}") from None
