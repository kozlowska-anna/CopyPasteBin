from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Sequence, TextIO

from .application import NO_GUARANTEE, inspect_and_record, requires_high_risk_confirmation
from .bridge import BridgeError, bridge_result_json, observe_framed_event
from .clipboard import ClipboardError, read_clipboard, write_clipboard
from .config import (
    MAX_CUSTOM_EXCLUSIONS,
    ConfigError,
    load_customizations,
    save_customizations,
)
from .detection import Bip39ResourceError, analyze_text
from .filters import AUTO_CLEAR_CHOICES, FilterError, FilterStore
from .history import HistoryError, HistoryStore
from .input_sources import InputError, read_stream, read_text_file
from .language import LANGUAGE_CHOICES, LanguageError, LanguageStore
from .launcher import LauncherController, LauncherError
from .models import Category
from .notifications import DesktopNotifier, NotificationError
from .pause import (
    PAUSE_1_HOUR,
    PAUSE_30_MINUTES,
    PauseError,
    PauseMode,
    PauseStore,
)
from .safe_text import neutralize_for_terminal
from .ui import (
    UiError,
    auto_clear_json,
    custom_rules_from_json,
    custom_rules_json,
    detections_json,
    exclusion_request_from_json,
    exclusion_result_json,
    filters_json,
    history_json,
    redacted_suggestion,
)
from .service import (
    AutostartStatus,
    ServiceController,
    ServiceError,
    ServiceStatus,
)
from .watcher import (
    BackendStartupFailureCode,
    ClipboardWatcher,
    WatcherError,
    WlPastePollingBackend,
)


PURPOSES = ("chat", "email", "drive", "terminal", "other")


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, "cpb: niepoprawne użycie.\n")


def _parser() -> SafeArgumentParser:
    parser = SafeArgumentParser(prog="cpb")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("history").set_defaults(command="history")
    show = subparsers.add_parser("show")
    show.add_argument("operation_id")
    show.set_defaults(command="show")
    watch = subparsers.add_parser("watch")
    watch_actions = watch.add_subparsers(dest="watch_action", required=True)
    watch_actions.add_parser("start")
    watch.set_defaults(command="watch")
    service = subparsers.add_parser("service")
    service_actions = service.add_subparsers(dest="service_action", required=True)
    for action in (
        "setup",
        "start",
        "stop",
        "status",
        "enable",
        "disable",
        "autostart",
    ):
        service_actions.add_parser(action)
    service.set_defaults(command="service")
    launcher = subparsers.add_parser("launcher")
    launcher_actions = launcher.add_subparsers(
        dest="launcher_action", required=True
    )
    launcher_actions.add_parser("setup")
    launcher.set_defaults(command="launcher")
    pause = subparsers.add_parser("pause")
    pause_actions = pause.add_subparsers(dest="pause_action", required=True)
    for action in ("30m", "1h", "until-resumed", "resume", "status"):
        pause_actions.add_parser(action)
    pause.set_defaults(command="pause")
    bridge = subparsers.add_parser("bridge", help=argparse.SUPPRESS)
    bridge_actions = bridge.add_subparsers(dest="bridge_action", required=True)
    bridge_actions.add_parser("observe", help=argparse.SUPPRESS)
    bridge.set_defaults(command="bridge")
    ui = subparsers.add_parser("ui", help=argparse.SUPPRESS)
    ui_actions = ui.add_subparsers(dest="ui_action", required=True)
    ui_actions.add_parser("history", help=argparse.SUPPRESS)
    ui_actions.add_parser("redact", help=argparse.SUPPRESS)
    ui_actions.add_parser("filters", help=argparse.SUPPRESS)
    ui_actions.add_parser("auto-clear", help=argparse.SUPPRESS)
    auto_clear_set = ui_actions.add_parser("auto-clear-set", help=argparse.SUPPRESS)
    auto_clear_set.add_argument(
        "seconds", choices=tuple(str(value) for value in AUTO_CLEAR_CHOICES)
    )
    ui_actions.add_parser("detections", help=argparse.SUPPRESS)
    ui_actions.add_parser("rules", help=argparse.SUPPRESS)
    ui_actions.add_parser("rules-save", help=argparse.SUPPRESS)
    ui_actions.add_parser("exclusion-add", help=argparse.SUPPRESS)
    ui_actions.add_parser("language", help=argparse.SUPPRESS)
    language_set = ui_actions.add_parser("language-set", help=argparse.SUPPRESS)
    language_set.add_argument("language", choices=LANGUAGE_CHOICES)
    filter_set = ui_actions.add_parser("filter-set", help=argparse.SUPPRESS)
    filter_set.add_argument("category", choices=tuple(item.value for item in Category))
    filter_set.add_argument("filter_state", choices=("on", "off"))
    ui.set_defaults(command="ui")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--clipboard", action="store_true")
    parser.add_argument("--purpose", choices=PURPOSES, default="other")
    parser.add_argument("--copy", choices=("redacted", "original"))
    parser.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--config", type=Path, help=argparse.SUPPRESS)
    return parser


