from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import BinaryIO


MAX_INPUT_BYTES = 10 * 1024 * 1024


class InputError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie odczytać tekstu wejściowego."

    def __repr__(self) -> str:
        return "InputError(redacted=True)"


def decode_text(data: bytes) -> str:
    if len(data) > MAX_INPUT_BYTES or b"\x00" in data:
        raise InputError()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError() from exc


def read_stream(stream: BinaryIO) -> str:
    try:
        data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise InputError() from exc
    if len(data) > MAX_INPUT_BYTES:
        raise InputError()
    return decode_text(data)


def read_text_file(path: Path) -> str:
    if not hasattr(os, "O_NOFOLLOW"):
        raise InputError()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InputError() from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise InputError()
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return read_stream(stream)
    finally:
        os.close(descriptor)
