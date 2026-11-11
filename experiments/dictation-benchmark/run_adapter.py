#!/usr/bin/env python3
"""Run one file-based STT adapter and append bounded metrics to a private file."""

from __future__ import annotations

import argparse
import json
import os
import queue
import resource
import subprocess
import threading
import time
import wave
from pathlib import Path

from score import ALLOWED_ENGINES, InputError, _read_json

MAX_EVENTS = 10_000
MAX_RESULTS = 500


def _tree_size(path: Path) -> int:
    resolved = path.resolve(strict=True)
    if resolved.is_file():
        return resolved.stat().st_size
    total = 0
    for item in resolved.rglob("*"):
        if item.is_symlink():
            raise InputError("measured path contains a symlink")
        if item.is_file():
            total += item.stat().st_size
    return total


def _audio_duration(path: Path) -> float:
    with wave.open(str(path.resolve(strict=True)), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                audio.getcomptype()) != (1, 2, 16000, "NONE"):
            raise InputError("audio must be mono 16-bit PCM WAV at 16 kHz")
        return audio.getnframes() / 16


def _frame(raw: str, session: str, last_sequence: int) -> dict:
    try:
        frame = json.loads(raw)
    except json.JSONDecodeError as error:
        raise InputError("adapter emitted invalid JSON") from error
    if not isinstance(frame, dict) or frame.get("version") != 1 or \
            frame.get("session_id") != session or \
            not isinstance(frame.get("sequence"), int) or \
            frame["sequence"] <= last_sequence or \
            frame.get("kind") not in {"ready", "partial", "final", "stopped", "error"}:
        raise InputError("adapter emitted an invalid frame")
    expected = {"version", "session_id", "sequence", "kind"}
    if frame["kind"] in {"partial", "final"}:
        expected |= {"segment", "text"}
        if not isinstance(frame.get("segment"), int) or frame["segment"] < 0 or \
                not isinstance(frame.get("text"), str) or len(frame["text"]) > 4096 or \
                "\0" in frame["text"] or (frame["kind"] == "final" and not frame["text"]):
            raise InputError("adapter emitted invalid text")
    elif frame["kind"] == "error":
        expected.add("code")
        if frame.get("code") not in {"audio-device", "engine", "protocol", "worker"}:
            raise InputError("adapter emitted an invalid error")
    if set(frame) != expected:
        raise InputError("adapter emitted fields outside the protocol")
    return frame


def _reader(stream, messages: queue.Queue) -> None:
    try:
        for line in stream:
            messages.put((time.monotonic(), line))
    finally:
        messages.put(None)


def _rss_mib(pid: int) -> float:
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        return 0.0
    for line in status.splitlines():
        if line.startswith(("VmHWM:", "VmRSS:")):
            return float(line.split()[1]) / 1024
    return 0.0


def _append_private(path: Path, result: dict) -> None:
    if path.exists():
        document = _read_json(path)
        if not isinstance(document, dict) or set(document) != {"version", "results"} or \
                document["version"] != 2 or not isinstance(document["results"], list):
            raise InputError("existing result file has an invalid shape")
    else:
        document = {"version": 2, "results": []}
    if len(document["results"]) >= MAX_RESULTS:
        raise InputError("result file is full")
    document["results"].append(result)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, ensure_ascii=False, separators=(",", ":"))
            output.write("\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--engine", required=True, choices=sorted(ALLOWED_ENGINES))
    parser.add_argument("--run", required=True, type=int, choices=(1, 2, 3))
    parser.add_argument("--mode", required=True, choices=("streaming", "windowed", "batch"))
    parser.add_argument("--session", required=True)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--engine-path", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--offline", action="store_true",
                        help="Assert that the command is running in a network namespace")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.offline:
        parser.error("refusing a run not explicitly marked offline")
    if not args.command or args.command[0] != "--" or len(args.command) == 1:
        parser.error("adapter command must follow --")
    command = args.command[1:]
    duration_ms = _audio_duration(args.audio)
    engine_bytes = _tree_size(args.engine_path)
    model_bytes = _tree_size(args.model_path)

    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
    messages: queue.Queue = queue.Queue()
    reader = threading.Thread(target=_reader, args=(process.stdout, messages), daemon=True)
    reader.start()
    events, peak_rss, finished = [], 0.0, False
    try:
        while not finished:
            if time.monotonic() - started > args.timeout_seconds:
                raise InputError("adapter timed out")
            peak_rss = max(peak_rss, _rss_mib(process.pid))
            try:
                item = messages.get(timeout=0.01)
            except queue.Empty:
                continue
            if item is None:
                finished = True
            else:
                observed, line = item
                if len(events) >= MAX_EVENTS or len(line.encode("utf-8")) > 8192:
                    raise InputError("adapter event limit exceeded")
                events.append((round((observed - started) * 1000, 3), line))
    except Exception:
        process.kill()
        process.wait()
        raise
    returncode = process.wait()
    if returncode != 0:
        raise InputError("adapter failed")
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)

    state, last_sequence, last_segment = "starting", 0, -1
    ready_ms = first_partial_ms = stopped_ms = None
    partials, finals = [], []
    for observed_ms, raw in events:
        frame = _frame(raw, args.session, last_sequence)
        last_sequence = frame["sequence"]
        kind = frame["kind"]
        if kind == "ready" and state == "starting":
            state, ready_ms = "recording", observed_ms
        elif kind == "partial" and state == "recording" and frame["segment"] > last_segment:
            partials.append({"at_ms": observed_ms, "text": frame["text"]})
            first_partial_ms = observed_ms if first_partial_ms is None else first_partial_ms
        elif kind == "final" and state == "recording" and frame["segment"] > last_segment:
            last_segment = frame["segment"]
            finals.append(frame["text"])
        elif kind == "stopped" and state == "recording":
            state, stopped_ms = "stopped", observed_ms
        elif kind == "error":
            raise InputError("adapter reported an error")
        else:
            raise InputError("adapter frame violates session state")
    if state != "stopped" or ready_ms is None or stopped_ms is None or not finals:
        raise InputError("adapter stream is incomplete")
    if args.mode == "batch" and partials:
        raise InputError("batch adapter emitted partial results")

    cpu_seconds = ((usage_after.ru_utime + usage_after.ru_stime) -
                   (usage_before.ru_utime + usage_before.ru_stime))
    result = {
        "case_id": args.case_id,
        "engine": args.engine,
        "run": args.run,
        "transcript": " ".join(finals),
        "recognition_mode": args.mode,
        "audio_duration_ms": duration_ms,
        "model_init_ms": ready_ms,
        "first_partial_ms": first_partial_ms,
        "final_result_ms": stopped_ms,
        "partials": partials,
        "cpu_seconds": round(cpu_seconds, 6),
        "peak_rss_mib": round(peak_rss, 3),
        "engine_bytes": engine_bytes,
        "model_bytes": model_bytes,
        "offline": True,
    }
    _append_private(args.results, result)
    print("Benchmark run recorded without printing transcript content.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InputError, OSError, wave.Error) as error:
        raise SystemExit(f"benchmark failed: {error}") from None
