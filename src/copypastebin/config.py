from __future__ import annotations

import os
import json
import secrets
import stat
import tomllib
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from .detection import (
    EXCLUDABLE_CATEGORIES,
    CustomLiteralExclusion,
    CustomLiteralRule,
    analyze_text,
)
from .models import Category, RiskLevel


MAX_CONFIG_BYTES = 64 * 1024
MAX_CUSTOM_RULES = 32
MAX_CUSTOM_EXCLUSIONS = 32


def _custom_rule_risk(value: str) -> RiskLevel:
    legacy = {"warning": RiskLevel.MEDIUM}
    try:
        risk = legacy[value] if value in legacy else RiskLevel(value)
    except ValueError as exc:
        raise ConfigError() from exc
    if risk not in {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}:
        raise ConfigError()
    return risk


class ConfigError(Exception):
    def __str__(self) -> str:
        return "Konfiguracja CopyPasteBin jest nieprawidłowa."

    def __repr__(self) -> str:
        return "ConfigError(redacted=True)"


def default_config_path() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    root = Path(configured) if configured else Path.home() / ".config"
    return root / "copypastebin" / "config.toml"


def load_customizations(
    path: Path | None = None,
) -> tuple[tuple[CustomLiteralRule, ...], tuple[CustomLiteralExclusion, ...]]:
    selected = path or default_config_path()
    try:
        descriptor = os.open(selected, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except FileNotFoundError:
        return (), ()
    except (AttributeError, OSError) as exc:
        raise ConfigError() from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONFIG_BYTES:
            raise ConfigError()
        data = os.read(descriptor, MAX_CONFIG_BYTES + 1)
    except OSError as exc:
        raise ConfigError() from exc
    finally:
        os.close(descriptor)
    if len(data) > MAX_CONFIG_BYTES:
        raise ConfigError()
    try:
        document = tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError() from exc
    version = document.get("version", 1)
    if type(version) is not int or version not in {1, 2, 3}:
        raise ConfigError()
    allowed_fields = {"version", "rules"}
    if version in {2, 3}:
        allowed_fields.add("exclusions")
    if set(document) - allowed_fields:
        raise ConfigError()
    entries = document.get("rules", [])
    if not isinstance(entries, list) or len(entries) > MAX_CUSTOM_RULES:
        raise ConfigError()
    rules: list[CustomLiteralRule] = []
    literals: set[str] = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) not in ({"literal", "risk"}, {"literal", "risk", "enabled"})
        ):
            raise ConfigError()
        literal = entry["literal"]
        risk_value = entry["risk"]
        enabled = entry.get("enabled", True)
        if not isinstance(literal, str) or not 3 <= len(literal) <= 128:
            raise ConfigError()
        if any(unicodedata.category(character) in {"Cc", "Cf"} for character in literal):
            raise ConfigError()
        if not isinstance(risk_value, str):
            raise ConfigError()
        if type(enabled) is not bool:
            raise ConfigError()
        if literal in literals:
            raise ConfigError()
        literals.add(literal)
        rules.append(CustomLiteralRule(literal, _custom_rule_risk(risk_value), enabled))
    exclusions_entries = document.get("exclusions", [])
    if (
        not isinstance(exclusions_entries, list)
        or len(exclusions_entries) > MAX_CUSTOM_EXCLUSIONS
    ):
        raise ConfigError()
    exclusions: list[CustomLiteralExclusion] = []
    for entry in exclusions_entries:
        allowed_entry_fields = (
            ({"literal"}, {"literal", "enabled"})
            if version == 2
            else ({"literal", "category"}, {"literal", "category", "enabled"})
        )
        if not isinstance(entry, dict) or set(entry) not in allowed_entry_fields:
            raise ConfigError()
        literal = entry["literal"]
        enabled = entry.get("enabled", True)
        if (
            not isinstance(literal, str)
            or not 3 <= len(literal) <= 128
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in literal)
            or type(enabled) is not bool
            or literal in literals
        ):
            raise ConfigError()
        literals.add(literal)
        if version == 2:
            migrated = _migrate_v2_exclusion(literal, enabled)
            if migrated is not None:
                exclusions.append(migrated)
            continue
        category_value = entry["category"]
        try:
            category = Category(category_value)
        except (TypeError, ValueError) as exc:
            raise ConfigError() from exc
        if category not in EXCLUDABLE_CATEGORIES:
            raise ConfigError()
        exclusions.append(CustomLiteralExclusion(literal, category, enabled))
    return tuple(rules), tuple(exclusions)


