from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    # Source compatibility for callers; serialized values use the new scale.
    INFORMATION = "none"
    WARNING = "medium"


class Category(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    PESEL = "PESEL"
    IBAN = "IBAN"
    PAYMENT_CARD = "PAYMENT_CARD"
    RECOVERY_KEY = "RECOVERY_KEY"
    HOME_PATH = "HOME_PATH"
    IP_ADDRESS = "IP_ADDRESS"
    URL_CREDENTIALS = "URL_CREDENTIALS"
    AUTHORIZATION = "AUTHORIZATION"
    PRIVATE_KEY = "PRIVATE_KEY"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    GOOGLE_API_KEY = "GOOGLE_API_KEY"
    GITHUB_TOKEN = "GITHUB_TOKEN"
    SLACK_TOKEN = "SLACK_TOKEN"
    STRIPE_KEY = "STRIPE_KEY"
    AWS_ACCESS_KEY = "AWS_ACCESS_KEY"
    JWT = "JWT"
    DATABASE_URL = "DATABASE_URL"
    TOKEN = "TOKEN"
    SECRET_ASSIGNMENT = "SECRET_ASSIGNMENT"
    POSSIBLE_SEED_PHRASE = "POSSIBLE_SEED_PHRASE"
    MONEY_AMOUNT_PLN_USD = "MONEY_AMOUNT_PLN_USD"
    CRYPTO_AMOUNT_BTC_XRP = "CRYPTO_AMOUNT_BTC_XRP"
    CUSTOM_RULE = "CUSTOM_RULE"


@dataclass(frozen=True, slots=True, repr=False)
class Detection:
    rule_id: str
    category: Category
    start: int
    end: int
    risk: RiskLevel
    heuristic: bool = False

    def __repr__(self) -> str:
        return (
            "Detection(category="
            f"{self.category.value!r}, risk={self.risk.value!r}, redacted=True)"
        )


@dataclass(frozen=True, slots=True, repr=False)
class AnalysisResult:
    detections: tuple[Detection, ...]
    redacted_text: str
    highest_risk: RiskLevel

    def __repr__(self) -> str:
        return (
            "AnalysisResult(detections="
            f"{len(self.detections)}, highest_risk={self.highest_risk.value!r}, "
            "text_redacted=True)"
        )

    @property
    def category_counts(self) -> tuple[tuple[str, int], ...]:
        counts: dict[str, int] = {}
        for detection in self.detections:
            key = detection.category.value
            counts[key] = counts.get(key, 0) + 1
        return tuple(sorted(counts.items()))
