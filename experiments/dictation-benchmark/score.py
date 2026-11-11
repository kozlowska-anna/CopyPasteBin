#!/usr/bin/env python3
"""Score synthetic Polish dictation results without invoking an STT engine."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import fmean
from typing import Any

MAX_DOCUMENT_BYTES = 256 * 1024
MAX_TRANSCRIPT_CHARS = 2_000
ALLOWED_ENGINES = {"vosk-small-pl-0.22", "whisper.cpp-tiny", "whisper.cpp-base", "whisper.cpp-small"}
RESULT_KEYS = {"case_id", "engine", "run", "transcript", "first_result_ms", "final_result_ms", "cpu_seconds", "peak_rss_mib", "model_bytes"}


class InputError(ValueError):
    pass


def _read_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise InputError("input could not be read") from error
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise InputError("input is too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InputError("input is not valid UTF-8 JSON") from error


def _exact_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise InputError(f"{label} has an invalid shape")
    return value


def _nonnegative_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{label} must be a number")
    rendered = float(value)
    if not math.isfinite(rendered) or rendered < 0:
        raise InputError(f"{label} must be finite and non-negative")
    return rendered


def _edit_distance(reference: list[str] | str, hypothesis: list[str] | str) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, expected in enumerate(reference, start=1):
        current = [row]
        for column, actual in enumerate(hypothesis, start=1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def _characters(text: str) -> str:
    return " ".join(text.casefold().split())


def load_cases(path: Path) -> dict[str, str]:
    document = _exact_object(_read_json(path), {"version", "language", "cases"}, "case document")
    if document["version"] != 1 or document["language"] != "pl":
        raise InputError("unsupported case document")
    if not isinstance(document["cases"], list) or not document["cases"]:
        raise InputError("case list is empty")
    cases: dict[str, str] = {}
    for item in document["cases"]:
        case = _exact_object(item, {"id", "text"}, "case")
        if not isinstance(case["id"], str) or not re.fullmatch(r"pl-[0-9]{2}", case["id"]):
            raise InputError("invalid case identifier")
        if not isinstance(case["text"], str) or not 1 <= len(case["text"]) <= 500:
            raise InputError("invalid case text")
        if not _words(case["text"]):
            raise InputError("case text has no words")
        if case["id"] in cases:
            raise InputError("duplicate case identifier")
        cases[case["id"]] = case["text"]
    return cases


def score(cases: dict[str, str], results_path: Path) -> dict[str, Any]:
    document = _exact_object(_read_json(results_path), {"version", "results"}, "result document")
    if document["version"] != 1 or not isinstance(document["results"], list):
        raise InputError("unsupported result document")
    groups: dict[str, list[dict[str, float | int]]] = {}
    seen: set[tuple[str, str, int]] = set()
    for item in document["results"]:
        result = _exact_object(item, RESULT_KEYS, "result")
        case_id, engine, run = result["case_id"], result["engine"], result["run"]
        transcript = result["transcript"]
        if case_id not in cases or engine not in ALLOWED_ENGINES:
            raise InputError("result uses an unknown case or engine")
        if isinstance(run, bool) or not isinstance(run, int) or run not in {1, 2, 3}:
            raise InputError("run must be 1, 2, or 3")
        if not isinstance(transcript, str) or len(transcript) > MAX_TRANSCRIPT_CHARS or "\0" in transcript:
            raise InputError("invalid transcript")
        identity = (engine, case_id, run)
        if identity in seen:
            raise InputError("duplicate engine, case, and run")
        seen.add(identity)
        first_ms = _nonnegative_number(result["first_result_ms"], "first_result_ms")
        final_ms = _nonnegative_number(result["final_result_ms"], "final_result_ms")
        if final_ms < first_ms:
            raise InputError("final_result_ms precedes first_result_ms")
        reference_words, hypothesis_words = _words(cases[case_id]), _words(transcript)
        reference_chars, hypothesis_chars = _characters(cases[case_id]), _characters(transcript)
        groups.setdefault(engine, []).append({
            "word_edits": _edit_distance(reference_words, hypothesis_words),
            "word_units": len(reference_words),
            "char_edits": _edit_distance(reference_chars, hypothesis_chars),
            "char_units": len(reference_chars),
            "first_result_ms": first_ms,
            "final_result_ms": final_ms,
            "cpu_seconds": _nonnegative_number(result["cpu_seconds"], "cpu_seconds"),
            "peak_rss_mib": _nonnegative_number(result["peak_rss_mib"], "peak_rss_mib"),
            "model_bytes": int(_nonnegative_number(result["model_bytes"], "model_bytes")),
        })
    engines = []
    for engine in sorted(groups):
        rows = groups[engine]
        word_units = sum(int(row["word_units"]) for row in rows)
        char_units = sum(int(row["char_units"]) for row in rows)
        engines.append({
            "engine": engine,
            "runs": len(rows),
            "wer": round(sum(int(row["word_edits"]) for row in rows) / word_units, 6),
            "cer": round(sum(int(row["char_edits"]) for row in rows) / char_units, 6),
            "mean_first_result_ms": round(fmean(float(row["first_result_ms"]) for row in rows), 3),
            "mean_final_result_ms": round(fmean(float(row["final_result_ms"]) for row in rows), 3),
            "mean_cpu_seconds": round(fmean(float(row["cpu_seconds"]) for row in rows), 3),
            "peak_rss_mib": round(max(float(row["peak_rss_mib"]) for row in rows), 3),
            "model_bytes": max(int(row["model_bytes"]) for row in rows),
        })
    return {"version": 1, "scored_results": len(seen), "engines": engines}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    arguments = parser.parse_args()
    try:
        report = score(load_cases(arguments.cases), arguments.results)
    except InputError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
