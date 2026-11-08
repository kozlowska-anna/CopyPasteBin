#!/usr/bin/env python3
"""Report a deterministic synthetic baseline for clipboard history policy."""

from __future__ import annotations

import io
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from copypastebin.bridge import observe_framed_event
from copypastebin.detection import detect_text
from copypastebin.filters import FilterStore
from copypastebin.history import HistoryStore
from copypastebin.history_policy import history_text_is_eligible
from copypastebin.models import Category
from copypastebin.pause import PauseStore


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "tests" / "fixtures" / "history_policy" / "cases.json"


def load_cases():
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    if type(document) is not dict or document.get("version") != 1:
        raise RuntimeError("invalid history policy corpus")
    cases = document.get("cases")
    if type(cases) is not list or any(type(case) is not dict for case in cases):
        raise RuntimeError("invalid history policy corpus")
    return cases


def frame(text):
    application = b"app.synthetic.corpus"
    return len(application).to_bytes(4, "big") + application + text.encode("utf-8")


def configure_filters(state_dir, *, enabled):
    store = FilterStore(state_dir)
    for category in Category:
        store.set_enabled(category, enabled)


def observe(text, *, history, pause):
    return observe_framed_event(
        io.BytesIO(frame(text)),
        history=history,
        pause=pause,
    )


def empty_metrics():
    return {
        "cases": 0,
        "allowed": 0,
        "blocked": 0,
        "secret_leaks": 0,
        "false_rejections": 0,
    }


def update_metrics(metrics, case, eligible):
    metrics["cases"] += 1
    metrics["allowed" if eligible else "blocked"] += 1
    if case["classification"] == "secret" and eligible:
        metrics["secret_leaks"] += 1
    if case["classification"] == "non_secret" and not eligible:
        metrics["false_rejections"] += 1


def render_breakdown(title, metrics):
    print(title)
    print("name                         cases  allowed  blocked  leaks  false_rejects")
    for name in sorted(metrics):
        values = metrics[name]
        print(
            f"{name:28}"
            f"{values['cases']:7}"
            f"{values['allowed']:9}"
            f"{values['blocked']:9}"
            f"{values['secret_leaks']:7}"
            f"{values['false_rejections']:15}"
        )


def run():
    cases = load_cases()
    totals = empty_metrics()
    by_group = defaultdict(empty_metrics)
    by_transform = defaultdict(empty_metrics)
    expectation_failures = []
    bridge_differences = []
    filter_history_differences = []
    disabled_banner_differences = []
    detection_differences = []
    banner_differences = []
    observed_detections = []
    known_bypasses = []
    target_gaps = []

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        enabled_state = root / "enabled"
        disabled_state = root / "disabled"
        configure_filters(enabled_state, enabled=True)
        configure_filters(disabled_state, enabled=False)
        enabled_history = HistoryStore(enabled_state)
        disabled_history = HistoryStore(disabled_state)
        enabled_pause = PauseStore(enabled_state)
        disabled_pause = PauseStore(disabled_state)

        for case in cases:
            identifier = case["id"]
            detections = detect_text(case["text"])
            categories = {item.category.value for item in detections}
            direct = history_text_is_eligible(case["text"], detections)
            enabled = observe(
                case["text"], history=enabled_history, pause=enabled_pause
            )
            disabled = observe(
                case["text"], history=disabled_history, pause=disabled_pause
            )

            update_metrics(totals, case, direct)
            update_metrics(by_group[case["group"]], case, direct)
            update_metrics(by_transform[case["transform"]], case, direct)

            if direct != enabled.history_eligible:
                bridge_differences.append(identifier)
            if enabled.history_eligible != disabled.history_eligible:
                filter_history_differences.append(identifier)
            if disabled.notification is not None:
                disabled_banner_differences.append(identifier)

            if case["detection"] == "required" and not detections:
                detection_differences.append(identifier)
            if case["detection"] == "none" and detections:
                detection_differences.append(identifier)
            if not set(case["required_categories"]) <= categories:
                detection_differences.append(identifier)
            if case["detection"] == "observe" and detections:
                observed_detections.append(identifier)

            if case["banner"] == "required" and enabled.notification is None:
                banner_differences.append(identifier)
            if case["banner"] == "none" and enabled.notification is not None:
                banner_differences.append(identifier)

            if case["history"] == "block" and direct:
                expectation_failures.append(identifier)
            if case["history"] == "allow" and not direct:
                expectation_failures.append(identifier)

            if case["group"] == "known_bypass" and direct:
                known_bypasses.append(identifier)
            if case["target_history"] == "block" and direct:
                target_gaps.append(identifier)
            if case["target_history"] == "allow" and not direct:
                target_gaps.append(identifier)

    print("CopyPasteBin history policy corpus — synthetic baseline")
    print(f"cases={totals['cases']}")
    print(f"secret_leaks={totals['secret_leaks']}")
    print(f"false_rejections={totals['false_rejections']}")
    print(f"bridge_differences={len(set(bridge_differences))}")
    print(f"filter_history_differences={len(set(filter_history_differences))}")
    print(f"disabled_banner_differences={len(set(disabled_banner_differences))}")
    print(f"observed_detections={len(observed_detections)}")
    print(f"known_bypasses={len(known_bypasses)}")
    print(f"target_gaps={len(target_gaps)}")
    render_breakdown("BY GROUP", by_group)
    render_breakdown("BY TRANSFORM", by_transform)
    print("KNOWN BYPASS IDS")
    for identifier in sorted(known_bypasses):
        print(identifier)
    print("TARGET GAP IDS")
    for identifier in sorted(target_gaps):
        print(identifier)
    print("OBSERVED DETECTION IDS")
    for identifier in sorted(observed_detections):
        print(identifier)

    failures = {
        *expectation_failures,
        *bridge_differences,
        *filter_history_differences,
        *disabled_banner_differences,
        *detection_differences,
        *banner_differences,
    }
    if failures:
        print("REGRESSION IDS")
        for identifier in sorted(failures):
            print(identifier)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
