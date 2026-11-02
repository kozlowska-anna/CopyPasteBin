from __future__ import annotations

import io
import json
import os
import selectors
import time
from pathlib import Path
from typing import BinaryIO

from . import __version__
from .application_id import MAX_APPLICATION_ID_LENGTH
from .bridge import (
    BACKEND_PROTOCOL_VERSION,
    FRAME_HEADER_BYTES,
    bridge_result_json,
    observe_framed_event,
)
from .history import HistoryStore
from .input_sources import MAX_INPUT_BYTES
from .pause import PauseStore


WORKER_PROTOCOL_VERSION = 1
WORKER_DOCUMENT_VERSION = 1
WORKER_FRAME_HEADER_BYTES = 4
MAX_WORKER_REQUEST_BYTES = (
    FRAME_HEADER_BYTES + MAX_APPLICATION_ID_LENGTH + MAX_INPUT_BYTES
)
MAX_WORKER_RESPONSE_BYTES = 2048
WORKER_IDLE_TIMEOUT_SECONDS = 30.0
MIN_WORKER_IDLE_TIMEOUT_SECONDS = 0.05
MAX_WORKER_IDLE_TIMEOUT_SECONDS = 3600.0


class BridgeWorkerError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć procesu analizy."

    def __repr__(self) -> str:
        return "BridgeWorkerError(redacted=True)"


class _IdleExit(Exception):
    pass


def worker_capabilities_json() -> bytes:
    return (
        json.dumps(
            {
                "document_version": WORKER_DOCUMENT_VERSION,
                "product_version": __version__,
                "protocol_version": BACKEND_PROTOCOL_VERSION,
                "worker_protocol_version": WORKER_PROTOCOL_VERSION,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _read_exact(
    descriptor: int,
    selector: selectors.BaseSelector,
    length: int,
    timeout: float,
    *,
    allow_clean_eof: bool = False,
) -> bytes | None:
    deadline = time.monotonic() + timeout
    chunks = bytearray()
    while len(chunks) < length:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not selector.select(remaining):
            if not chunks and allow_clean_eof:
                raise _IdleExit()
            raise BridgeWorkerError()
        try:
            part = os.read(descriptor, length - len(chunks))
        except OSError as exc:
            raise BridgeWorkerError() from exc
        if not part:
            if not chunks and allow_clean_eof:
                return None
            raise BridgeWorkerError()
        chunks.extend(part)
    return bytes(chunks)


def _read_request(
    descriptor: int,
    selector: selectors.BaseSelector,
    timeout: float,
) -> bytes | None:
    header = _read_exact(
        descriptor,
        selector,
        WORKER_FRAME_HEADER_BYTES,
        timeout,
        allow_clean_eof=True,
    )
    if header is None:
        return None
    length = int.from_bytes(header, "big")
    if not 1 <= length <= MAX_WORKER_REQUEST_BYTES:
        raise BridgeWorkerError()
    return _read_exact(descriptor, selector, length, timeout)


def _write_response(stream: BinaryIO, payload: bytes) -> None:
    if not payload or len(payload) > MAX_WORKER_RESPONSE_BYTES:
        raise BridgeWorkerError()
    try:
        framed = memoryview(
            len(payload).to_bytes(WORKER_FRAME_HEADER_BYTES, "big") + payload
        )
        while framed:
            written = stream.write(framed)
            if not isinstance(written, int) or written <= 0:
                raise BridgeWorkerError()
            framed = framed[written:]
        stream.flush()
    except (BrokenPipeError, OSError) as exc:
        raise BridgeWorkerError() from exc


def run_bridge_worker(
    input_stream: BinaryIO,
    output_stream: BinaryIO,
    *,
    state_dir: Path | None = None,
    config_path: Path | None = None,
    idle_timeout: float = WORKER_IDLE_TIMEOUT_SECONDS,
) -> int:
    if (
        not isinstance(idle_timeout, (int, float))
        or isinstance(idle_timeout, bool)
        or not MIN_WORKER_IDLE_TIMEOUT_SECONDS
        <= idle_timeout
        <= MAX_WORKER_IDLE_TIMEOUT_SECONDS
    ):
        raise BridgeWorkerError()
    try:
        descriptor = input_stream.fileno()
    except (AttributeError, OSError) as exc:
        raise BridgeWorkerError() from exc
    history = HistoryStore(state_dir)
    pause = PauseStore(state_dir)
    selector = selectors.DefaultSelector()
    try:
        selector.register(descriptor, selectors.EVENT_READ)
        _write_response(output_stream, worker_capabilities_json())
        while True:
            try:
                request = _read_request(descriptor, selector, float(idle_timeout))
            except _IdleExit:
                return 0
            if request is None:
                return 0
            notification = observe_framed_event(
                io.BytesIO(request),
                history=history,
                pause=pause,
                config_path=config_path,
            )
            rendered = bridge_result_json(notification).encode("ascii")
            _write_response(output_stream, rendered)
            del notification, rendered, request
    finally:
        selector.close()
