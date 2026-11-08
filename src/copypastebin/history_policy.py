from __future__ import annotations

import math
from collections import Counter

from .models import Category, Detection, RiskLevel


SECRET_CATEGORIES = frozenset(
    {
        Category.RECOVERY_KEY,
        Category.URL_CREDENTIALS,
        Category.AUTHORIZATION,
        Category.PRIVATE_KEY,
        Category.OPENAI_API_KEY,
        Category.ANTHROPIC_API_KEY,
        Category.GOOGLE_API_KEY,
        Category.GITHUB_TOKEN,
        Category.SLACK_TOKEN,
        Category.STRIPE_KEY,
        Category.AWS_ACCESS_KEY,
        Category.JWT,
        Category.DATABASE_URL,
        Category.TOKEN,
        Category.SECRET_ASSIGNMENT,
        Category.POSSIBLE_SEED_PHRASE,
    }
)


def history_text_is_eligible(
    text: str,
    detections: tuple[Detection, ...],
) -> bool:
    """Return a history-only storage decision without retaining the text."""
    if type(text) is not str or type(detections) is not tuple:
        raise TypeError("invalid history policy input")
    if any(
        type(item) is not Detection
        or item.category in SECRET_CATEGORIES
        or item.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        for item in detections
    ):
        return False
    return not _looks_like_standalone_generated_secret(text, detections)


def _looks_like_standalone_generated_secret(
    text: str,
    detections: tuple[Detection, ...],
) -> bool:
    candidate = _without_one_trailing_line_ending(text)
    if (
        not 12 <= len(candidate) <= 128
        or any(character.isspace() for character in candidate)
        or "://" in candidate
        or candidate.startswith(("/", "./", "../"))
        or any(
            item.category is Category.EMAIL
            and item.start == 0
            and item.end == len(candidate)
            for item in detections
        )
    ):
        return False
    classes = sum(
        (
            any(
                character.isascii() and character.islower()
                for character in candidate
            ),
            any(
                character.isascii() and character.isupper()
                for character in candidate
            ),
            any(
                character.isascii() and character.isdigit()
                for character in candidate
            ),
            any(
                character.isascii() and not character.isalnum()
                for character in candidate
            ),
        )
    )
    if classes < 3 or (len(candidate) < 16 and classes < 4):
        return False
    counts = Counter(candidate)
    entropy = -sum(
        (count / len(candidate)) * math.log2(count / len(candidate))
        for count in counts.values()
    )
    return entropy >= 3.5 and len(counts) / len(candidate) >= 0.6


def _without_one_trailing_line_ending(text: str) -> str:
    if text.endswith("\r\n"):
        return text[:-2]
    if text.endswith("\n"):
        return text[:-1]
    return text
