from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


MANIFEST_VERSION = 1
MAX_MANIFEST_BYTES = 64 * 1024
MAX_MODELS = 16
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ModelManifestError(Exception):
    def __str__(self) -> str:
        return "The speech model catalog is invalid."

    def __repr__(self) -> str:
        return "ModelManifestError(redacted=True)"


class ModelArtifactError(Exception):
    def __str__(self) -> str:
        return "The speech model artifact could not be verified."

    def __repr__(self) -> str:
        return "ModelArtifactError(redacted=True)"


@dataclass(frozen=True, slots=True)
class EngineCompatibility:
    engine_id: str
    versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DownloadSpec:
    enabled: bool
    source_url: str
    bytes: int | None
    required_disk_bytes: int
    sha256: str | None
    artifact_format: str | None
    limitation: str | None


@dataclass(frozen=True, slots=True)
class SpeechModel:
    model_id: str
    model_version: str
    names: dict[str, str]
    language_code: str
    language_names: dict[str, str]
    engine: EngineCompatibility
    download: DownloadSpec
    license_id: str
    license_url: str
    install_relative_path: str
    approximate_ram_mib: int


def _https_url(value: object) -> str:
    if type(value) is not str or len(value) > 2048:
        raise ModelManifestError()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ModelManifestError()
    return value


def _short_text(value: object, *, maximum: int = 128) -> str:
    if type(value) is not str or not value or len(value) > maximum or "\0" in value:
        raise ModelManifestError()
    return value


def _labels(value: object) -> dict[str, str]:
    if type(value) is not dict or set(value) != {"pl", "en"}:
        raise ModelManifestError()
    return {key: _short_text(value[key]) for key in ("pl", "en")}


def _relative_path(value: object) -> str:
    text = _short_text(value, maximum=256)
    path = PurePosixPath(text)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ModelManifestError()
    if "\\" in text:
        raise ModelManifestError()
    return text


def _positive_int(value: object) -> int:
    if type(value) is not int or not 0 < value <= 8 * 1024**3:
        raise ModelManifestError()
    return value


def _parse_model(raw: object) -> SpeechModel:
    expected = {
        "id", "model_version", "name", "language", "engine", "download",
        "license", "install_relative_path", "approximate_ram_mib",
    }
    if type(raw) is not dict or set(raw) != expected:
        raise ModelManifestError()
    model_id = raw["id"]
    if type(model_id) is not str or not _IDENTIFIER.fullmatch(model_id):
        raise ModelManifestError()
    model_version = _short_text(raw["model_version"])

    language = raw["language"]
    if type(language) is not dict or set(language) != {"code", "name"}:
        raise ModelManifestError()
    language_code = language["code"]
    if type(language_code) is not str or not re.fullmatch(r"[a-z]{2,3}|multilingual", language_code):
        raise ModelManifestError()

    engine = raw["engine"]
    if type(engine) is not dict or set(engine) != {"id", "compatible_versions"}:
        raise ModelManifestError()
    engine_id = engine["id"]
    versions = engine["compatible_versions"]
    if (
        type(engine_id) is not str
        or not _IDENTIFIER.fullmatch(engine_id)
        or type(versions) is not list
        or not 1 <= len(versions) <= 16
        or any(type(item) is not str or not item or len(item) > 64 for item in versions)
        or len(set(versions)) != len(versions)
    ):
        raise ModelManifestError()

    download = raw["download"]
    if type(download) is not dict or set(download) != {
        "enabled", "source_url", "bytes", "required_disk_bytes", "sha256",
        "format", "limitation",
    }:
        raise ModelManifestError()
    enabled = download["enabled"]
    if type(enabled) is not bool:
        raise ModelManifestError()
    source_url = _https_url(download["source_url"])
    required_disk_bytes = _positive_int(download["required_disk_bytes"])
    artifact_bytes = download["bytes"]
    digest = download["sha256"]
    artifact_format = download["format"]
    limitation = download["limitation"]
    if enabled:
        artifact_bytes = _positive_int(artifact_bytes)
        if required_disk_bytes < artifact_bytes:
            raise ModelManifestError()
        if type(digest) is not str or not _SHA256.fullmatch(digest):
            raise ModelManifestError()
        if artifact_format not in {"single-file", "zip-directory"} or limitation is not None:
            raise ModelManifestError()
    else:
        if artifact_bytes is not None or digest is not None or artifact_format is not None:
            raise ModelManifestError()
        limitation = _short_text(limitation, maximum=256)

    license_data = raw["license"]
    if type(license_data) is not dict or set(license_data) != {"id", "url"}:
        raise ModelManifestError()
    license_id = _short_text(license_data["id"], maximum=64)
    license_url = _https_url(license_data["url"])
    ram = raw["approximate_ram_mib"]
    if type(ram) is not int or not 1 <= ram <= 16 * 1024:
        raise ModelManifestError()

    return SpeechModel(
        model_id=model_id,
        model_version=model_version,
        names=_labels(raw["name"]),
        language_code=language_code,
        language_names=_labels(language["name"]),
        engine=EngineCompatibility(engine_id, tuple(versions)),
        download=DownloadSpec(
            enabled, source_url, artifact_bytes, required_disk_bytes, digest,
            artifact_format, limitation,
        ),
        license_id=license_id,
        license_url=license_url,
        install_relative_path=_relative_path(raw["install_relative_path"]),
        approximate_ram_mib=ram,
    )


def _parse_manifest(payload: bytes) -> tuple[SpeechModel, ...]:
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ModelManifestError()
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelManifestError() from exc
    if type(document) is not dict or set(document) != {"version", "models"}:
        raise ModelManifestError()
    raw_models = document["models"]
    if (
        type(document["version"]) is not int
        or document["version"] != MANIFEST_VERSION
        or type(raw_models) is not list
        or not 1 <= len(raw_models) <= MAX_MODELS
    ):
        raise ModelManifestError()
    models = tuple(_parse_model(raw) for raw in raw_models)
    identifiers = [model.model_id for model in models]
    paths = [model.install_relative_path for model in models]
    if len(set(identifiers)) != len(identifiers) or len(set(paths)) != len(paths):
        raise ModelManifestError()
    return models


def load_model_manifest(path: Path | None = None) -> tuple[SpeechModel, ...]:
    if path is None:
        resource = files("copypastebin.data").joinpath("stt-models-v1.json")
        return _parse_manifest(resource.read_bytes())
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except (AttributeError, OSError) as exc:
        raise ModelManifestError() from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_MANIFEST_BYTES:
            raise ModelManifestError()
        payload = os.read(descriptor, MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise ModelManifestError() from exc
    finally:
        os.close(descriptor)
    return _parse_manifest(payload)


def verify_local_artifact(path: Path, model: SpeechModel) -> None:
    spec = model.download
    if not spec.enabled or spec.bytes is None or spec.sha256 is None:
        raise ModelArtifactError()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except (AttributeError, OSError) as exc:
        raise ModelArtifactError() from exc
    digest = hashlib.sha256()
    total = 0
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size != spec.bytes:
            raise ModelArtifactError()
        while chunk := os.read(descriptor, min(1024 * 1024, spec.bytes - total + 1)):
            total += len(chunk)
            if total > spec.bytes:
                raise ModelArtifactError()
            digest.update(chunk)
    except OSError as exc:
        raise ModelArtifactError() from exc
    finally:
        os.close(descriptor)
    if total != spec.bytes or digest.hexdigest() != spec.sha256:
        raise ModelArtifactError()
