from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Protocol

from .application import inspect_and_record
from .clipboard import ClipboardError, read_clipboard
from .detection import CustomLiteralExclusion, CustomLiteralRule
from .history import HistoryStore
from .lifecycle import LifecycleError, LifecycleFailureReason, WatcherRuntime
from .models import RiskLevel
from .notifications import NotificationError, SafeNotification


DEFAULT_POLL_INTERVAL_SECONDS = 1.0
STARTUP_BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)


class BackendStartupFailureCode(StrEnum):
    ATTEMPT_1_FAILED = "BACKEND_STARTUP_ATTEMPT_1_FAILED"
    ATTEMPT_2_FAILED = "BACKEND_STARTUP_ATTEMPT_2_FAILED"
    ATTEMPT_3_FAILED = "BACKEND_STARTUP_ATTEMPT_3_FAILED"
    LATE_ATTEMPT_FAILED = "BACKEND_STARTUP_LATE_ATTEMPT_FAILED"
    GRACE_EXHAUSTED = "BACKEND_STARTUP_GRACE_EXHAUSTED"


_BACKEND_STARTUP_FAILURE_CODES = (
    BackendStartupFailureCode.ATTEMPT_1_FAILED,
    BackendStartupFailureCode.ATTEMPT_2_FAILED,
    BackendStartupFailureCode.ATTEMPT_3_FAILED,
    BackendStartupFailureCode.LATE_ATTEMPT_FAILED,
    BackendStartupFailureCode.LATE_ATTEMPT_FAILED,
)


class WatcherError(Exception):
    __slots__ = ("_lifecycle_reason",)

    def __init__(
        self,
        *args: object,
        lifecycle_reason: LifecycleFailureReason | None = None,
    ) -> None:
        if (
            lifecycle_reason is not None
            and type(lifecycle_reason) is not LifecycleFailureReason
        ):
            raise TypeError("lifecycle_reason must be LifecycleFailureReason or None")
        super().__init__()
        self._lifecycle_reason = lifecycle_reason

    @property
    def lifecycle_reason(self) -> LifecycleFailureReason | None:
        return self._lifecycle_reason

    def __str__(self) -> str:
        return "Watcher schowka zatrzymał się bez ujawniania danych."

    def __repr__(self) -> str:
        return "WatcherError(redacted=True)"


class WatcherBackendError(WatcherError):
    def __repr__(self) -> str:
        return "WatcherBackendError(redacted=True)"


class ClipboardSampleKind(StrEnum):
    TEXT = "text"
    EMPTY = "empty"
    NON_TEXT = "non_text"


@dataclass(frozen=True, slots=True, repr=False)
class ClipboardSample:
    kind: ClipboardSampleKind
    text: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ClipboardSampleKind:
            raise WatcherError()
        if self.kind is ClipboardSampleKind.TEXT:
            if type(self.text) is not str or not self.text:
                raise WatcherError()
        elif self.text is not None:
            raise WatcherError()

    def __repr__(self) -> str:
        return f"ClipboardSample(kind={self.kind.value!r}, content_redacted=True)"


class WatcherState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"


class WatchCycleOutcome(StrEnum):
    ANALYZED = "analyzed"
    DUPLICATE = "duplicate"
    EMPTY = "empty"
    NON_TEXT = "non_text"


class ClipboardBackend(Protocol):
    def read(self) -> ClipboardSample: ...


class Notifier(Protocol):
    def notify(self, notification: SafeNotification) -> None: ...


class WlPastePollingBackend:
    def read(self) -> ClipboardSample:
        try:
            text = read_clipboard()
        except ClipboardError as exc:
            raise WatcherBackendError() from exc
        if not text:
            return ClipboardSample(ClipboardSampleKind.EMPTY)
        return ClipboardSample(ClipboardSampleKind.TEXT, text)


