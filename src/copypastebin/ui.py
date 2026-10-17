from __future__ import annotations

import json
import unicodedata

from .config import MAX_CUSTOM_EXCLUSIONS, MAX_CUSTOM_RULES
from .detection import (
    EXCLUDABLE_CATEGORIES,
    CustomLiteralExclusion,
    CustomLiteralRule,
    analyze_text,
)
from .filters import ALL_CATEGORIES, AUTO_CLEAR_CHOICES, FilterStatus
from .history import HistoryStore, VIEW_LIMIT
from .models import AnalysisResult, Category, RiskLevel


MAX_HISTORY_JSON_BYTES = 16 * 1024
MAX_RULES_JSON_BYTES = 64 * 1024
MAX_DETECTIONS_JSON_BYTES = 64 * 1024
MAX_EXCLUSION_REQUEST_BYTES = 2048
MAX_UI_DETECTIONS = 1000


class UiError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie przygotować interfejsu."

    def __repr__(self) -> str:
        return "UiError(redacted=True)"


def history_json(history: HistoryStore) -> str:
    entries = []
    for entry in history.recent(VIEW_LIMIT):
        entries.append(
            {
                "time": entry.created_at,
                "from": entry.source_application,
                "to": entry.destination_application,
                "risk": entry.highest_risk,
                "categories": [list(item) for item in entry.category_counts],
            }
        )
    encoded = json.dumps(
        {"version": 1, "entries": entries},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(encoded.encode("ascii")) > MAX_HISTORY_JSON_BYTES:
        raise UiError()
    return encoded + "\n"


def redacted_suggestion(
    text: str,
    custom_rules: tuple[CustomLiteralRule, ...] = (),
    disabled_categories: frozenset[Category] = frozenset(),
    custom_exclusions: tuple[CustomLiteralExclusion, ...] = (),
) -> str:
    if not text or "\x00" in text:
        raise UiError()
    return analyze_text(
        text,
        custom_rules,
        disabled_categories,
        custom_exclusions,
    ).redacted_text


def filters_json(status: FilterStatus) -> str:
    if type(status) is not FilterStatus:
        raise UiError()
    encoded = json.dumps(
        {
            "version": 1,
            "filters": [
                [category.value, status.enabled(category)]
                for category in ALL_CATEGORIES
            ],
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    if len(encoded.encode("ascii")) > 2048:
        raise UiError()
    return encoded + "\n"


def auto_clear_json(status: FilterStatus) -> str:
    if (
        type(status) is not FilterStatus
        or type(status.auto_clear_seconds) is not int
        or status.auto_clear_seconds not in AUTO_CLEAR_CHOICES
    ):
        raise UiError()
    return json.dumps(
        {"version": 1, "seconds": status.auto_clear_seconds},
        ensure_ascii=True,
        separators=(",", ":"),
    ) + "\n"


def detections_json(analysis: AnalysisResult) -> str:
    if type(analysis) is not AnalysisResult:
        raise UiError()
    if len(analysis.detections) > MAX_UI_DETECTIONS:
        raise UiError()
    encoded = json.dumps(
        {
            "version": 1,
            "detections": [
                {
                    "start": item.start,
                    "end": item.end,
                    "category": item.category.value,
                    "risk": item.risk.value,
                }
                for item in analysis.detections
            ],
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    if len(encoded.encode("ascii")) > MAX_DETECTIONS_JSON_BYTES:
        raise UiError()
    return encoded + "\n"


def custom_rules_json(
    rules: tuple[CustomLiteralRule, ...],
    exclusions: tuple[CustomLiteralExclusion, ...] = (),
) -> str:
    if (
        type(rules) is not tuple
        or len(rules) > MAX_CUSTOM_RULES
        or type(exclusions) is not tuple
        or len(exclusions) > MAX_CUSTOM_EXCLUSIONS
    ):
        raise UiError()
    encoded = json.dumps(
        {
            "version": 3,
            "max_rules": MAX_CUSTOM_RULES,
            "max_exclusions": MAX_CUSTOM_EXCLUSIONS,
            "rules": [
                {
                    "literal": rule.literal,
                    "risk": rule.risk.value,
                    "enabled": rule.enabled,
                }
                for rule in rules
            ],
            "exclusions": [
                {
                    "literal": exclusion.literal,
                    "category": exclusion.category.value,
                    "enabled": exclusion.enabled,
                }
                for exclusion in exclusions
            ],
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    if len(encoded.encode("ascii")) > MAX_RULES_JSON_BYTES:
        raise UiError()
    return encoded + "\n"


def custom_rules_from_json(
    text: str,
) -> tuple[tuple[CustomLiteralRule, ...], tuple[CustomLiteralExclusion, ...]]:
    if not text or len(text.encode("utf-8")) > MAX_RULES_JSON_BYTES:
        raise UiError()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UiError() from exc
    if (
        type(payload) is not dict
        or set(payload) != {"version", "rules", "exclusions"}
        or payload.get("version") != 3
        or type(payload.get("rules")) is not list
        or len(payload["rules"]) > MAX_CUSTOM_RULES
        or type(payload.get("exclusions")) is not list
        or len(payload["exclusions"]) > MAX_CUSTOM_EXCLUSIONS
    ):
        raise UiError()
    rules: list[CustomLiteralRule] = []
    for entry in payload["rules"]:
        if type(entry) is not dict or set(entry) != {"literal", "risk", "enabled"}:
            raise UiError()
        literal = entry["literal"]
        risk = entry["risk"]
        enabled = entry["enabled"]
        if type(literal) is not str or type(risk) is not str or type(enabled) is not bool:
            raise UiError()
        legacy = {"warning": RiskLevel.MEDIUM}
        try:
            parsed_risk = legacy[risk] if risk in legacy else RiskLevel(risk)
            if parsed_risk is RiskLevel.NONE:
                raise ValueError
            rules.append(CustomLiteralRule(literal, parsed_risk, enabled))
        except ValueError as exc:
            raise UiError() from exc
    literals = {rule.literal for rule in rules}
    exclusions: list[CustomLiteralExclusion] = []
    for entry in payload["exclusions"]:
        if type(entry) is not dict or set(entry) != {"literal", "category", "enabled"}:
            raise UiError()
        literal = entry["literal"]
        category_value = entry["category"]
        enabled = entry["enabled"]
        if (
            type(literal) is not str
            or type(category_value) is not str
            or type(enabled) is not bool
            or literal in literals
        ):
            raise UiError()
        try:
            category = Category(category_value)
        except ValueError as exc:
            raise UiError() from exc
        if category not in EXCLUDABLE_CATEGORIES:
            raise UiError()
        literals.add(literal)
        exclusions.append(CustomLiteralExclusion(literal, category, enabled))
    return tuple(rules), tuple(exclusions)


def exclusion_request_from_json(text: str) -> CustomLiteralExclusion:
    if not text or len(text.encode("utf-8")) > MAX_EXCLUSION_REQUEST_BYTES:
        raise UiError()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UiError() from exc
    if (
        type(payload) is not dict
        or set(payload) != {"version", "literal", "category"}
        or payload.get("version") != 1
        or type(payload.get("literal")) is not str
        or type(payload.get("category")) is not str
    ):
        raise UiError()
    try:
        category = Category(payload["category"])
    except ValueError as exc:
        raise UiError() from exc
    literal = payload["literal"]
    if (
        category not in EXCLUDABLE_CATEGORIES
        or not 3 <= len(literal) <= 128
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in literal)
    ):
        raise UiError()
    return CustomLiteralExclusion(literal, category, True)


def exclusion_result_json(status: str) -> str:
    if status not in {"added", "enabled", "exists", "conflict", "limit"}:
        raise UiError()
    return json.dumps(
        {"version": 1, "status": status},
        ensure_ascii=True,
        separators=(",", ":"),
    ) + "\n"
