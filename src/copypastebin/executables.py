from __future__ import annotations

import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path


class ExecutableResolutionError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie odnaleźć programu CopyPasteBin."

    def __repr__(self) -> str:
        return "ExecutableResolutionError(redacted=True)"


def resolve_entry_point(
    *,
    entry_point: Path | None = None,
    entry_point_which: Callable[[str], str | None] | None = None,
) -> Path:
    if entry_point is None:
        selected_which = shutil.which if entry_point_which is None else entry_point_which
        selected_value = selected_which("cpb")
    else:
        selected_value = str(entry_point)
    if (
        type(selected_value) is not str
        or not selected_value
        or any(character in selected_value for character in ("\x00", "\n", "\r"))
    ):
        raise ExecutableResolutionError()
    selected = Path(selected_value)
    if not selected.is_absolute():
        raise ExecutableResolutionError()
    try:
        resolved = selected.resolve(strict=True)
        info = resolved.stat()
    except (OSError, ValueError) as exc:
        raise ExecutableResolutionError() from exc
    if (
        not resolved.is_absolute()
        or not stat.S_ISREG(info.st_mode)
        or not os.access(resolved, os.X_OK)
        or any(character in str(resolved) for character in ("\x00", "\n", "\r"))
    ):
        raise ExecutableResolutionError()
    return resolved
