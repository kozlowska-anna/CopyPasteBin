#!/usr/bin/env python3
"""Benchmark wrapper around the production CopyPasteBin bridge worker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from copypastebin.bridge_worker import (
    BridgeWorkerError,
    MAX_WORKER_IDLE_TIMEOUT_SECONDS,
    MIN_WORKER_IDLE_TIMEOUT_SECONDS,
    run_bridge_worker,
)
from copypastebin.config import ConfigError
from copypastebin.detection import Bip39ResourceError
from copypastebin.filters import FilterError
from copypastebin.history import HistoryError
from copypastebin.notifications import NotificationError
from copypastebin.pause import PauseError


GENERIC_ERROR = "Persistent bridge worker stopped safely.\n"


def _absolute_path(value: str) -> Path:
    selected = Path(value)
    if not selected.is_absolute() or "\x00" in value:
        raise argparse.ArgumentTypeError("an absolute benchmark path is required")
    return selected


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=_absolute_path, required=True)
    parser.add_argument("--config", type=_absolute_path, required=True)
    parser.add_argument("--idle-timeout", type=float, default=30.0)
    arguments = parser.parse_args(argv)
    if not (
        MIN_WORKER_IDLE_TIMEOUT_SECONDS
        <= arguments.idle_timeout
        <= MAX_WORKER_IDLE_TIMEOUT_SECONDS
    ):
        parser.error("--idle-timeout is outside the benchmark range")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        return run_bridge_worker(
            sys.stdin.buffer,
            sys.stdout.buffer,
            state_dir=arguments.state_dir,
            config_path=arguments.config,
            idle_timeout=arguments.idle_timeout,
        )
    except (
        Bip39ResourceError,
        BridgeWorkerError,
        ConfigError,
        FilterError,
        HistoryError,
        NotificationError,
        PauseError,
        BrokenPipeError,
        OSError,
    ):
        sys.stderr.write(GENERIC_ERROR)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