def _write_analysis(result, output: TextIO) -> None:
    output.write(f"operation_id={result.operation_id}\n")
    output.write(f"risk={result.analysis.highest_risk.value}\n")
    for category, count in result.analysis.category_counts:
        output.write(f"category={category} count={count}\n")
    if not result.analysis.detections:
        output.write(NO_GUARANTEE + "\n")
    output.write("redacted_preview_begin\n")
    output.write(neutralize_for_terminal(result.analysis.redacted_text) + "\n")
    output.write("redacted_preview_end\n")


def _input(args, stdin: TextIO) -> tuple[str, str]:
    if args.file is not None and args.clipboard:
        raise InputError()
    if args.file is not None:
        return read_text_file(args.file), "file"
    if args.clipboard:
        return read_clipboard(), "clipboard"
    return read_stream(stdin.buffer), "stdin"


def _history_output(store: HistoryStore, output: TextIO) -> None:
    for entry in store.recent():
        summary = ",".join(f"{name}:{count}" for name, count in entry.category_counts) or "none"
        output.write(f"id={entry.operation_id} time={entry.created_at} source={entry.source_kind} from={entry.source_application} to={entry.destination_application} purpose={entry.purpose} risk={entry.highest_risk} categories={summary} status={entry.status}\n")


def _show_output(store: HistoryStore, operation_id: str, output: TextIO) -> int:
    entry = store.get(operation_id)
    if entry is None:
        output.write("Nie znaleziono operacji.\n")
        return 1
    summary = ",".join(f"{name}:{count}" for name, count in entry.category_counts) or "none"
    output.write(f"id={entry.operation_id}\ntime={entry.created_at}\nsource={entry.source_kind}\nfrom={entry.source_application}\nto={entry.destination_application}\npurpose={entry.purpose}\nrisk={entry.highest_risk}\ncategories={summary}\nstatus={entry.status}\nruleset={entry.ruleset_version}\n")
    return 0


def _journal_context_present() -> bool:
    return bool(os.environ.get("INVOCATION_ID")) and bool(
        os.environ.get("JOURNAL_STREAM")
    )


def _emit_backend_startup_failure(
    code: BackendStartupFailureCode, output: TextIO
) -> None:
    if type(code) is not BackendStartupFailureCode:
        raise TypeError("code must be BackendStartupFailureCode")
    if _journal_context_present():
        output.write(f"CopyPasteBin diagnostic code: {code.value}\n")


def _run_foreground_watcher(
    args, store: HistoryStore, output: TextIO, diagnostic_output: TextIO
) -> int:
    custom_rules, custom_exclusions = load_customizations(args.config)
    watcher = ClipboardWatcher(
        WlPastePollingBackend(),
        DesktopNotifier(),
        store,
        custom_rules=custom_rules,
        custom_exclusions=custom_exclusions,
        purpose=args.purpose,
    )
    output.write(
        "Watcher uruchamia się w trybie pierwszoplanowym. "
        "Zatrzymaj go przez Ctrl+C.\n"
    )
    try:
        watcher.run_forever(
            startup_backend_failure=lambda code: _emit_backend_startup_failure(
                code, diagnostic_output
            )
        )
    except KeyboardInterrupt:
        output.write("Watcher zatrzymany.\n")
    return 0


