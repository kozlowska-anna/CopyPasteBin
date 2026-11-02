Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

from .bridge import (
    BridgeError,
    bridge_result_json,
    capabilities_json,
    observe_framed_event,
)
from .config import ConfigError
from .detection import Bip39ResourceError
from .filters import FilterError
from .history import HistoryError, HistoryStore
from .notifications import NotificationError
from .pause import PauseError, PauseStore


@dataclass(frozen=True, slots=True)
class _Arguments:
    action: str
    state_dir: Path | None
    config_path: Path | None


class _UsageError(Exception):
    pass


def _parse_arguments(arguments: Sequence[str]) -> _Arguments:
    if type(arguments) not in {list, tuple} or any(
        type(value) is not str for value in arguments
    ):
        raise _UsageError()
    remaining = list(arguments)
    state_dir: Path | None = None
    config_path: Path | None = None
    seen: set[str] = set()
    while remaining and remaining[0] in {"--state-dir", "--config"}:
        option = remaining.pop(0)
        if option in seen or not remaining:
            raise _UsageError()
        seen.add(option)
        value = remaining.pop(0)
        if not value or value.startswith("--") or "\x00" in value:
            raise _UsageError()
        if option == "--state-dir":
            state_dir = Path(value)
        else:
            config_path = Path(value)
    if remaining == ["bridge", "capabilities"]:
        action = "capabilities"
    elif remaining == ["bridge", "observe"]:
        action = "observe"
    else:
        raise _UsageError()
    return _Arguments(action, state_dir, config_path)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    try:
        arguments = _parse_arguments(sys.argv[1:] if argv is None else argv)
    except _UsageError:
        stderr.write("cpb-bridge: niepoprawne użycie.\n")
        return 2
    try:
        if arguments.action == "capabilities":
            stdout.write(capabilities_json())
            return 0
        if not hasattr(stdin, "buffer"):
            raise BridgeError()
        result = observe_framed_event(
            stdin.buffer,
            history=HistoryStore(arguments.state_dir),
            pause=PauseStore(arguments.state_dir),
            config_path=arguments.config_path,
        )
        stdout.write(bridge_result_json(result))
        return 0
    except (
        Bip39ResourceError,
        BridgeError,
        ConfigError,
        FilterError,
        HistoryError,
        NotificationError,
        PauseError,
    ):
        stderr.write(
            "Operacja nie powiodła się bez ujawniania danych wejściowych.\n"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
