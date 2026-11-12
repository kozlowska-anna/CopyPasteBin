#!/usr/bin/env python3
"""Validate the approved natural-Polish corpus after its audio is obtained."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import wave
from pathlib import Path

from score import InputError, _read_json, load_cases


ALLOWED_LICENSES = {"CC0-1.0", "CC-BY-4.0"}
ALLOWED_CATEGORIES = {
    "daily-conversation", "natural-long", "numbers-dates-times",
    "proper-names", "computing", "pauses-tempo", "self-correction",
    "punctuation",
}
CORPUS_KEYS = {
    "name", "language", "selection", "source_revisions", "conversion",
    "minimum_speakers", "clip_duration_ms", "total_duration_ms",
    "coverage_gaps",
}
SAMPLE_KEYS = {
    "case_id", "file", "sha256", "source_sha256", "source_dataset",
    "source_revision", "source_item_id", "source_url", "reference_url",
    "audio_license", "reference_license", "attribution", "speaker_id",
    "duration_ms", "categories", "purpose",
}


def _closed_range(value: object, label: str) -> tuple[float, float]:
    if not isinstance(value, dict) or set(value) != {"minimum", "maximum"}:
        raise InputError(f"{label} has an invalid shape")
    minimum, maximum = value["minimum"], value["maximum"]
    if any(isinstance(item, bool) or not isinstance(item, (int, float))
           for item in (minimum, maximum)) or minimum <= 0 or maximum < minimum:
        raise InputError(f"{label} is invalid")
    return float(minimum), float(maximum)


def validate(manifest_path: Path, audio_root: Path, cases_path: Path) -> dict:
    cases = load_cases(cases_path)
    document = _read_json(manifest_path)
    if not isinstance(document, dict) or set(document) != {
            "version", "corpus", "samples"} or document.get("version") != 3:
        raise InputError("natural audio manifest has an invalid shape")
    corpus, samples = document["corpus"], document["samples"]
    if not isinstance(corpus, dict) or set(corpus) != CORPUS_KEYS or \
            corpus.get("language") != "pl" or not isinstance(samples, list) or \
            not 12 <= len(samples) <= 20 or len(samples) != len(cases):
        raise InputError("natural corpus metadata or sample count is invalid")
    for key in ("name", "selection", "conversion"):
        if not isinstance(corpus.get(key), str) or not corpus[key]:
            raise InputError("natural corpus metadata is incomplete")
    if corpus.get("minimum_speakers") != 3:
        raise InputError("natural corpus must require at least three speakers")
    revisions = corpus.get("source_revisions")
    if not isinstance(revisions, dict) or not revisions or not all(
            isinstance(key, str) and re.fullmatch(r"[a-z0-9.-]{1,64}", key) and
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{7,64}", value)
            for key, value in revisions.items()):
        raise InputError("source revisions are invalid")
    clip_min, clip_max = _closed_range(corpus.get("clip_duration_ms"),
                                       "clip duration")
    total_min, total_max = _closed_range(corpus.get("total_duration_ms"),
                                         "total duration")
    if (clip_min, clip_max) != (10_000, 20_000) or \
            (total_min, total_max) != (180_000, 300_000):
        raise InputError("natural corpus duration policy is invalid")
    gaps = corpus.get("coverage_gaps")
    if not isinstance(gaps, list) or len(gaps) != len(set(gaps)) or \
            any(gap not in ALLOWED_CATEGORIES for gap in gaps):
        raise InputError("coverage gaps are invalid")

    try:
        root_info = os.lstat(audio_root)
        root = audio_root.resolve(strict=True)
    except OSError as error:
        raise InputError("natural audio root is unavailable") from error
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode) or \
            root_info.st_uid != os.geteuid() or stat.S_IMODE(root_info.st_mode) != 0o700:
        raise InputError("natural audio root must be user-owned mode 0700")
    seen: set[str] = set()
    speakers: set[str] = set()
    covered: set[str] = set()
    total_frames = 0
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) != SAMPLE_KEYS:
            raise InputError("natural audio sample has an invalid shape")
        case_id = sample["case_id"]
        if case_id not in cases or case_id in seen:
            raise InputError("natural audio sample uses an invalid case")
        seen.add(case_id)
        if sample["purpose"] != "quality" or \
                sample["audio_license"] not in ALLOWED_LICENSES or \
                sample["reference_license"] not in ALLOWED_LICENSES:
            raise InputError("natural audio sample has an invalid use or license")
        source = sample["source_dataset"]
        if source not in revisions or sample["source_revision"] != revisions[source]:
            raise InputError("natural audio sample source is not pinned")
        for key in ("source_item_id", "attribution", "speaker_id"):
            if not isinstance(sample[key], str) or not sample[key] or \
                    len(sample[key]) > 500 or "\0" in sample[key]:
                raise InputError("natural audio sample metadata is incomplete")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", sample["speaker_id"]):
            raise InputError("speaker identifier must be pseudonymous and bounded")
        if sample["speaker_id"] != "unknown":
            speakers.add(sample["speaker_id"])
        for key in ("source_url", "reference_url"):
            if not isinstance(sample[key], str) or not sample[key].startswith("https://"):
                raise InputError("natural audio source URL is invalid")
        for key in ("sha256", "source_sha256"):
            if not isinstance(sample[key], str) or not re.fullmatch(
                    r"[0-9a-f]{64}", sample[key]):
                raise InputError("natural audio checksum is invalid")
        categories = sample["categories"]
        if not isinstance(categories, list) or not categories or \
                len(categories) != len(set(categories)) or \
                any(category not in ALLOWED_CATEGORIES for category in categories):
            raise InputError("natural audio categories are invalid")
        covered.update(categories)

        relative = Path(sample["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise InputError("natural audio path is not relative")
        path = root / relative
        try:
            info = os.lstat(path)
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise InputError("natural audio path is unavailable") from error
        current = root
        has_symlink = False
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                has_symlink = True
                break
        if has_symlink or not resolved.is_file() or not resolved.is_relative_to(root) or \
                info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise InputError("natural audio path is outside the trusted directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
            raise InputError("natural audio checksum mismatch")
        with wave.open(str(path), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                    audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise InputError("natural audio must be mono 16-bit PCM WAV at 16 kHz")
            frames = audio.getnframes()
        duration_ms = frames / 16
        if duration_ms != sample["duration_ms"] or not clip_min <= duration_ms <= clip_max:
            raise InputError("natural audio duration is invalid")
        total_frames += frames

    total_duration_ms = total_frames / 16
    if seen != set(cases) or len(speakers) < corpus["minimum_speakers"] or \
            not total_min <= total_duration_ms <= total_max or \
            covered | set(gaps) != ALLOWED_CATEGORIES or not covered.isdisjoint(gaps):
        raise InputError("natural corpus coverage, speakers, or duration is incomplete")
    return {
        "version": 3,
        "samples": len(seen),
        "speakers": len(speakers),
        "duration_ms": total_duration_ms,
        "covered_categories": sorted(covered),
        "coverage_gaps": gaps,
        "case_ids": sorted(seen),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(arguments.manifest, arguments.audio_root, arguments.cases)
    except (InputError, OSError, wave.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