def _run_service(args, output: TextIO) -> int:
    controller = ServiceController()
    if args.service_action == "setup":
        controller.setup()
        output.write("CopyPasteBin service: CONFIGURED\n")
        return 0
    if args.service_action == "enable":
        status = controller.enable()
        output.write(f"CopyPasteBin autostart: {status.value}\n")
        return 0
    if args.service_action == "disable":
        status = controller.disable()
        output.write(f"CopyPasteBin autostart: {status.value}\n")
        return 0
    if args.service_action == "autostart":
        status = controller.autostart()
        output.write(f"CopyPasteBin autostart: {status.value}\n")
        if status is AutostartStatus.UNKNOWN:
            return 1
        return 0
    if args.service_action == "start":
        status = controller.start()
    elif args.service_action == "stop":
        status = controller.stop()
    else:
        status = controller.status()
    output.write(f"CopyPasteBin service: {status.value}\n")
    if args.service_action == "status" and status is not ServiceStatus.RUNNING:
        return 1
    return 0


def _run_launcher(args, output: TextIO) -> int:
    controller = LauncherController()
    if args.launcher_action == "setup":
        controller.setup()
        output.write("CopyPasteBin launcher: CONFIGURED\n")
        return 0
    raise LauncherError()


def _pause_output(status, output: TextIO) -> None:
    if status.mode is PauseMode.ACTIVE:
        output.write("CopyPasteBin pause: ACTIVE\n")
    elif status.mode is PauseMode.INDEFINITE:
        output.write("CopyPasteBin pause: PAUSED_INDEFINITE\n")
    else:
        output.write(
            "CopyPasteBin pause: PAUSED_TIMED "
            f"remaining_seconds={status.remaining_seconds}\n"
        )


def _run_pause(args, output: TextIO) -> int:
    store = PauseStore(args.state_dir)
    if args.pause_action == "30m":
        status = store.pause_for(PAUSE_30_MINUTES)
    elif args.pause_action == "1h":
        status = store.pause_for(PAUSE_1_HOUR)
    elif args.pause_action == "until-resumed":
        status = store.pause_indefinitely()
    elif args.pause_action == "resume":
        status = store.resume()
    else:
        status = store.status()
    _pause_output(status, output)
    return 0


def _run_bridge(args, store: HistoryStore, stdin: TextIO, output: TextIO) -> int:
    if args.bridge_action != "observe" or not hasattr(stdin, "buffer"):
        raise BridgeError()
    result = observe_framed_event(
        stdin.buffer,
        history=store,
        pause=PauseStore(args.state_dir),
        config_path=args.config,
    )
    output.write(bridge_result_json(result))
    return 0


