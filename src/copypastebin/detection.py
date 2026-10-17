from __future__ import annotations

import ipaddress
import base64
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from urllib.parse import urlsplit

from .models import AnalysisResult, Category, Detection, RiskLevel


RULESET_VERSION = "10"
BIP39_RESOURCE_VERSION = "english-bip39-from-python-passlib-1.9.3-1ubuntu1"
BIP39_RESOURCE_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"

_EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}(?![\w.-])", re.I)
_HOME_PATH = re.compile(r"(?<![\w])(?:file:///home/|/home/|~/)[^\s\x00]+")
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\x00]+", re.I)
_AUTH = re.compile(r"(?im)\b(?:authorization\s*:\s*(?:basic|bearer)|bearer)\s+[A-Za-z0-9._~+/=-]{8,}")
_PEM_BLOCK = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
_PEM_HEADER = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
_OPENAI_KEY = re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])")
_ANTHROPIC_KEY = re.compile(r"(?<![A-Za-z0-9_-])sk-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])")
_GOOGLE_KEY = re.compile(r"(?<![A-Za-z0-9_-])AIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])")
_GITHUB_TOKEN = re.compile(r"(?<![A-Za-z0-9_])(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,})(?![A-Za-z0-9_])")
_SLACK_TOKEN = re.compile(r"(?<![A-Za-z0-9-])(?:xox[baprs]-[A-Za-z0-9-]{10,}|xapp-\d+-[A-Za-z0-9-]{10,})(?![A-Za-z0-9-])")
_STRIPE_KEY = re.compile(r"(?<![A-Za-z0-9_])(?:(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|whsec_[A-Za-z0-9]{16,})(?![A-Za-z0-9])")
_AWS_ACCESS_KEY = re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])")
_JWT_CANDIDATE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])")
_DATABASE_URL = re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis(?:s)?|mssql|sqlserver)://[^\s\x00]+")
_ASSIGNMENT = re.compile(r"(?im)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*([^\s,;]{4,})")
_NATURAL_SECRET = re.compile(r"(?i)\b(?:my|the)\s+(?:password|secret|api key)\s+is\s+\S{4,}")
_PHONE = re.compile(r"(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\(?\d{2,3}\)?[ .-]?){2,4}\d{2,4}(?!\w)")
_PHONE_NUMERIC_RUN = re.compile(r"(?<!\w)(?:\+|\()?\d[\d .()-]*\d(?!\w)")
_PHONE_POSITIVE_CONTEXT = re.compile(
    r"(?i)(?:\b(?:mobile|phone|tel(?:efon)?|telefon|komórka|komork[aą])\s*[:.=\-]?\s*)$"
)
_PHONE_NEGATIVE_CONTEXT = re.compile(
    r"(?i)(?:\b(?:id|identifier|invoice|order|reference|ref|serial|"
    r"identyfikator|faktura|zamówienie|zamowienie|referencja|seryjny)\s*[:=#\-]?\s*)$"
)
_DATE_CANDIDATE = re.compile(
    r"(?<!\d)(?:"
    r"(?P<year_first>\d{4})(?P<year_separator>[-./])"
    r"(?P<year_month>\d{2})(?P=year_separator)(?P<year_day>\d{2})|"
    r"(?P<day_first>\d{2})(?P<day_separator>[-./])"
    r"(?P<day_month>\d{2})(?P=day_separator)(?P<day_year>\d{4})"
    r")(?!\d)"
)
_PESEL_CANDIDATE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_IBAN_PREFIX = re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}", re.I)
_PAYMENT_CARD_CANDIDATE = re.compile(
    r"(?<!\d)(?:\d{13,19}|(?:\d{4}[ -]){3}\d{1,4})(?![ -]?\d)"
)
_BITLOCKER_RECOVERY_KEY = re.compile(
    r"(?<!\d)(?:\d{48}|\d{6}(?:-\d{6}){7}|\d{6}(?: \d{6}){7})(?!\d)"
)
_LABELED_RECOVERY_KEY = re.compile(
    r"(?im)\b(?:bitlocker\s+)?(?:recovery\s+(?:key|code|password)|"
    r"klucz\s+odzyskiwania)\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9._-]{7,255})"
)
_TOKENISH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9+/=_-]{24,}(?![A-Za-z0-9])")
_IP_CANDIDATE = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f:.]{3,})(?![\w:])")
_SEED_LIKE = re.compile(r"(?<![A-Za-z])(?:[a-z]{3,10}[ \t]+){11,23}[a-z]{3,10}(?![A-Za-z])")
_SECRETLIKE_IDENTIFIER_SEGMENTS = frozenset(
    {
        "auth",
        "bearer",
        "credential",
        "credentials",
        "key",
        "passwd",
        "password",
        "secret",
        "token",
    }
)

