#!/usr/bin/env python3
"""Synthetic performance and lifecycle probe for the persistent worker prototype."""

from __future__ import annotations

import json
import math
import os
import selectors
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
WORKER = ROOT / "benchmarks" / "prototypes" / "persistent_bridge_worker.py"
APPLICATION_ID = b"synthetic.persistent-benchmark"
IO_TIMEOUT_SECONDS = 5.0
OUTER_HEADER_BYTES = 4


class WorkerFailure(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Timing:
    median_ms: float
    p95_ms: float
    p99_ms: float
    minimum_ms: float
    maximum_ms: float


def synthetic_text(size: int) -> str:
    suffix = (
        " Contact: person@example.invalid; phone: +48 123 456 789; "
        "key: sk-proj-CPBINSYNTHETIC0123456789abcdef."
    )
    filler = "CPB synthetic persistent benchmark text; "
    if size < len(suffix):
        raise ValueError("synthetic case is too small")
    repeated = (filler * math.ceil((size - len(suffix)) / len(filler)))[
        : size - len(suffix)
    ]
    return repeated + suffix


def _percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percentage) - 1)]


def _timing(values: list[float]) -> Timing:
    return Timing(
        statistics.median(values),
        _percentile(values, 0.95),
        _percentile(values, 0.99),
        min(values),
        max(values),
    )