def _run_ui(args, store: HistoryStore, stdin: TextIO, output: TextIO) -> int:
    if args.ui_action == "history":
        output.write(history_json(store))
        return 0
    filter_store = FilterStore(args.state_dir)
    if args.ui_action in {"language", "language-set"}:
        language_store = LanguageStore(args.state_dir)
        status = (
            language_store.set_choice(args.language)
            if args.ui_action == "language-set"
            else language_store.status()
        )
        output.write(
            json.dumps(
                {
                    "version": 1,
                    "choice": status.choice,
                    "effective": status.effective,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    if args.ui_action == "filters":
        output.write(filters_json(filter_store.status()))
        return 0
    if args.ui_action == "filter-set":
        status = filter_store.set_enabled(
            Category(args.category), args.filter_state == "on"
        )
        output.write(filters_json(status))
        return 0
    if args.ui_action == "auto-clear":
        output.write(auto_clear_json(filter_store.status()))
        return 0
    if args.ui_action == "auto-clear-set":
        output.write(auto_clear_json(filter_store.set_auto_clear(int(args.seconds))))
        return 0
    if args.ui_action == "rules":
        rules, exclusions = load_customizations(args.config)
        output.write(custom_rules_json(rules, exclusions))
        return 0
    if args.ui_action == "rules-save":
        if not hasattr(stdin, "buffer"):
            raise UiError()
        rules, exclusions = custom_rules_from_json(read_stream(stdin.buffer))
        save_customizations(rules, exclusions, args.config)
        output.write(custom_rules_json(rules, exclusions))
        return 0
    if args.ui_action == "exclusion-add":
        if not hasattr(stdin, "buffer"):
            raise UiError()
        proposed = exclusion_request_from_json(read_stream(stdin.buffer))
        rules, exclusions = load_customizations(args.config)
        if any(rule.literal == proposed.literal for rule in rules):
            output.write(exclusion_result_json("conflict"))
            return 0
        for index, exclusion in enumerate(exclusions):
            if exclusion.literal != proposed.literal:
                continue
            if exclusion.category is not proposed.category:
                output.write(exclusion_result_json("conflict"))
                return 0
            if exclusion.enabled:
                output.write(exclusion_result_json("exists"))
                return 0
            updated = exclusions[:index] + (proposed,) + exclusions[index + 1:]
            save_customizations(rules, updated, args.config)
            output.write(exclusion_result_json("enabled"))
            return 0
        if len(exclusions) >= MAX_CUSTOM_EXCLUSIONS:
            output.write(exclusion_result_json("limit"))
            return 0
        save_customizations(rules, exclusions + (proposed,), args.config)
        output.write(exclusion_result_json("added"))
        return 0
    if args.ui_action not in {"redact", "detections"} or not hasattr(stdin, "buffer"):
        raise UiError()
    if PauseStore(args.state_dir).status().paused:
        raise UiError()
    text = read_stream(stdin.buffer)
    custom_rules, custom_exclusions = load_customizations(args.config)
    status = filter_store.status()
    if args.ui_action == "detections":
        output.write(
            detections_json(
                analyze_text(
                    text,
                    custom_rules,
                    status.disabled,
                    custom_exclusions,
                )
            )
        )
    else:
        output.write(
            redacted_suggestion(
                text,
                custom_rules,
                status.disabled,
                custom_exclusions,
            )
        )
    return 0


def main(argv: Sequence[str] | None = None, *, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    parser = _parser()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    store = HistoryStore(args.state_dir)
    try:
        if args.command == "history":
            _history_output(store, stdout)
            return 0
        if args.command == "show":
            return _show_output(store, args.operation_id, stdout)
        if args.command == "watch":
            return _run_foreground_watcher(args, store, stdout, stderr)
        if args.command == "service":
            return _run_service(args, stdout)
        if args.command == "launcher":
            return _run_launcher(args, stdout)
        if args.command == "pause":
            return _run_pause(args, stdout)
        if args.command == "bridge":
            return _run_bridge(args, store, stdin, stdout)
        if args.command == "ui":
            return _run_ui(args, store, stdin, stdout)
        text, source = _input(args, stdin)
        if not text:
            stderr.write("Nie można przetworzyć pustego tekstu.\n")
            return 1
        custom_rules, custom_exclusions = load_customizations(args.config)
        result = inspect_and_record(text, source_kind=source, purpose=args.purpose, history=store, custom_rules=custom_rules, disabled_categories=FilterStore(args.state_dir).status().disabled, custom_exclusions=custom_exclusions)
        _write_analysis(result, stdout)
        if args.copy is None:
            return 0
        if args.copy == "redacted":
            try:
                write_clipboard(result.analysis.redacted_text)
            except ClipboardError:
                store.set_outcome(result.operation_id, "failed")
                raise
            store.set_outcome(result.operation_id, "copied_redacted")
            return 0
        if requires_high_risk_confirmation(result.analysis):
            stderr.write(f"Wysokie ryzyko. Aby jednorazowo skopiować oryginał, wpisz: COPY {result.operation_id}\n")
            confirmation = stdin.readline().rstrip("\n")
            if not hmac.compare_digest(confirmation.encode(), f"COPY {result.operation_id}".encode()):
                store.set_outcome(result.operation_id, "cancelled")
                stderr.write("Operacja anulowana.\n")
                return 1
        try:
            write_clipboard(text)
        except ClipboardError:
            store.set_outcome(result.operation_id, "failed")
            raise
        store.set_outcome(result.operation_id, "copied_original", exception_used=requires_high_risk_confirmation(result.analysis))
        return 0
    except WatcherError as exc:
        if (
            exc.lifecycle_reason is not None
            and _journal_context_present()
        ):
            stderr.write(
                "CopyPasteBin diagnostic code: "
                f"LIFECYCLE_{exc.lifecycle_reason.value}\n"
            )
        stderr.write("Operacja nie powiodła się bez ujawniania danych wejściowych.\n")
        return 1
    except (
        InputError,
        ClipboardError,
        ConfigError,
        HistoryError,
        Bip39ResourceError,
        NotificationError,
        ServiceError,
        LauncherError,
        PauseError,
        FilterError,
        LanguageError,
        BridgeError,
        UiError,
    ):
        stderr.write("Operacja nie powiodła się bez ujawniania danych wejściowych.\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