FIAT_CURRENCIES = (
    "USD", "EUR", "JPY", "GBP", "CNY", "CHF", "AUD", "CAD", "HKD", "SGD",
    "INR", "KRW", "SEK", "MXN", "NZD", "NOK", "TWD", "BRL", "ZAR", "PLN",
)
CRYPTO_CURRENCIES = (
    "BTC", "ETH", "USDT", "BNB", "XRP", "USDC", "SOL", "TRX", "HYPE", "ZEC",
    "DOGE", "XMR", "LINK", "LEO", "ADA", "XLM", "USDE", "DAI", "BCH", "USD1",
)
_FIAT_CODES = "|".join(FIAT_CURRENCIES)
_CRYPTO_CODES = "|".join(CRYPTO_CURRENCIES)
_USD_NUMBER = r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,4})?"
_FIAT_NUMBER = (
    r"(?:\d+|\d{1,3}(?:[ \u00a0]\d{3})+|\d{1,3}(?:,\d{3})+|"
    r"\d{1,3}(?:\.\d{3})+)(?:[.,]\d{1,4})?"
)
_MONEY = re.compile(
    rf"(?<![0-9][ .,])(?<![\w$€£])(?:"
    rf"-?{_FIAT_NUMBER}\s*(?:{_FIAT_CODES}|zł)|"
    rf"-?(?:[$€£])\s*{_FIAT_NUMBER}"
    rf")(?![\w])",
    re.I,
)
_CRYPTO_NUMBER = (
    r"(?:\d+|\d{1,3}(?: \d{3})+|\d{1,3}(?:,\d{3})+|"
    r"\d{1,3}(?:\.\d{3})+)(?:[.,]\d{1,18})?"
)
_CRYPTO_MONEY = re.compile(
    rf"(?<![0-9][ .,-])(?<!\w)-?{_CRYPTO_NUMBER}\s*(?:{_CRYPTO_CODES})(?!\w)",
    re.I,
)

_PRIORITY = {
    RiskLevel.CRITICAL: 0,
    RiskLevel.HIGH: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 3,
    RiskLevel.NONE: 4,
}

_IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20,
    "BE": 16, "BG": 22, "BH": 22, "BR": 29, "BY": 28, "CH": 21,
    "CR": 22, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "DO": 28,
    "EE": 20, "EG": 29, "ES": 24, "FI": 18, "FO": 18, "FR": 27,
    "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27, "GT": 28,
    "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23, "IS": 26,
    "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32,
    "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MD": 24,
    "ME": 22, "MK": 19, "MR": 27, "MT": 31, "MU": 30, "NL": 18,
    "NO": 15, "PK": 24, "PL": 28, "PS": 29, "PT": 25, "QA": 29,
    "RO": 24, "RS": 22, "SA": 24, "SC": 31, "SE": 24, "SI": 19,
    "SK": 24, "SM": 27, "ST": 25, "SV": 28, "TL": 23, "TN": 24,
    "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}


@dataclass(frozen=True, slots=True, repr=False)
class CustomLiteralRule:
    literal: str
    risk: RiskLevel
    enabled: bool = True

    def __repr__(self) -> str:
        return (
            "CustomLiteralRule(risk="
            f"{self.risk.value!r}, enabled={self.enabled!r}, literal_redacted=True)"
        )


@dataclass(frozen=True, slots=True, repr=False)
class CustomLiteralExclusion:
    literal: str
    category: Category
    enabled: bool = True

    def __repr__(self) -> str:
        return (
            "CustomLiteralExclusion(category="
            f"{self.category.value!r}, enabled={self.enabled!r}, "
            "literal_redacted=True)"
        )


