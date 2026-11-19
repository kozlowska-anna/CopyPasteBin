from __future__ import annotations

from dataclasses import dataclass

from .models import Category, RiskLevel


class NotificationError(Exception):
    def __str__(self) -> str:
        return "Nie udało się bezpiecznie wyświetlić powiadomienia."

    def __repr__(self) -> str:
        return "NotificationError(redacted=True)"


@dataclass(frozen=True, slots=True, repr=False)
class SafeNotification:
    risk: RiskLevel
    category_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if type(self.risk) is not RiskLevel or self.risk is RiskLevel.NONE:
            raise NotificationError()
        if type(self.category_counts) is not tuple:
            raise NotificationError()
        allowed = {category.value for category in Category}
        previous = ""
        for item in self.category_counts:
            if type(item) is not tuple or len(item) != 2:
                raise NotificationError()
            category, count = item
            if (
                type(category) is not str
                or category not in allowed
                or category <= previous
                or type(count) is not int
                or count <= 0
            ):
                raise NotificationError()
            previous = category

    def __repr__(self) -> str:
        return (
            "SafeNotification(risk="
            f"{self.risk.value!r}, categories={len(self.category_counts)}, "
            "content_redacted=True)"
        )
