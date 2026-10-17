from __future__ import annotations

import json
from typing import BinaryIO

from .application import inspect_and_record
from .application_id import MAX_APPLICATION_ID_LENGTH, normalize_application_id
from .clipboard import MAX_INPUT_BYTES
from .config import load_customizations
from .filters import FilterStore
from .history import HistoryStore
from .models import RiskLevel
from .notifications import SafeNotification
from .pause import PauseStore


FRAME_HEADER_BYTES = 4
MAX_BRIDGE_RESULT_BYTES = 2048


class BridgeError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć zdarzenia schowka."

    def __repr__(self) -> str:
        return "BridgeError(redacted=True)"


def observe_framed_event(
    stream: BinaryIO,
    *,
    history: HistoryStore,
    pause: PauseStore,
    config_path=None,
) -> SafeNotification | None:
    if pause.status().paused:
        raise BridgeError()
    header = _read_exact(stream, FRAME_HEADER_BYTES)
    application_length = int.from_bytes(header, "big")
    if application_length > MAX_APPLICATION_ID_LENGTH:
        raise BridgeError()
    application_bytes = _read_exact(stream, application_length)
    try:
        application = normalize_application_id(application_bytes.decode("ascii"))
    except UnicodeDecodeError:
        application = normalize_application_id(None)
    payload = stream.read(MAX_INPUT_BYTES + 1)
    if type(payload) is not bytes or len(payload) > MAX_INPUT_BYTES:
        raise BridgeError()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BridgeError() from exc
    if not text or "\x00" in text:
        raise BridgeError()
    custom_rules, custom_exclusions = load_customizations(config_path)
    result = inspect_and_record(
        text,
        source_kind="clipboard_event",
        source_application=application,
        destination_application="unknown",
        purpose="other",
        history=history,
        custom_rules=custom_rules,
        custom_exclusions=custom_exclusions,
        disabled_categories=FilterStore(history.state_dir).status().disabled,
    )
    if result.analysis.highest_risk is not RiskLevel.NONE:
        return SafeNotification(
            result.analysis.highest_risk,
            result.analysis.category_counts,
        )
    return None


def bridge_result_json(notification: SafeNotification | None) -> str:
    if notification is None:
        payload = {"version": 1, "risk": "none", "categories": []}
    elif type(notification) is SafeNotification:
        payload = {
            "version": 1,
            "risk": notification.risk.value,
            "categories": [list(item) for item in notification.category_counts],
        }
    else:
        raise BridgeError()
    rendered = json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n"
    if len(rendered.encode("ascii")) > MAX_BRIDGE_RESULT_BYTES:
        raise BridgeError()
    return rendered


def _read_exact(stream: BinaryIO, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        part = stream.read(length - len(chunks))
        if type(part) is not bytes or not part:
            raise BridgeError()
        chunks.extend(part)
    return bytes(chunks)