EXCLUDABLE_CATEGORIES = frozenset(
    {
        Category.EMAIL,
        Category.PHONE,
        Category.IBAN,
        Category.HOME_PATH,
        Category.IP_ADDRESS,
        Category.MONEY_AMOUNT_PLN_USD,
        Category.CRYPTO_AMOUNT_BTC_XRP,
    }
)


class Bip39ResourceError(Exception):
    def __str__(self) -> str:
        return "Wbudowany zasób reguł bezpieczeństwa jest niedostępny lub uszkodzony."

    def __repr__(self) -> str:
        return "Bip39ResourceError(redacted=True)"


@lru_cache(maxsize=1)
def load_bip39_words() -> tuple[str, ...]:
    try:
        data = files("copypastebin.data").joinpath("bip39_english.txt").read_bytes()
        decoded = data.decode("ascii")
    except (ImportError, OSError, TypeError, UnicodeDecodeError) as exc:
        raise Bip39ResourceError() from exc
    words = tuple(decoded.splitlines())
    if (
        sha256(data).hexdigest() != BIP39_RESOURCE_SHA256
        or len(words) != 2048
        or len(set(words)) != 2048
        or words != tuple(sorted(words))
        or any(not word.isalpha() or not word.islower() for word in words)
    ):
        raise Bip39ResourceError()
    return words


