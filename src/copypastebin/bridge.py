Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import BinaryIO

from . import __version__
from .application_id import MAX_APPLICATION_ID_LENGTH, normalize_application_id
from .config import load_customizations
from .detection import RULESET_VERSION, analysis_from_detections, detect_text
from .filters import FilterStore
from .history import HistoryStore
from .history_policy import history_text_is_eligible
from .input_sources import MAX_INPUT_BYTES
from .models import RiskLevel
from .notifications import SafeNotification
from .pause import PauseStore


FRAME_HEADER_BYTES = 4
MAX_BRIDGE_RESULT_BYTES = 2048
CAPABILITIES_DOCUMENT_VERSION = 1
BACKEND_PROTOCOL_VERSION = 2
MAX_CAPABILITIES_RESULT_BYTES = 512
_PRODUCT_VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}\Z")


class BridgeError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie obsłużyć zdarzenia schowka."

    def __repr__(self) -> str:
        return "BridgeError(redacted=True)"


@dataclass(frozen=True, slots=True, repr=False)
class BridgeObservation:
    notification: SafeNotification | None
    history_eligible: bool

    def __repr__(self) -> str:
        return (
            "BridgeObservation(notification="
            f"{self.notification!r}, history_eligible={self.history_eligible!r})"
        )


def capabilities_json() -> str:
    if not _PRODUCT_VERSION.fullmatch(__version__):
        raise BridgeError()
    payload = {
        "document_version": CAPABILITIES_DOCUMENT_VERSION,
        "product_version": __version__,
        "protocol_version": BACKEND_PROTOCOL_VERSION,
    }
    rendered = json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n"
    if len(rendered.encode("ascii")) > MAX_CAPABILITIES_RESULT_BYTES:
        raise BridgeError()
    return rendered


def observe_framed_event(
    stream: BinaryIO,
    *,
    history: HistoryStore,
    pause: PauseStore,
    config_path=None,
) -> BridgeObservation:
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
    detections = detect_text(text, custom_rules)
    history_eligible = history_text_is_eligible(text, detections)
    analysis = analysis_from_detections(
        text,
        detections,
        FilterStore(history.state_dir).status().disabled,
        custom_exclusions,
    )
    history.record(
        text,
        "clipboard_event",
        "other",
        analysis,
        "warned",
        ruleset_version=RULESET_VERSION + (
            "+custom" if custom_rules or custom_exclusions else ""
        ),
        source_application=application,
        destination_application="unknown",
    )
    notification = None
    if analysis.highest_risk is not RiskLevel.NONE:
        notification = SafeNotification(
            analysis.highest_risk,
            analysis.category_counts,
        )
    return BridgeObservation(notification, history_eligible)


def bridge_result_json(observation: BridgeObservation) -> str:
    if type(observation) is not BridgeObservation:
        raise BridgeError()
    notification = observation.notification
    if notification is None:
        payload = {
            "version": 1,
            "risk": "none",
            "categories": [],
            "history_eligible": observation.history_eligible,
        }
    elif type(notification) is SafeNotification:
        payload = {
            "version": 1,
            "risk": notification.risk.value,
            "categories": [list(item) for item in notification.category_counts],
            "history_eligible": observation.history_eligible,
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