def load_custom_rules(path: Path | None = None) -> tuple[CustomLiteralRule, ...]:
    return load_customizations(path)[0]


def load_custom_exclusions(
    path: Path | None = None,
) -> tuple[CustomLiteralExclusion, ...]:
    return load_customizations(path)[1]


def save_customizations(
    rules: tuple[CustomLiteralRule, ...],
    exclusions: tuple[CustomLiteralExclusion, ...],
    path: Path | None = None,
) -> None:
    if (
        type(rules) is not tuple
        or len(rules) > MAX_CUSTOM_RULES
        or type(exclusions) is not tuple
        or len(exclusions) > MAX_CUSTOM_EXCLUSIONS
    ):
        raise ConfigError()
    literals: set[str] = set()
    lines = ["version = 3"]
    for rule in rules:
        if type(rule) is not CustomLiteralRule:
            raise ConfigError()
        literal = rule.literal
        if (
            not isinstance(literal, str)
            or not 3 <= len(literal) <= 128
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in literal)
            or literal in literals
            or type(rule.risk) is not RiskLevel
            or rule.risk is RiskLevel.NONE
            or type(rule.enabled) is not bool
        ):
            raise ConfigError()
        literals.add(literal)
        lines.extend(
            (
                "",
                "[[rules]]",
                f"literal = {json.dumps(literal, ensure_ascii=True)}",
                f"risk = {json.dumps(rule.risk.value)}",
                f"enabled = {json.dumps(rule.enabled)}",
            )
        )
    for exclusion in exclusions:
        if type(exclusion) is not CustomLiteralExclusion:
            raise ConfigError()
        literal = exclusion.literal
        if (
            not isinstance(literal, str)
            or not 3 <= len(literal) <= 128
            or any(unicodedata.category(character) in {"Cc", "Cf"} for character in literal)
            or literal in literals
            or type(exclusion.category) is not Category
            or exclusion.category not in EXCLUDABLE_CATEGORIES
            or type(exclusion.enabled) is not bool
        ):
            raise ConfigError()
        literals.add(literal)
        lines.extend(
            (
                "",
                "[[exclusions]]",
                f"literal = {json.dumps(literal, ensure_ascii=True)}",
                f"category = {json.dumps(exclusion.category.value)}",
                f"enabled = {json.dumps(exclusion.enabled)}",
            )
        )
    payload = ("\n".join(lines) + "\n").encode("ascii")
    if len(payload) > MAX_CONFIG_BYTES:
        raise ConfigError()
    selected = path or default_config_path()
    if not selected.is_absolute():
        raise ConfigError()
    directory = selected.parent
    _ensure_private_config_directory(directory)
    _validate_config_target(selected)
    temporary = directory / f".{selected.name}.{secrets.token_hex(8)}.tmp"
    descriptor: int | None = None
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        with _private_umask():
            descriptor = os.open(temporary, flags, 0o600)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ConfigError()
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, selected)
        selected.chmod(0o600)
    except (AttributeError, OSError) as exc:
        raise ConfigError() from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def save_custom_rules(
    rules: tuple[CustomLiteralRule, ...], path: Path | None = None
) -> None:
    selected = path or default_config_path()
    exclusions = load_customizations(selected)[1]
    save_customizations(rules, exclusions, selected)


def _migrate_v2_exclusion(
    literal: str, enabled: bool
) -> CustomLiteralExclusion | None:
    analysis = analyze_text(literal)
    if len(analysis.detections) != 1:
        return None
    detection = analysis.detections[0]
    if (
        detection.start != 0
        or detection.end != len(literal)
        or detection.risk not in {RiskLevel.LOW, RiskLevel.MEDIUM}
        or detection.category not in EXCLUDABLE_CATEGORIES
    ):
        return None
    return CustomLiteralExclusion(literal, detection.category, enabled)


def _ensure_private_config_directory(path: Path) -> None:
    user_id = os.geteuid()
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        try:
            with _private_umask():
                path.mkdir(mode=0o700, parents=True, exist_ok=False)
        except OSError as exc:
            raise ConfigError() from exc
        info = os.lstat(path)
    except OSError as exc:
        raise ConfigError() from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != user_id
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ConfigError()


def _validate_config_target(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ConfigError() from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_size > MAX_CONFIG_BYTES
    ):
        raise ConfigError()


@contextmanager
def _private_umask():
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)