class PersistentWorker:
    def __init__(
        self,
        state_dir: Path,
        config_path: Path,
        *,
        idle_timeout: float = 30.0,
    ) -> None:
        environment = {
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(SOURCE),
        }
        started = time.perf_counter_ns()
        command = (
            (
                sys.executable,
                "-m",
                "copypastebin.cli",
                "--state-dir",
                str(state_dir),
                "--config",
                str(config_path),
                "bridge",
                "worker",
            )
            if idle_timeout == 30.0
            else (
                sys.executable,
                str(WORKER),
                "--state-dir",
                str(state_dir),
                "--config",
                str(config_path),
                "--idle-timeout",
                str(idle_timeout),
            )
        )
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            close_fds=True,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise WorkerFailure("worker pipes are unavailable")
        self._selector = selectors.DefaultSelector()
        self._selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            capabilities = self._read_document()
            self.startup_ms = (time.perf_counter_ns() - started) / 1_000_000
            if (
                set(capabilities)
                != {
                    "document_version",
                    "product_version",
                    "protocol_version",
                    "worker_protocol_version",
                }
                or capabilities.get("document_version") != 1
                or capabilities.get("protocol_version") != 2
                or capabilities.get("worker_protocol_version") != 1
            ):
                raise WorkerFailure("unexpected worker capabilities")
        except Exception:
            self._selector.close()
            if self.process.stdin is not None:
                self.process.stdin.close()
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=2)
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.stderr is not None:
                self.process.stderr.close()
            raise

    def _read_exact(self, length: int) -> bytes:
        if self.process.stdout is None:
            raise WorkerFailure("worker stdout is unavailable")
        deadline = time.monotonic() + IO_TIMEOUT_SECONDS
        chunks = bytearray()
        while len(chunks) < length:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._selector.select(remaining):
                raise WorkerFailure("worker response timed out")
            part = os.read(self.process.stdout.fileno(), length - len(chunks))
            if not part:
                raise WorkerFailure("worker response ended early")
            chunks.extend(part)
        return bytes(chunks)

    def _read_document(self) -> dict:
        length = int.from_bytes(self._read_exact(OUTER_HEADER_BYTES), "big")
        if not 1 <= length <= 2048:
            raise WorkerFailure("worker response length is invalid")
        try:
            document = json.loads(self._read_exact(length).decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerFailure("worker response is invalid") from exc
        if type(document) is not dict:
            raise WorkerFailure("worker response is not a document")
        return document

    def request_payload(self, payload: bytes) -> dict:
        if self.process.stdin is None:
            raise WorkerFailure("worker stdin is unavailable")
        try:
            self.process.stdin.write(
                len(payload).to_bytes(OUTER_HEADER_BYTES, "big") + payload
            )
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise WorkerFailure("worker request failed") from exc
        return self._read_document()

    def request(self, text: str) -> dict:
        content = text.encode("ascii")
        inner = (
            len(APPLICATION_ID).to_bytes(4, "big")
            + APPLICATION_ID
            + content
        )
        document = self.request_payload(inner)
        if (
            document.get("version") != 1
            or document.get("risk")
            not in {"none", "low", "medium", "high", "critical"}
            or type(document.get("categories")) is not list
            or type(document.get("history_eligible")) is not bool
        ):
            raise WorkerFailure("worker bridge result is invalid")
        return document

    def rss_kib(self) -> int | None:
        try:
            lines = Path(f"/proc/{self.process.pid}/status").read_text(
                encoding="ascii"
            ).splitlines()
        except OSError:
            return None
        for line in lines:
            if line.startswith("VmRSS:"):
                fields = line.split()
                if len(fields) == 3 and fields[2] == "kB":
                    return int(fields[1])
        return None

    def cpu_seconds(self) -> float | None:
        try:
            data = Path(f"/proc/{self.process.pid}/stat").read_text(
                encoding="ascii"
            )
            fields = data[data.rfind(")") + 2 :].split()
            ticks = int(fields[11]) + int(fields[12])
            return ticks / os.sysconf("SC_CLK_TCK")
        except (OSError, ValueError, IndexError):
            return None

    def close(self, *, expected_code: int = 0) -> None:
        self._selector.close()
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
            raise WorkerFailure("worker did not exit after stdin closed")
        finally:
            if self.process.stdout is not None:
                self.process.stdout.close()
            if self.process.stderr is not None:
                self.process.stderr.close()
        if code != expected_code:
            raise WorkerFailure(f"worker exited with status {code}")


def _measure(worker: PersistentWorker, text: str, runs: int) -> Timing:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter_ns()
        worker.request(text)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return _timing(samples)


def _print_timing(label: str, runs: int, timing: Timing) -> None:
    print(
        f"{label:22} {runs:5d} "
        f"{timing.median_ms:10.3f} {timing.p95_ms:10.3f} "
        f"{timing.p99_ms:10.3f} "
        f"{timing.minimum_ms:10.3f} {timing.maximum_ms:10.3f}"
    )


def run() -> int:
    cases = (
        ("warm_short", synthetic_text(256), 200),
        ("warm_medium", synthetic_text(4 * 1024), 100),
        ("warm_large", synthetic_text(64 * 1024), 20),
    )
    with tempfile.TemporaryDirectory(prefix="cpb-persistent-") as temporary:
        root = Path(temporary)
        worker = PersistentWorker(
            root / "state",
            root / "missing-synthetic-config.toml",
        )
        print("CopyPasteBin persistent bridge prototype benchmark")
        print("All input and state are synthetic and temporary.")
        print(f"startup_handshake_ms={worker.startup_ms:.3f}")
        print(f"rss_after_handshake_kib={worker.rss_kib()}")

        first_text = cases[0][1]
        started = time.perf_counter_ns()
        worker.request(first_text)
        first_request_ms = (time.perf_counter_ns() - started) / 1_000_000
        print(f"first_request_ms={first_request_ms:.3f}")
        print(f"rss_after_first_request_kib={worker.rss_kib()}")
        print()
        print(
            "measurement             runs  median_ms     p95_ms     p99_ms"
            "     min_ms     max_ms"
        )
        for label, text, runs in cases:
            _print_timing(label, runs, _measure(worker, text, runs))

        stability_before = worker.rss_kib()
        _print_timing(
            "stability_short",
            1000,
            _measure(worker, cases[0][1], 1000),
        )
        stability_after = worker.rss_kib()

        before = worker.cpu_seconds()
        time.sleep(0.5)
        after = worker.cpu_seconds()
        idle_cpu = None if before is None or after is None else after - before
        print()
        print(f"idle_500ms_cpu_seconds={idle_cpu}")
        print(f"rss_final_kib={worker.rss_kib()}")
        print(f"rss_stability_before_kib={stability_before}")
        print(f"rss_stability_after_kib={stability_after}")
        closing_started = time.perf_counter_ns()
        worker.close()
        print(
            "worker_close_ms="
            f"{(time.perf_counter_ns() - closing_started) / 1_000_000:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
