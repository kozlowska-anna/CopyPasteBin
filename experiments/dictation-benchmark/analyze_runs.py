#!/usr/bin/env python3
"""Aggregate real STT benchmark runs without printing transcripts."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from statistics import fmean
from typing import Any

from score import InputError, _edit_distance, _read_json, _words, load_cases

MAX_RESULTS = 500
MAX_PARTIALS = 10_000
ENGINES = {
    "vosk-small-pl-0.22",
    "whisper.cpp-tiny",
    "whisper.cpp-base",
    "whisper.cpp-small",
}
MODES = {"streaming", "windowed", "batch"}
RESULT_KEYS = {
    "case_id", "engine", "run", "transcript", "recognition_mode",
    "audio_duration_ms", "model_init_ms", "first_partial_ms",
    "final_result_ms", "partials", "cpu_seconds", "peak_rss_mib",
    "engine_bytes", "model_bytes", "offline",
}


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise InputError(f"{label} has an invalid value")
    return result


def _punctuation(text: str) -> str:
    return "".join(re.findall(r"[.,!?;:—-]", text))


def _partial_churn(partials: list[dict[str, Any]]) -> float | None:
    if len(partials) < 2:
        return None
    changes = []
    for before, after in zip(partials, partials[1:]):
        left, right = before["text"], after["text"]
        changes.append(_edit_distance(left, right) / max(len(left), len(right), 1))
    return fmean(changes)


def analyze(cases: dict[str, str], path: Path) -> dict[str, Any]:
    document = _read_json(path)
    if not isinstance(document, dict) or set(document) != {"version", "results"}:
        raise InputError("result document has an invalid shape")
    if document["version"] != 2 or not isinstance(document["results"], list):
        raise InputError("unsupported result document")
    if not 1 <= len(document["results"]) <= MAX_RESULTS:
        raise InputError("result count is invalid")

    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str, int]] = set()
    for raw in document["results"]:
        if not isinstance(raw, dict) or set(raw) != RESULT_KEYS:
            raise InputError("result has an invalid shape")
        case_id, engine, run = raw["case_id"], raw["engine"], raw["run"]
        if case_id not in cases or engine not in ENGINES:
            raise InputError("result uses an unknown case or engine")
        if isinstance(run, bool) or not isinstance(run, int) or run not in {1, 2, 3}:
            raise InputError("run must be 1, 2, or 3")
        identity = (engine, case_id, run)
        if identity in seen:
            raise InputError("duplicate engine, case, and run")
        seen.add(identity)
        transcript = raw["transcript"]
        if not isinstance(transcript, str) or len(transcript) > 4000 or "\0" in transcript:
            raise InputError("invalid transcript")
        mode = raw["recognition_mode"]
        if mode not in MODES:
            raise InputError("invalid recognition mode")
        if raw["offline"] is not True:
            raise InputError("run was not confirmed offline")
        duration = _number(raw["audio_duration_ms"], "audio_duration_ms", positive=True)
        init_ms = _number(raw["model_init_ms"], "model_init_ms")
        final_ms = _number(raw["final_result_ms"], "final_result_ms")
        first_ms = raw["first_partial_ms"]
        if first_ms is not None:
            first_ms = _number(first_ms, "first_partial_ms")
            if first_ms > final_ms:
                raise InputError("first partial follows final result")
        if mode == "batch" and first_ms is not None:
            raise InputError("batch run cannot claim a partial result")
        partials = raw["partials"]
        if not isinstance(partials, list) or len(partials) > MAX_PARTIALS:
            raise InputError("invalid partial list")
        previous_ms = -1.0
        checked_partials = []
        for partial in partials:
            if not isinstance(partial, dict) or set(partial) != {"at_ms", "text"}:
                raise InputError("partial has an invalid shape")
            at_ms = _number(partial["at_ms"], "partial at_ms")
            text = partial["text"]
            if at_ms < previous_ms or at_ms > final_ms or not isinstance(text, str) or len(text) > 4000 or "\0" in text:
                raise InputError("invalid partial")
            previous_ms = at_ms
            checked_partials.append({"at_ms": at_ms, "text": text})
        if (first_ms is None) != (len(checked_partials) == 0):
            raise InputError("partial timing and events disagree")

        reference = cases[case_id]
        ref_words, hyp_words = _words(reference), _words(transcript)
        ref_chars = " ".join(reference.casefold().split())
        hyp_chars = " ".join(transcript.casefold().split())
        ref_punctuation, hyp_punctuation = _punctuation(reference), _punctuation(transcript)
        grouped.setdefault(engine, []).append({
            "mode": mode,
            "word_edits": _edit_distance(ref_words, hyp_words),
            "word_units": len(ref_words),
            "char_edits": _edit_distance(ref_chars, hyp_chars),
            "char_units": len(ref_chars),
            "punctuation_accuracy": 1 - _edit_distance(ref_punctuation, hyp_punctuation) /
                max(len(ref_punctuation), len(hyp_punctuation), 1),
            "duration": duration,
            "init": init_ms,
            "first": first_ms,
            "final": final_ms,
            "churn": _partial_churn(checked_partials),
            "partial_count": len(checked_partials),
            "cpu": _number(raw["cpu_seconds"], "cpu_seconds"),
            "rss": _number(raw["peak_rss_mib"], "peak_rss_mib"),
            "engine_bytes": int(_number(raw["engine_bytes"], "engine_bytes")),
            "model_bytes": int(_number(raw["model_bytes"], "model_bytes")),
        })

    engines = []
    for engine in sorted(grouped):
        rows = grouped[engine]
        word_units = sum(row["word_units"] for row in rows)
        char_units = sum(row["char_units"] for row in rows)
        first = [row["first"] for row in rows if row["first"] is not None]
        churn = [row["churn"] for row in rows if row["churn"] is not None]
        engines.append({
            "engine": engine,
            "modes": sorted(set(row["mode"] for row in rows)),
            "runs": len(rows),
            "wer": round(sum(row["word_edits"] for row in rows) / word_units, 6),
            "cer": round(sum(row["char_edits"] for row in rows) / char_units, 6),
            "mean_punctuation_accuracy": round(fmean(row["punctuation_accuracy"] for row in rows), 6),
            "mean_model_init_ms": round(fmean(row["init"] for row in rows), 3),
            "mean_first_partial_ms": None if not first else round(fmean(first), 3),
            "runs_without_partial": len(rows) - len(first),
            "mean_final_result_ms": round(fmean(row["final"] for row in rows), 3),
            "mean_realtime_factor": round(fmean(row["final"] / row["duration"] for row in rows), 6),
            "mean_endpoint_latency_ms": round(fmean(max(0, row["final"] - row["duration"]) for row in rows), 3),
            "mean_partial_updates_per_second": round(fmean(row["partial_count"] / (row["duration"] / 1000) for row in rows), 6),
            "mean_partial_churn": None if not churn else round(fmean(churn), 6),
            "mean_cpu_seconds": round(fmean(row["cpu"] for row in rows), 3),
            "peak_rss_mib": round(max(row["rss"] for row in rows), 3),
            "engine_bytes": max(row["engine_bytes"] for row in rows),
            "model_bytes": max(row["model_bytes"] for row in rows),
            "offline_runs": len(rows),
        })
    return {"version": 2, "scored_results": len(seen), "engines": engines}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    arguments = parser.parse_args()
    try:
        report = analyze(load_cases(arguments.cases), arguments.results)
    except InputError as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
