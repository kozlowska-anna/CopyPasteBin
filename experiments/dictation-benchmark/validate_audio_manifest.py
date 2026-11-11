#!/usr/bin/env python3
"""Validate licensed benchmark WAV files without reading private locations."""

from __future__ import annotations

import argparse
import hashlib
import json
import wave
from pathlib import Path

from score import InputError, _read_json, load_cases


def validate(manifest_path: Path, audio_root: Path, cases_path: Path) -> dict:
    cases = load_cases(cases_path)
    document = _read_json(manifest_path)
    if not isinstance(document, dict) or set(document) != {"version", "samples"}:
        raise InputError("audio manifest has an invalid shape")
    if document["version"] != 1 or not isinstance(document["samples"], list):
        raise InputError("unsupported audio manifest")
    root = audio_root.resolve(strict=True)
    seen = set()
    total_frames = 0
    for sample in document["samples"]:
        keys = {"case_id", "file", "sha256", "license", "source_url", "purpose"}
        if not isinstance(sample, dict) or set(sample) != keys:
            raise InputError("audio sample has an invalid shape")
        case_id = sample["case_id"]
        if case_id not in cases or case_id in seen:
            raise InputError("audio sample uses an invalid case")
        seen.add(case_id)
        if sample["purpose"] not in {"technical", "quality"}:
            raise InputError("audio sample has an invalid purpose")
        if not all(isinstance(sample[key], str) and sample[key]
                   for key in ("file", "sha256", "license", "source_url")):
            raise InputError("audio sample metadata is incomplete")
        if len(sample["sha256"]) != 64 or any(char not in "0123456789abcdef" for char in sample["sha256"]):
            raise InputError("audio sample has an invalid SHA-256")
        relative = Path(sample["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise InputError("audio path is not relative")
        path = root / relative
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise InputError("audio path is outside the isolated directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sample["sha256"]:
            raise InputError("audio checksum mismatch")
        with wave.open(str(path), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(),
                    audio.getcomptype()) != (1, 2, 16000, "NONE"):
                raise InputError("audio must be mono 16-bit PCM WAV at 16 kHz")
            total_frames += audio.getnframes()
    return {
        "version": 1,
        "samples": len(seen),
        "duration_ms": round(total_frames / 16000 * 1000),
        "case_ids": sorted(seen),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    arguments = parser.parse_args()
    try:
        result = validate(arguments.manifest, arguments.audio_root, arguments.cases)
    except (InputError, OSError, wave.Error) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
