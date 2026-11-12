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
SAFE_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}")
SAFE_CASE = re.compile(r"pl-[0-9]{2}")


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
        root = path.resolve(strict=True)
        for item in path.rglob("*"):
            try:
                item_info = os.lstat(item)
            except OSError as error:
                raise IsolationError("an input tree could not be validated") from error
            if item_info.st_uid != os.geteuid():
                raise IsolationError("an input tree contains an untrusted object")
            if stat.S_ISLNK(item_info.st_mode):
                try:
                    target = item.resolve(strict=True)
                except OSError as error:
                    raise IsolationError("an input tree contains a broken symlink") from error
                if not target.is_relative_to(root) or not target.is_file():
                    raise IsolationError("an input tree contains an unsafe symlink")
            elif not (stat.S_ISREG(item_info.st_mode) or stat.S_ISDIR(item_info.st_mode)):
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


def _validate_engine_layout(engine_id: str, engine: Path, model: Path) -> None:
    if engine_id == "vosk-small-pl-0.22":
        if not engine.is_file() or engine.name != "libvosk.so" or \
                not model.is_dir() or model.name != "vosk-model-small-pl-0.22":
            raise IsolationError("Vosk inputs do not match the pinned layout")
        return
    expected_model = {
        "whisper.cpp-tiny": "ggml-tiny.bin",
        "whisper.cpp-base": "ggml-base.bin",
        "whisper.cpp-small": "ggml-small.bin",
    }[engine_id]
    binary = engine / "whisper-cli"
    try:
        binary_info = os.lstat(binary)
    except OSError as error:
        raise IsolationError("the pinned whisper-cli executable is unavailable") from error
    if not engine.is_dir() or not model.is_file() or model.name != expected_model or \
            stat.S_ISLNK(binary_info.st_mode) or not stat.S_ISREG(binary_info.st_mode) or \
            binary_info.st_uid != os.geteuid() or not binary_info.st_mode & stat.S_IXUSR:
        raise IsolationError("Whisper inputs do not match the pinned layout")


def _validate_command(command: list[str], engine: str, mode: str,
                      input_pacing: str, session: str, timeout_seconds: int) -> None:
    if len(command) > 32 or any(not value or "\0" in value or len(value) > 4096
                                for value in command):
        raise IsolationError("adapter command is invalid")
    if engine == "vosk-small-pl-0.22":
        expected = "realtime" if input_pacing == "realtime" else "file"
        approved = [
            "/usr/bin/python3", "/benchmark/adapters/vosk_ctypes.py",
            "--library", "/engine", "--model", "/model",
            "--audio", "/audio/input.wav", "--session", session,
            "--feed-mode", expected,
        ]
        if mode != "streaming" or command != approved:
            raise IsolationError("Vosk requires the exact approved adapter command")
        return
    approved = [
        "/usr/bin/python3", "/benchmark/adapters/whisper_cli.py",
        "--binary", "/engine/whisper-cli", "--model", "/model",
        "--audio", "/audio/input.wav", "--session", session,
        "--threads", "4", "--timeout-seconds", str(timeout_seconds - 5),
    ]
    if mode != "batch" or input_pacing != "fast" or command != approved:
        raise IsolationError("whisper-cli requires the exact approved batch command")


def build_command(arguments: argparse.Namespace) -> list[str]:
    bwrap = shutil.which("bwrap")
    if bwrap is None or Path(bwrap).resolve() != Path("/usr/bin/bwrap"):
        raise IsolationError("the approved /usr/bin/bwrap executable is unavailable")
    benchmark = Path(__file__).resolve().parent
    audio = _validate_input(arguments.audio, regular_file=True)
    engine = _validate_input(arguments.engine_path)
    model = _validate_input(arguments.model_path)
    _validate_engine_layout(arguments.engine, engine, model)
    results_directory, result_name = _validate_results(arguments.results)
    command = arguments.command
    if command and command[0] == "--":
        command = command[1:]
    if not SAFE_CASE.fullmatch(arguments.case_id) or \
            not SAFE_SESSION.fullmatch(arguments.session):
        raise IsolationError("session identifier is invalid")
    _validate_command(command, arguments.engine, arguments.mode,
                      arguments.input_pacing, arguments.session,
                      arguments.timeout_seconds)

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
    if not 10 <= arguments.timeout_seconds <= 3600:
        parser.error("timeout is outside the safe range")
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
