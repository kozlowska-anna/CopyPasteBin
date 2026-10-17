from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from .models import Category, RiskLevel


NOTIFICATION_TIMEOUT_SECONDS = 5.0


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


class DesktopNotifier:
    def notify(self, notification: SafeNotification) -> None:
        if type(notification) is not SafeNotification:
            raise NotificationError()
        executable = shutil.which("notify-send")
        if executable is None:
            raise NotificationError()
        title = f"CopyPasteBin: ryzyko {notification.risk.value}"
        count = sum(value for _, value in notification.category_counts)
        body = (
            f"Wykryte kategorie: {len(notification.category_counts)}; "
            f"trafienia: {count}. Sprawdź bieżący schowek jawnie w CopyPasteBin."
        )
        try:
            result = subprocess.run(
                [executable, "--app-name", "CopyPasteBin", title, body],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise NotificationError() from exc
        if result.returncode != 0:
            raise NotificationError()
