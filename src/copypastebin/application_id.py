from __future__ import annotations

import re


UNKNOWN_APPLICATION = "unknown"
MAX_APPLICATION_ID_LENGTH = 128
_APPLICATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def normalize_application_id(value: object) -> str:
    if type(value) is not str or not _APPLICATION_ID.fullmatch(value):
        return UNKNOWN_APPLICATION
    return value