def bip39_checksum_is_valid(words: tuple[str, ...], word_index: dict[str, int]) -> bool:
    if len(words) not in {12, 15, 18, 21, 24}:
        return False
    try:
        bit_string = "".join(f"{word_index[word]:011b}" for word in words)
    except KeyError:
        return False
    entropy_length = len(bit_string) * 32 // 33
    checksum_length = len(bit_string) - entropy_length
    entropy = int(bit_string[:entropy_length], 2).to_bytes(entropy_length // 8, "big")
    expected = f"{int.from_bytes(sha256(entropy).digest(), 'big'):0256b}"[:checksum_length]
    return bit_string[entropy_length:] == expected


def _entropy(value: str) -> float:
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _valid_jwt(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 3:
        return False
    try:
        padded = parts[0] + "=" * (-len(parts[0]) % 4)
        header = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        type(header) is dict
        and type(header.get("alg")) is str
        and 1 <= len(header["alg"]) <= 32
        and header["alg"].lower() != "none"
    )


def _is_wordlike_identifier(value: str) -> bool:
    segments = re.split(r"[-_]", value)
    if len(segments) < 3 or any(not segment for segment in segments):
        return False
    if any(segment in _SECRETLIKE_IDENTIFIER_SEGMENTS for segment in segments):
        return False
    word_segments = [
        segment
        for segment in segments
        if segment.isascii() and segment.isalpha() and segment.islower()
    ]
    return len(word_segments) >= 2 and all(
        segment.isdigit()
        or (segment.isascii() and segment.isalpha() and segment.islower())
        for segment in segments
    )


def _valid_money(match: re.Match[str]) -> bool:
    raw = match.group(0)
    if raw.upper().rstrip().endswith("USD"):
        return re.fullmatch(rf"-?{_USD_NUMBER}\s*USD", raw, re.I) is not None
    if raw.lstrip("-").startswith("$"):
        return re.fullmatch(rf"-?\$\s*{_USD_NUMBER}", raw) is not None
    numeric = re.sub(
        rf"(?i)\s*(?:{_FIAT_CODES}|zł)$", "", raw
    ).replace("$", "").replace("€", "").replace("£", "").lstrip("-")
    compact = numeric.replace(" ", "").replace("\u00a0", "")
    if "," in compact and "." in compact:
        decimal = "," if compact.rfind(",") > compact.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        normalized = compact.replace(thousands, "").replace(decimal, ".")
    elif "," in compact or "." in compact:
        separator = "," if "," in compact else "."
        head, tail = compact.rsplit(separator, 1)
        normalized = (
            compact.replace(separator, "")
            if len(tail) == 3 and len(head) <= 3
            else head.replace(separator, "") + "." + tail
        )
    else:
        normalized = compact
    try:
        Decimal(normalized)
    except InvalidOperation:
        return False
    return True


def _valid_pesel(value: str) -> bool:
    if len(value) != 11 or not value.isascii() or not value.isdigit():
        return False
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    checksum = (10 - sum(int(digit) * weight for digit, weight in zip(value[:10], weights)) % 10) % 10
    if checksum != int(value[-1]):
        return False
    year = int(value[0:2])
    month = int(value[2:4])
    day = int(value[4:6])
    if 1 <= month <= 12:
        year += 1900
    elif 21 <= month <= 32:
        year += 2000
        month -= 20
    elif 41 <= month <= 52:
        year += 2100
        month -= 40
    elif 61 <= month <= 72:
        year += 2200
        month -= 60
    elif 81 <= month <= 92:
        year += 1800
        month -= 80
    else:
        return False
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def _valid_iban(value: str) -> bool:
    compact = value.replace(" ", "").upper()
    if (
        not 15 <= len(compact) <= 34
        or not compact[:2].isalpha()
        or not compact[:2].isascii()
        or not compact[2:4].isdigit()
        or not compact[4:].isalnum()
        or not compact.isascii()
    ):
        return False
    remainder = 0
    for character in compact[4:] + compact[:4]:
        digits = character if character.isdigit() else str(ord(character) - 55)
        for digit in digits:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder == 1


def _iban_candidates(text: str) -> list[tuple[int, int, str]]:
    candidates: list[tuple[int, int, str]] = []
    for prefix in _IBAN_PREFIX.finditer(text):
        country = prefix.group(0)[:2].upper()
        expected_length = _IBAN_LENGTHS.get(country)
        if expected_length is None:
            continue
        compact: list[str] = []
        end = prefix.start()
        for index in range(prefix.start(), len(text)):
            character = text[index]
            if character == " ":
                continue
            if not character.isascii() or not character.isalnum():
                break
            compact.append(character)
            end = index + 1
            if len(compact) == expected_length:
                candidate = "".join(compact)
                if _valid_iban(candidate):
                    candidates.append((prefix.start(), end, candidate))
                break
    return candidates


def _valid_payment_card(value: str) -> bool:
    digits = value.replace(" ", "").replace("-", "")
    if (
        not 13 <= len(digits) <= 19
        or not digits.isascii()
        or not digits.isdigit()
        or len(set(digits)) == 1
    ):
        return False
    total = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        number = int(character)
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _valid_bitlocker_recovery_key(value: str) -> bool:
    digits = value.replace(" ", "").replace("-", "")
    if len(digits) != 48 or not digits.isascii() or not digits.isdigit():
        return False
    groups = (digits[index:index + 6] for index in range(0, len(digits), 6))
    return all(
        int(group) <= 720885 and int(group) % 11 == 0
        for group in groups
    )


def _phone_search_text(text: str) -> str:
    masked = list(text)
    for match in _DATE_CANDIDATE.finditer(text):
        if match.group("year_first") is not None:
            year = int(match.group("year_first"))
            month = int(match.group("year_month"))
            day = int(match.group("year_day"))
        else:
            year = int(match.group("day_year"))
            month = int(match.group("day_month"))
            day = int(match.group("day_first"))
        try:
            date(year, month, day)
        except ValueError:
            continue
        masked[match.start():match.end()] = "#" * (match.end() - match.start())
    return "".join(masked)


def _phone_context(pattern: re.Pattern[str], text: str, start: int) -> bool:
    return pattern.search(text[max(0, start - 40):start]) is not None


def _valid_phone_candidate(text: str, start: int, end: int) -> bool:
    candidate = text[start:end]
    digits = "".join(character for character in candidate if character.isdigit())
    if (
        not digits.isascii()
        or not 7 <= len(digits) <= 15
        or candidate.count("+") > 1
        or ("+" in candidate and not candidate.startswith("+"))
        or candidate.count("(") != candidate.count(")")
        or candidate.count("(") > 1
        or re.search(r"[ .-]{2,}", candidate) is not None
        or _PHONE.fullmatch(candidate) is None
    ):
        return False

    positive_context = _phone_context(_PHONE_POSITIVE_CONTEXT, text, start)
    strong_structure = candidate.startswith("+") or "(" in candidate
    groups = re.findall(r"\d+", candidate)
    if (
        len(groups) >= 3
        and all(len(group) >= 4 for group in groups)
        and not (positive_context or strong_structure)
    ):
        return False
    if (
        _phone_context(_PHONE_NEGATIVE_CONTEXT, text, start)
        and not (positive_context or strong_structure)
    ):
        return False
    return True


def _phone_candidates(text: str) -> list[tuple[int, int]]:
    search_text = _phone_search_text(text)
    candidates: list[tuple[int, int]] = []
    for match in _PHONE_NUMERIC_RUN.finditer(search_text):
        if _valid_phone_candidate(text, match.start(), match.end()):
            candidates.append(match.span())
            continue
        digit_count = sum(character.isdigit() for character in match.group(0))
        if digit_count <= 15 or " " not in match.group(0):
            continue
        positive_context = _phone_context(
            _PHONE_POSITIVE_CONTEXT, text, match.start()
        )
        if (
            _phone_context(_PHONE_NEGATIVE_CONTEXT, text, match.start())
            and not positive_context
        ):
            continue
        for part in re.finditer(r"\S+", match.group(0)):
            start = match.start() + part.start()
            end = match.start() + part.end()
            strong_structure = (
                part.group(0).startswith("+")
                or any(character in part.group(0) for character in "-.()")
            )
            if not (positive_context or strong_structure):
                continue
            if _valid_phone_candidate(text, start, end):
                candidates.append((start, end))
    return candidates


def _pattern_detections(text: str, pattern: re.Pattern[str], category: Category, risk: RiskLevel, rule_id: str, *, heuristic: bool = False) -> list[Detection]:
    return [Detection(rule_id, category, match.start(), match.end(), risk, heuristic) for match in pattern.finditer(text)]


def _raw_detections(text: str, custom_rules: tuple[CustomLiteralRule, ...], bip39_words: tuple[str, ...]) -> list[Detection]:
    found: list[Detection] = []
    private_key_block_spans = [match.span() for match in _PEM_BLOCK.finditer(text)]
    for start, end in private_key_block_spans:
        found.append(Detection(
            "private-key-block-v2", Category.PRIVATE_KEY, start, end,
            RiskLevel.CRITICAL,
        ))
    for match in _PEM_HEADER.finditer(text):
        if not any(start <= match.start() < end for start, end in private_key_block_spans):
            found.append(Detection(
                "private-key-incomplete-v2", Category.PRIVATE_KEY,
                match.start(), len(text), RiskLevel.CRITICAL, True,
            ))
    recovery_key_spans: list[tuple[int, int]] = []
    for match in _BITLOCKER_RECOVERY_KEY.finditer(text):
        if _valid_bitlocker_recovery_key(match.group(0)):
            found.append(Detection(
                "bitlocker-recovery-key-v1",
                Category.RECOVERY_KEY,
                match.start(),
                match.end(),
                RiskLevel.CRITICAL,
            ))
            recovery_key_spans.append((match.start(), match.end()))
    for match in _LABELED_RECOVERY_KEY.finditer(text):
        start, end = match.span(1)
        found.append(Detection(
            "labeled-recovery-key-v1",
            Category.RECOVERY_KEY,
            start,
            end,
            RiskLevel.CRITICAL,
        ))
        recovery_key_spans.append((start, end))
    specifications = (
        (_ANTHROPIC_KEY, Category.ANTHROPIC_API_KEY, RiskLevel.HIGH, "anthropic-api-key-v1", False),
        (_OPENAI_KEY, Category.OPENAI_API_KEY, RiskLevel.HIGH, "openai-api-key-v1", False),
        (_GOOGLE_KEY, Category.GOOGLE_API_KEY, RiskLevel.HIGH, "google-api-key-v1", False),
        (_GITHUB_TOKEN, Category.GITHUB_TOKEN, RiskLevel.HIGH, "github-token-v1", False),
        (_SLACK_TOKEN, Category.SLACK_TOKEN, RiskLevel.HIGH, "slack-token-v1", False),
        (_STRIPE_KEY, Category.STRIPE_KEY, RiskLevel.HIGH, "stripe-key-v1", False),
        (_AWS_ACCESS_KEY, Category.AWS_ACCESS_KEY, RiskLevel.HIGH, "aws-access-key-v1", False),
        (_DATABASE_URL, Category.DATABASE_URL, RiskLevel.HIGH, "database-url-v1", False),
        (_AUTH, Category.AUTHORIZATION, RiskLevel.HIGH, "authorization-v1", False),
        (_ASSIGNMENT, Category.SECRET_ASSIGNMENT, RiskLevel.HIGH, "secret-assignment-v1", False),
        (_NATURAL_SECRET, Category.SECRET_ASSIGNMENT, RiskLevel.HIGH, "natural-secret-v1", True),
        (_EMAIL, Category.EMAIL, RiskLevel.MEDIUM, "email-v1", False),
        (_HOME_PATH, Category.HOME_PATH, RiskLevel.LOW, "home-path-v1", False),
    )
    for pattern, category, risk, rule_id, heuristic in specifications:
        found.extend(_pattern_detections(text, pattern, category, risk, rule_id, heuristic=heuristic))

    for start, end in _phone_candidates(text):
        if not any(
            start < recovery_end and recovery_start < end
            for recovery_start, recovery_end in recovery_key_spans
        ):
            found.append(Detection(
                "phone-v2", Category.PHONE, start, end,
                RiskLevel.LOW, True,
            ))

    for match in _URL.finditer(text):
        try:
            parsed = urlsplit(match.group(0))
        except ValueError:
            continue
        if parsed.username is not None or parsed.password is not None:
            found.append(Detection("url-credentials-v1", Category.URL_CREDENTIALS, match.start(), match.end(), RiskLevel.HIGH))

    for match in _IP_CANDIDATE.finditer(text):
        candidate = match.group(0).strip(".")
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        offset = match.group(0).find(candidate)
        found.append(Detection("ip-address-v1", Category.IP_ADDRESS, match.start() + offset, match.start() + offset + len(candidate), RiskLevel.LOW))

    for match in _PESEL_CANDIDATE.finditer(text):
        if _valid_pesel(match.group(0)):
            found.append(Detection("pesel-checksum-v1", Category.PESEL, match.start(), match.end(), RiskLevel.HIGH))

    iban_spans: list[tuple[int, int]] = []
    for start, end, candidate in _iban_candidates(text):
        if _valid_iban(candidate):
            found.append(Detection("iban-mod97-v1", Category.IBAN, start, end, RiskLevel.MEDIUM))
            iban_spans.append((start, end))

    for match in _PAYMENT_CARD_CANDIDATE.finditer(text):
        if (
            not any(match.start() < end and start < match.end() for start, end in iban_spans)
            and _valid_payment_card(match.group(0))
        ):
            found.append(Detection("payment-card-luhn-v1", Category.PAYMENT_CARD, match.start(), match.end(), RiskLevel.HIGH))

    for match in _MONEY.finditer(text):
        if _valid_money(match):
            found.append(Detection("fiat-money-v2", Category.MONEY_AMOUNT_PLN_USD, match.start(), match.end(), RiskLevel.LOW))

    for match in _CRYPTO_MONEY.finditer(text):
        found.append(
            Detection(
                "crypto-money-v2",
                Category.CRYPTO_AMOUNT_BTC_XRP,
                match.start(),
                match.end(),
                RiskLevel.LOW,
            )
        )

    for match in _TOKENISH.finditer(text):
        candidate = match.group(0)
        if (
            not _is_wordlike_identifier(candidate)
            and _entropy(candidate) >= 3.5
            and any(c.isalpha() for c in candidate)
            and any(c.isdigit() for c in candidate)
        ):
            found.append(Detection("token-entropy-v2", Category.TOKEN, match.start(), match.end(), RiskLevel.HIGH, True))

    for match in _JWT_CANDIDATE.finditer(text):
        if _valid_jwt(match.group(0)):
            found.append(Detection(
                "jwt-structure-v1", Category.JWT, match.start(), match.end(),
                RiskLevel.HIGH,
            ))

    bip39_word_index = {word: index for index, word in enumerate(bip39_words)}
    for match in _SEED_LIKE.finditer(text):
        phrase_words = tuple(match.group(0).split())
        if len(phrase_words) in {12, 15, 18, 21, 24}:
            if bip39_checksum_is_valid(phrase_words, bip39_word_index):
                rule_id = "bip39-confirmed-v1"
                heuristic = False
            elif all(word in bip39_word_index for word in phrase_words):
                rule_id = "possible-bip39-invalid-checksum-v1"
                heuristic = True
            else:
                rule_id = "possible-seed-structure-v1"
                heuristic = True
            found.append(Detection(rule_id, Category.POSSIBLE_SEED_PHRASE, match.start(), match.end(), RiskLevel.CRITICAL, heuristic))
    for index, rule in enumerate(custom_rules):
        if not rule.enabled:
            continue
        start = 0
        while True:
            position = text.find(rule.literal, start)
            if position < 0:
                break
            found.append(Detection(f"custom-literal-{index}", Category.CUSTOM_RULE, position, position + len(rule.literal), rule.risk))
            start = position + len(rule.literal)
    return found


def _select_non_overlapping(found: list[Detection]) -> tuple[Detection, ...]:
    ordered = sorted(found, key=lambda item: (_PRIORITY[item.risk], -(item.end - item.start), item.rule_id, item.start))
    selected: list[Detection] = []
    for candidate in ordered:
        if any(candidate.start < existing.end and existing.start < candidate.end for existing in selected):
            continue
        selected.append(candidate)
    return tuple(sorted(selected, key=lambda item: (item.start, item.end, item.rule_id)))


def _literal_exclusion_spans(
    text: str,
    exclusions: tuple[CustomLiteralExclusion, ...],
) -> frozenset[tuple[int, int, Category]]:
    spans: set[tuple[int, int, Category]] = set()
    for exclusion in exclusions:
        if not exclusion.enabled:
            continue
        start = 0
        while True:
            position = text.find(exclusion.literal, start)
            if position < 0:
                break
            end = position + len(exclusion.literal)
            spans.add((position, end, exclusion.category))
            start = end
    return frozenset(spans)


def analyze_text(
    text: str,
    custom_rules: tuple[CustomLiteralRule, ...] = (),
    disabled_categories: frozenset[Category] = frozenset(),
    custom_exclusions: tuple[CustomLiteralExclusion, ...] = (),
) -> AnalysisResult:
    if type(disabled_categories) is not frozenset or any(
        type(category) is not Category for category in disabled_categories
    ):
        raise TypeError("disabled_categories must contain Category values")
    if type(custom_exclusions) is not tuple or any(
        type(exclusion) is not CustomLiteralExclusion
        or type(exclusion.literal) is not str
        or not 3 <= len(exclusion.literal) <= 128
        or type(exclusion.category) is not Category
        or exclusion.category not in EXCLUDABLE_CATEGORIES
        or type(exclusion.enabled) is not bool
        for exclusion in custom_exclusions
    ):
        raise TypeError("custom_exclusions must contain CustomLiteralExclusion values")
    bip39_words = load_bip39_words()
    excluded_spans = _literal_exclusion_spans(text, custom_exclusions)
    found = (
        detection
        for detection in _raw_detections(text, custom_rules, bip39_words)
        if detection.category not in disabled_categories
        and (
            detection.risk not in {RiskLevel.LOW, RiskLevel.MEDIUM}
            or (detection.start, detection.end, detection.category)
            not in excluded_spans
        )
    )
    selected = _select_non_overlapping(list(found))
    labels: dict[tuple[Category, str], int] = {}
    next_number: dict[Category, int] = {}
    pieces: list[str] = []
    cursor = 0
    for detection in selected:
        pieces.append(text[cursor:detection.start])
        raw = text[detection.start:detection.end]
        key = (detection.category, raw)
        if key not in labels:
            number = next_number.get(detection.category, 0) + 1
            next_number[detection.category] = number
            labels[key] = number
        pieces.append(f"[{detection.category.value}_{labels[key]}]")
        cursor = detection.end
    pieces.append(text[cursor:])
    highest = min((item.risk for item in selected), key=lambda value: _PRIORITY[value], default=RiskLevel.NONE)
    return AnalysisResult(selected, "".join(pieces), highest)
