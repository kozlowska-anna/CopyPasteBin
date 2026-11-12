#!/usr/bin/env python3
"""Run one file-based STT adapter and append bounded metrics to a private file."""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import resource
import socket
import stat
import subprocess
import threading
import time
import wave
from pathlib import Path

from score import ALLOWED_ENGINES, InputError, _read_json

MAX_EVENTS = 10_000
MAX_RESULTS = 500
ISOLATION_PROFILE = "bwrap-v1"


def _tree_size(path: Path) -> int:
    resolved = path.resolve(strict=True)
    if resolved.is_file():
        return resolved.stat().st_size
    total = 0
    seen = set()
    for item in resolved.rglob("*"):
        if item.is_symlink():
            target = item.resolve(strict=True)
            if not target.is_relative_to(resolved) or not target.is_file():
                raise InputError("measured path contains an unsafe symlink")
            continue
        info = item.stat()
        if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in seen:
            seen.add((info.st_dev, info.st_ino))
            total += info.st_size
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
    if not isinstance(frame, dict) or type(frame.get("version")) is not int or \
            frame.get("version") != 1 or \
            frame.get("session_id") != session or \
            type(frame.get("sequence")) is not int or \
            frame["sequence"] <= last_sequence or \
            frame.get("kind") not in {"ready", "partial", "final", "stopped", "error"}:
        raise InputError("adapter emitted an invalid frame")
    expected = {"version", "session_id", "sequence", "kind"}
    if frame["kind"] == "ready" and "model_init_ms" in frame:
        value = frame["model_init_ms"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or \
                not math.isfinite(value) or value < 0:
            raise InputError("adapter emitted an invalid model initialization time")
        expected.add("model_init_ms")
    elif frame["kind"] in {"partial", "final"}:
        expected |= {"segment", "text", "audio_position_ms"}
        position = frame.get("audio_position_ms")
        if type(frame.get("segment")) is not int or frame["segment"] < 0 or \
                not isinstance(frame.get("text"), str) or len(frame["text"]) > 4096 or \
                "\0" in frame["text"] or (frame["kind"] == "final" and not frame["text"]) or \
                isinstance(position, bool) or not isinstance(position, (int, float)) or \
                position < 0:
            raise InputError("adapter emitted invalid text")
    elif frame["kind"] == "stopped":
        expected.add("audio_position_ms")
        position = frame.get("audio_position_ms")
        if isinstance(position, bool) or not isinstance(position, (int, float)) or position < 0:
            raise InputError("adapter emitted invalid audio progress")
    elif frame["kind"] == "error":
        expected.add("code")
        if frame.get("code") not in {"audio-device", "engine", "protocol", "worker"}:
            raise InputError("adapter emitted an invalid error")
    if set(frame) != expected:
        raise InputError("adapter emitted fields outside the protocol")
    return frame


def _mount_is_read_only(path: Path) -> bool:
    try:
        return bool(os.statvfs(path).f_flag & os.ST_RDONLY)
    except OSError as error:
        raise InputError("isolation mount validation failed") from error


def _network_interfaces() -> set[str]:
    try:
        return {name for _, name in socket.if_nameindex()}
    except OSError as error:
        raise InputError("network isolation validation failed") from error


def _effective_capabilities() -> int:
    try:
        lines = Path("/proc/self/status").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise InputError("capability isolation validation failed") from error
    for line in lines:
        if line.startswith("CapEff:"):
            try:
                return int(line.split()[1], 16)
            except (IndexError, ValueError) as error:
                raise InputError("capability isolation validation failed") from error
    raise InputError("capability isolation validation failed")


def _verify_isolation(arguments: argparse.Namespace) -> str:
    if os.environ.get("CPB_BENCHMARK_ISOLATION") != ISOLATION_PROFILE:
        raise InputError("benchmark requires the controlled bwrap launcher")
    expected = {
        "audio": Path("/audio/input.wav"),
        "engine_path": Path("/engine"),
        "model_path": Path("/model"),
    }
    if any(getattr(arguments, name) != path for name, path in expected.items()) or \
            arguments.results.parent != Path("/results"):
        raise InputError("benchmark paths do not match the isolation profile")
    required = tuple(expected.values()) + (
        Path("/benchmark"), Path("/results"), Path("/usr"), Path("/proc"),
        Path("/dev"), Path("/tmp"),
    )
    if any(not path.exists() for path in required):
        raise InputError("isolation profile is incomplete")
    if any(path.exists() for path in (Path("/home"), Path("/etc/passwd"), Path("/dev/snd"))):
        raise InputError("isolation exposes a forbidden resource")
    for path in (Path("/"), Path("/usr"), Path("/benchmark"), Path("/engine"),
                 Path("/model"), Path("/audio/input.wav")):
        if not _mount_is_read_only(path):
            raise InputError("isolation exposes a writable input")
    if _mount_is_read_only(Path("/results")) or _mount_is_read_only(Path("/tmp")):
        raise InputError("isolation output mounts are not writable")
    if _network_interfaces() - {"lo"}:
        raise InputError("network isolation exposes an external interface")
    try:
        routes = Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]
        ipv6_routes = Path("/proc/net/ipv6_route").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as error:
        raise InputError("network isolation validation failed") from error
    if any(line.split()[1] == "00000000" for line in routes if len(line.split()) > 1):
        raise InputError("network isolation has an IPv4 default route")
    if any(parts[0] == "0" * 32 and parts[1] == "00" and parts[-1] != "lo"
           for line in ipv6_routes if len(parts := line.split()) > 1):
        raise InputError("network isolation has an IPv6 default route")
    if _effective_capabilities() != 0:
        raise InputError("benchmark process retained capabilities")
    return ISOLATION_PROFILE