class ClipboardWatcher:
    def __init__(
        self,
        backend: ClipboardBackend,
        notifier: Notifier,
        history: HistoryStore,
        *,
        custom_rules: tuple[CustomLiteralRule, ...] = (),
        custom_exclusions: tuple[CustomLiteralExclusion, ...] = (),
        purpose: str = "other",
        deduplication_key: bytes | None = None,
        runtime: WatcherRuntime | None = None,
    ) -> None:
        key = deduplication_key if deduplication_key is not None else os.urandom(32)
        if type(key) is not bytes or len(key) != 32:
            raise WatcherError()
        if type(purpose) is not str or purpose not in {
            "chat",
            "email",
            "drive",
            "terminal",
            "other",
        }:
            raise WatcherError()
        self._backend = backend
        self._notifier = notifier
        self._history = history
        self._custom_rules = custom_rules
        self._custom_exclusions = custom_exclusions
        self._purpose = purpose
        self._deduplication_key = key
        self._last_fingerprint: bytes | None = None
        self._state = WatcherState.STOPPED
        self._runtime = runtime if runtime is not None else WatcherRuntime()

    @property
    def state(self) -> WatcherState:
        return self._state

    def start(self) -> None:
        if self._state is not WatcherState.STOPPED:
            raise WatcherError()
        self._state = WatcherState.RUNNING

    def stop(self) -> None:
        self._state = WatcherState.STOPPED

    def poll_once(self) -> WatchCycleOutcome:
        if self._state is not WatcherState.RUNNING:
            raise WatcherError()
        sample = self._backend.read()
        if type(sample) is not ClipboardSample:
            raise WatcherError()
        if sample.kind is ClipboardSampleKind.NON_TEXT:
            self._last_fingerprint = self._fingerprint_marker(b"non-text")
            return WatchCycleOutcome.NON_TEXT
        if sample.kind is ClipboardSampleKind.EMPTY:
            self._last_fingerprint = self._fingerprint_marker(b"empty")
            return WatchCycleOutcome.EMPTY
        assert sample.text is not None
        fingerprint = hmac.new(
            self._deduplication_key,
            b"text\x00" + sample.text.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if self._last_fingerprint is not None and hmac.compare_digest(
            fingerprint, self._last_fingerprint
        ):
            return WatchCycleOutcome.DUPLICATE
        result = inspect_and_record(
            sample.text,
            source_kind="clipboard_watcher",
            purpose=self._purpose,
            history=self._history,
            custom_rules=self._custom_rules,
            custom_exclusions=self._custom_exclusions,
        )
        if result.analysis.highest_risk is not RiskLevel.NONE:
            try:
                self._notifier.notify(
                    SafeNotification(
                        result.analysis.highest_risk, result.analysis.category_counts
                    )
                )
            except NotificationError:
                try:
                    self._history.set_outcome(result.operation_id, "failed")
                finally:
                    self.stop()
                raise
        self._last_fingerprint = fingerprint
        return WatchCycleOutcome.ANALYZED

    def run_forever(
        self,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        startup_backend_failure: Callable[[BackendStartupFailureCode], None]
        | None = None,
    ) -> None:
        if type(poll_interval) is not float or poll_interval <= 0:
            raise WatcherError()
        try:
            with self._runtime:
                self.start()
                try:
                    for failure_code, backoff in zip(
                        _BACKEND_STARTUP_FAILURE_CODES,
                        (*STARTUP_BACKOFF_SECONDS, None),
                        strict=True,
                    ):
                        try:
                            self.poll_once()
                            break
                        except WatcherBackendError:
                            if startup_backend_failure is not None:
                                startup_backend_failure(failure_code)
                            if backoff is None:
                                if startup_backend_failure is not None:
                                    startup_backend_failure(
                                        BackendStartupFailureCode.GRACE_EXHAUSTED
                                    )
                                raise
                            sleep(backoff)
                    while self._state is WatcherState.RUNNING:
                        sleep(poll_interval)
                        self.poll_once()
                finally:
                    self.stop()
        except LifecycleError as exc:
            raise WatcherError(lifecycle_reason=exc.reason) from exc

    def _fingerprint_marker(self, marker: bytes) -> bytes:
        return hmac.new(
            self._deduplication_key, b"state\x00" + marker, hashlib.sha256
        ).digest()
