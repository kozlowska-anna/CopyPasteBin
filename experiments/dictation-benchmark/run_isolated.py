#!/usr/bin/env python3
"""Establish the approved bwrap profile and run one STT benchmark adapter."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
from pathlib import Path


PROFILE = "bwrap-v1"
SAFE_RESULT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class IsolationError(Exception):
    pass


def _validate_input(path: Path, *, regular_file: bool = False) -> Path:
    if not path.is_absolute():
        raise IsolationError("input paths must be absolute")
    try:
        info = os.lstat(path)
    except OSError as error:
        raise IsolationError("an input path is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.geteuid():
        raise IsolationError("an input path is not a trusted user-owned object")
    if regular_file:
        if not stat.S_ISREG(info.st_mode):
            raise IsolationError("audio input must be a regular file")
    elif not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise IsolationError("engine and model inputs must be regular files or directories")
    if stat.S_ISDIR(info.st_mode):
        for item in path.rglob("*"):
            try:
                item_info = os.lstat(item)
            except OSError as error:
                raise IsolationError("an input tree could not be validated") from error
            if stat.S_ISLNK(item_info.st_mode) or item_info.st_uid != os.geteuid() or not (
                    stat.S_ISREG(item_info.st_mode) or stat.S_ISDIR(item_info.st_mode)):
                raise IsolationError("an input tree contains an untrusted object")
    return path


def _validate_results(path: Path) -> tuple[Path, str]:
    if not path.is_absolute() or not SAFE_RESULT_NAME.fullmatch(path.name):
        raise IsolationError("result path is invalid")
    directory = path.parent
    try:
        info = os.lstat(directory)
    except OSError as error:
        raise IsolationError("result directory is unavailable") from error
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise IsolationError("result directory must be user-owned mode 0700")
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        existing = None
    except OSError as error:
        raise IsolationError("result target could not be validated") from error
    if existing is not None and (
        not stat.S_ISREG(existing.st_mode)
        or stat.S_ISLNK(existing.st_mode)
        or existing.st_uid != os.geteuid()
        or stat.S_IMODE(existing.st_mode) != 0o600
    ):
        raise IsolationError("existing result must be a user-owned mode 0600 file")
    return directory, path.name


def _validate_command(command: list[str], input_pacing: str) -> None:
    if not command or command[0] not in {"/usr/bin/python3", "/engine/whisper-cli"}:
        raise IsolationError("adapter command is outside the closed executable set")
    if len(command) > 64 or any(not value or "\0" in value or len(value) > 4096 for value in command):
        raise IsolationError("adapter command is invalid")
    if len(command) >= 2 and command[:2] == [
            "/usr/bin/python3", "/benchmark/adapters/vosk_ctypes.py"]:
        expected = "realtime" if input_pacing == "realtime" else "file"
        positions = [index for index, value in enumerate(command) if value == "--feed-mode"]
        if len(positions) != 1 or positions[0] + 1 >= len(command) or \
                command[positions[0] + 1] != expected:
            raise IsolationError("Vosk feed mode does not match benchmark input pacing")


def build_command(arguments: argparse.Namespace) -> list[str]:
    bwrap = shutil.which("bwrap")
    if bwrap is None or Path(bwrap).resolve() != Path("/usr/bin/bwrap"):
        raise IsolationError("the approved /usr/bin/bwrap executable is unavailable")
    benchmark = Path(__file__).resolve().parent
    audio = _validate_input(arguments.audio, regular_file=True)
    engine = _validate_input(arguments.engine_path)
    model = _validate_input(arguments.model_path)
    results_directory, result_name = _validate_results(arguments.results)
    command = arguments.command
    if command and command[0] == "--":
        command = command[1:]
    _validate_command(command, arguments.input_pacing)

    runner = [
        "/usr/bin/python3", "/benchmark/run_adapter.py",
        "--case-id", arguments.case_id,
        "--engine", arguments.engine,
        "--run", str(arguments.run),
        "--mode", arguments.mode,
        "--input-pacing", arguments.input_pacing,
        "--session", arguments.session,
        "--audio", "/audio/input.wav",
        "--engine-path", "/engine",
        "--model-path", "/model",
        "--results", f"/results/{result_name}",
        "--timeout-seconds", str(arguments.timeout_seconds),
        "--", *command,
    ]
    return [
        bwrap,
        "--unshare-net", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
        "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--dir", "/etc",
        "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--ro-bind", str(benchmark), "/benchmark",
        "--ro-bind", str(engine), "/engine",
        "--ro-bind", str(model), "/model",
        "--dir", "/audio",
        "--ro-bind", str(audio), "/audio/input.wav",
        "--bind", str(results_directory), "/results",
        "--remount-ro", "/",
        "--chdir", "/benchmark",
        "--setenv", "HOME", "/tmp",
        "--setenv", "LANG", "C.UTF-8",
        "--setenv", "PATH", "/usr/bin",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--setenv", "LD_LIBRARY_PATH", "/engine",
        "--setenv", "CPB_BENCHMARK_ISOLATION", PROFILE,
        *runner,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--engine", required=True, choices=(
        "vosk-small-pl-0.22", "whisper.cpp-tiny", "whisper.cpp-base",
        "whisper.cpp-small",
    ))
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
    arguments = parser.parse_args()
    if arguments.mode == "batch" and arguments.input_pacing != "fast":
        parser.error("batch mode requires fast file input")
    try:
        command = build_command(arguments)
    except IsolationError as error:
        parser.error(str(error))
    os.execv(command[0], command)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