def _reader(stream, messages: queue.Queue) -> None:
    try:
        for line in stream:
            messages.put((time.monotonic(), line))
    finally:
        messages.put(None)


def _child_pids(pid: int) -> set[int]:
    pending, found = [pid], set()
    while pending:
        current = pending.pop()
        try:
            children = Path(f"/proc/{current}/task/{current}/children").read_text(
                encoding="ascii").split()
        except (OSError, UnicodeError):
            continue
        for value in children:
            child = int(value)
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def _rss_mib(pid: int) -> float:
    total = 0.0
    for process_id in {pid, *_child_pids(pid)}:
        total += _process_rss_mib(process_id)
    return total


def _process_rss_mib(pid: int) -> float:
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
            document["version"] != 3 or not isinstance(document["results"], list):
            raise InputError("existing result file has an invalid shape")
    else:
        document = {"version": 3, "results": []}
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
    parser.add_argument("--input-pacing", required=True, choices=("fast", "realtime"))
    parser.add_argument("--session", required=True)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--engine-path", required=True, type=Path)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        isolation_profile = _verify_isolation(args)
    except InputError as error:
        parser.error(str(error))
    if args.mode == "batch" and args.input_pacing != "fast":
        parser.error("batch mode requires fast file input")
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
    ready_ms = model_init_ms = first_partial_ms = final_result_ms = stopped_ms = None
    partials, finals = [], []
    final_audio_position_ms = None
    last_audio_position_ms = 0.0
    for observed_ms, raw in events:
        frame = _frame(raw, args.session, last_sequence)
        last_sequence = frame["sequence"]
        kind = frame["kind"]
        if kind == "ready" and state == "starting":
            state, ready_ms = "recording", observed_ms
            model_init_ms = float(frame.get("model_init_ms", observed_ms))
        elif kind == "partial" and state == "recording" and frame["segment"] > last_segment:
            audio_position_ms = float(frame["audio_position_ms"])
            if audio_position_ms < last_audio_position_ms or audio_position_ms > duration_ms:
                raise InputError("adapter reported audio progress beyond the input")
            last_audio_position_ms = audio_position_ms
            lag_ms = None
            if args.input_pacing == "realtime":
                observed_lag_ms = observed_ms - ready_ms - audio_position_ms
                if observed_lag_ms < -20:
                    raise InputError("adapter emitted a result before live audio was available")
                lag_ms = round(max(0, observed_lag_ms), 3)
            partials.append({"at_ms": observed_ms, "audio_position_ms": audio_position_ms,
                             "lag_ms": lag_ms, "text": frame["text"]})
            first_partial_ms = observed_ms if first_partial_ms is None else first_partial_ms
        elif kind == "final" and state == "recording" and frame["segment"] > last_segment:
            audio_position_ms = float(frame["audio_position_ms"])
            if audio_position_ms < last_audio_position_ms or audio_position_ms > duration_ms:
                raise InputError("adapter reported audio progress beyond the input")
            last_audio_position_ms = audio_position_ms
            if args.input_pacing == "realtime" and observed_ms - ready_ms - audio_position_ms < -20:
                raise InputError("adapter emitted a result before live audio was available")
            last_segment = frame["segment"]
            finals.append(frame["text"])
            final_result_ms = observed_ms
            final_audio_position_ms = audio_position_ms
        elif kind == "stopped" and state == "recording":
            audio_position_ms = float(frame["audio_position_ms"])
            if audio_position_ms < last_audio_position_ms or \
                    abs(audio_position_ms - duration_ms) > 1:
                raise InputError("adapter did not consume the complete audio input")
            state, stopped_ms = "stopped", observed_ms
        elif kind == "error":
            raise InputError("adapter reported an error")
        else:
            raise InputError("adapter frame violates session state")
    if state != "stopped" or ready_ms is None or stopped_ms is None or \
            final_result_ms is None or final_audio_position_ms is None or not finals:
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
        "input_pacing": args.input_pacing,
        "audio_duration_ms": duration_ms,
        "ready_ms": ready_ms,
        "model_init_ms": model_init_ms,
        "first_partial_ms": first_partial_ms,
        "final_result_ms": final_result_ms,
        "final_audio_position_ms": final_audio_position_ms,
        "completed_ms": stopped_ms,
        "partials": partials,
        "cpu_seconds": round(cpu_seconds, 6),
        "peak_rss_mib": round(peak_rss, 3),
        "engine_bytes": engine_bytes,
        "model_bytes": model_bytes,
        "offline": True,
        "isolation_profile": isolation_profile,
    }
    _append_private(args.results, result)
    print("Benchmark run recorded without printing transcript content.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InputError, OSError, wave.Error) as error:
        raise SystemExit(f"benchmark failed: {error}") from None
