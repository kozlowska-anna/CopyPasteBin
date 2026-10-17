from __future__ import annotations

import os
import selectors
import shutil
import subprocess
import time

from .input_sources import InputError, MAX_INPUT_BYTES, decode_text


CLIPBOARD_TIMEOUT_SECONDS = 5.0
_READ_CHUNK_BYTES = 64 * 1024


class ClipboardError(Exception):
    def __str__(self) -> str:
        return "Operacja schowka nie powiodła się."

    def __repr__(self) -> str:
        return "ClipboardError(redacted=True)"


def read_clipboard() -> str:
    output = _read_wl_paste(["--no-newline", "--type", "text"], MAX_INPUT_BYTES)
    try:
        return decode_text(output)
    except InputError as exc:
        raise ClipboardError() from exc


def _read_wl_paste(arguments: list[str], max_bytes: int) -> bytes:
    executable = shutil.which("wl-paste")
    if executable is None:
        raise ClipboardError()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [executable, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            close_fds=True,
            bufsize=0,
        )
        return _read_limited_output(process, CLIPBOARD_TIMEOUT_SECONDS, max_bytes)
    except (OSError, subprocess.SubprocessError, ClipboardError) as exc:
        raise ClipboardError() from exc
    finally:
        if process is not None:
            _close_process(process)


def _read_limited_output(
    process: subprocess.Popen[bytes], timeout: float, max_bytes: int
) -> bytes:
    if process.stdout is None:
        raise ClipboardError()
    deadline = time.monotonic() + timeout
    output = bytearray()
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        reached_eof = False
        while not reached_eof:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ClipboardError()
            events = selector.select(remaining)
            if not events:
                raise ClipboardError()
            for key, _ in events:
                bytes_left = max_bytes + 1 - len(output)
                chunk = os.read(key.fileobj.fileno(), min(_READ_CHUNK_BYTES, bytes_left))
                if not chunk:
                    reached_eof = True
                    break
                output.extend(chunk)
                if len(output) > max_bytes:
                    raise ClipboardError()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ClipboardError()
        try:
            return_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise ClipboardError() from exc
        if return_code != 0:
            raise ClipboardError()
        return bytes(output)
    finally:
        selector.close()


def _close_process(process: subprocess.Popen[bytes]) -> None:
    cleanup_failed = False
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
    except (OSError, subprocess.SubprocessError):
        cleanup_failed = True
    finally:
        if process.stdout is not None:
            process.stdout.close()
    if cleanup_failed:
        raise ClipboardError()


def write_clipboard(text: str) -> None:
    executable = shutil.which("wl-copy")
    if executable is None:
        raise ClipboardError()
    try:
        result = subprocess.run([executable, "--type", "text/plain;charset=utf-8"], input=text.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=CLIPBOARD_TIMEOUT_SECONDS, shell=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClipboardError() from exc
    if result.returncode != 0:
        raise ClipboardError()
