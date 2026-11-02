#!/usr/bin/env python3
"""Small synthetic benchmark for detection and the GNOME bridge boundary."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from copypastebin.detection import analyze_text
from copypastebin.filters import DEFAULT_DISABLED_CATEGORIES


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
APPLICATION_ID = b"synthetic.benchmark"
PROCESS_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    text: str
    core_runs: int


@dataclass(frozen=True, slots=True)
class Timing:
    median_ms: float
    p95_ms: float
    p99_ms: float
    minimum_ms: float
    maximum_ms: float


@dataclass(frozen=True, slots=True)
class ProcessTarget:
    label: str
    command: tuple[str, ...]
    environment: dict[str, str]
    supports_filters: bool = True


def _synthetic_text(size: int) -> str:
    suffix = (
        " Contact: person@example.invalid; phone: +48 123 456 789; "
        "key: sk-proj-CPBINSYNTHETIC0123456789abcdef."
    )
    filler = "CPB synthetic benchmark text; "
    if size < len(suffix):
        raise ValueError("synthetic case is too small")
    repeated = (filler * math.ceil((size - len(suffix)) / len(filler)))[
        : size - len(suffix)
    ]
    text = repeated + suffix
    if len(text.encode("ascii")) != size:
        raise RuntimeError("synthetic case has an unexpected byte size")
    return text


CASES = (
    BenchmarkCase("short", _synthetic_text(256), 1000),
    BenchmarkCase("medium", _synthetic_text(4 * 1024), 300),
    BenchmarkCase("large", _synthetic_text(64 * 1024), 50),
)


def _percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentage) - 1)
    return ordered[index]


def _measure(action: Callable[[], None], runs: int) -> Timing:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return Timing(
        median_ms=statistics.median(samples),
        p95_ms=_percentile(samples, 0.95),
        p99_ms=_percentile(samples, 0.99),
        minimum_ms=min(samples),
        maximum_ms=max(samples),
    )


def _process_environment(*, use_source_tree: bool) -> dict[str, str]:
    environment = {
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if use_source_tree:
        environment["PYTHONPATH"] = str(SOURCE)
    return environment


def _run_process(
    target: ProcessTarget,
    arguments: tuple[str, ...],
    payload: bytes | None = None,
) -> dict:
    completed = subprocess.run(
        (*target.command, *arguments),
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=PROCESS_TIMEOUT_SECONDS,
        env=target.environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"benchmark child failed with status {completed.returncode}"
        )
    try:
        document = json.loads(completed.stdout.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("benchmark child returned invalid JSON") from exc
    if type(document) is not dict:
        raise RuntimeError("benchmark child returned an invalid document")
    return document


def _filters_status(target: ProcessTarget, state_dir: Path) -> None:
    document = _run_process(
        target,
        ("--state-dir", str(state_dir), "ui", "filters"),
    )
    if (
        document.get("version") != 1
        or type(document.get("filters")) is not list
    ):
        raise RuntimeError("unexpected filter status")


def _capabilities(target: ProcessTarget) -> None:
    document = _run_process(target, ("bridge", "capabilities"))
    if document.get("protocol_version") != 2:
        raise RuntimeError("unexpected bridge capabilities")


def _filter_set(target: ProcessTarget, state_dir: Path, enabled: bool) -> None:
    document = _run_process(
        target,
        (
            "--state-dir",
            str(state_dir),
            "ui",
            "filter-set",
            "EMAIL",
            "on" if enabled else "off",
        )
    )
    if (
        document.get("version") != 1
        or type(document.get("filters")) is not list
    ):
        raise RuntimeError("unexpected filter result")


def _bridge_observe(
    target: ProcessTarget,
    text: str,
    state_dir: Path,
    config_path: Path,
) -> None:
    payload = text.encode("ascii")
    frame = len(APPLICATION_ID).to_bytes(4, "big") + APPLICATION_ID + payload
    document = _run_process(
        target,
        (
            "--state-dir",
            str(state_dir),
            "--config",
            str(config_path),
            "bridge",
            "observe",
        ),
        frame,
    )
    if (
        document.get("version") != 1
        or document.get("risk")
        not in {"none", "low", "medium", "high", "critical"}
        or type(document.get("categories")) is not list
    ):
        raise RuntimeError("unexpected bridge result")


def _core(text: str) -> None:
    result = analyze_text(text, disabled_categories=DEFAULT_DISABLED_CATEGORIES)
    if not result.detections:
        raise RuntimeError("synthetic text unexpectedly produced no detections")


def _print_timing(label: str, runs: int, timing: Timing) -> None:
    print(
        f"{label:24} {runs:5d} "
        f"{timing.median_ms:10.3f} {timing.p95_ms:10.3f} "
        f"{timing.p99_ms:10.3f} "
        f"{timing.minimum_ms:10.3f} {timing.maximum_ms:10.3f}"
    )


def run(process_runs: int, target: ProcessTarget) -> int:
    print("CopyPasteBin synthetic performance benchmark")
    print(
        f"Benchmark runner: Python {platform.python_version()} | "
        f"process runs: {process_runs}"
    )
    print("In-process core: current source tree")
    print(f"Process target: {target.label}")
    print("All input is generated locally and contains synthetic values only.")
    print()
    print(
        "measurement               runs  median_ms     p95_ms     p99_ms"
        "     min_ms     max_ms"
    )

    with tempfile.TemporaryDirectory(prefix="cpb-performance-") as temporary:
        root = Path(temporary)
        config_path = root / "missing-synthetic-config.toml"

        if target.supports_filters:
            baseline_state_dir = root / "state-baseline"
            baseline_action = lambda: _filters_status(
                target, baseline_state_dir
            )
        else:
            baseline_action = lambda: _capabilities(target)
        baseline_action()
        baseline = _measure(baseline_action, process_runs)
        _print_timing("process_baseline", process_runs, baseline)

        if target.supports_filters:
            filter_state_dir = root / "state-filter"
            filter_enabled = False

            def toggle_filter() -> None:
                nonlocal filter_enabled
                filter_enabled = not filter_enabled
                _filter_set(target, filter_state_dir, filter_enabled)

            toggle_filter()
            filter_timing = _measure(toggle_filter, process_runs)
            _print_timing("filter_set", process_runs, filter_timing)

        for case in CASES:
            _core(case.text)
            core = _measure(lambda: _core(case.text), case.core_runs)
            _print_timing(f"core_{case.name}", case.core_runs, core)

            state_dir = root / f"state-{case.name}"
            _bridge_observe(target, case.text, state_dir, config_path)
            bridge = _measure(
                lambda: _bridge_observe(
                    target, case.text, state_dir, config_path
                ),
                process_runs,
            )
            _print_timing(f"bridge_{case.name}", process_runs, bridge)
            print(
                f"  {case.name}: {len(case.text.encode('ascii'))} bytes; "
                f"median bridge minus core = "
                f"{bridge.median_ms - core.median_ms:.3f} ms"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--process-runs",
        type=int,
        default=21,
        help="number of fresh Python processes per process measurement (default: 21)",
    )
    parser.add_argument(
        "--entry-point",
        type=Path,
        help="benchmark an installed cpb executable instead of the source tree",
    )
    parser.add_argument(
        "--minimal-bridge",
        action="store_true",
        help="benchmark the experimental source-tree bridge entry point",
    )
    arguments = parser.parse_args()
    if not 5 <= arguments.process_runs <= 100:
        parser.error("--process-runs must be between 5 and 100")
    if arguments.entry_point is not None and arguments.minimal_bridge:
        parser.error("--entry-point and --minimal-bridge are mutually exclusive")
    if arguments.minimal_bridge:
        target = ProcessTarget(
            "experimental minimal bridge",
            (sys.executable, "-m", "copypastebin.bridge_cli"),
            _process_environment(use_source_tree=True),
            supports_filters=False,
        )
    elif arguments.entry_point is None:
        target = ProcessTarget(
            "source tree",
            (sys.executable, "-m", "copypastebin.cli"),
            _process_environment(use_source_tree=True),
        )
    else:
        try:
            entry_point = arguments.entry_point.resolve(strict=True)
        except OSError:
            parser.error("--entry-point does not exist")
        if not entry_point.is_file() or not os.access(entry_point, os.X_OK):
            parser.error("--entry-point must be an executable file")
        target = ProcessTarget(
            str(entry_point),
            (str(entry_point),),
            _process_environment(use_source_tree=False),
        )
    return run(arguments.process_runs, target)


if __name__ == "__main__":
    raise SystemExit(main())
