#!/usr/bin/env python3
"""Deterministic, synthetic quality benchmark for the built-in ruleset."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from copypastebin.detection import RULESET_VERSION, analyze_text
from copypastebin.models import Category


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    category: Category
    text: str
    should_detect: bool


CASES = (
    BenchmarkCase(Category.EMAIL, "person@example.com", True),
    BenchmarkCase(Category.EMAIL, "person at example dot com", False),
    BenchmarkCase(Category.PHONE, "+48 123 456 789", True),
    BenchmarkCase(Category.PHONE, "2026-10-11", False),
    BenchmarkCase(Category.PHONE, "1234-5678-9012-3456-7890-1234", False),
    BenchmarkCase(Category.PHONE, "ID: 501-234-567", False),
    BenchmarkCase(Category.PHONE, "123456789 012345678", False),
    BenchmarkCase(Category.PHONE, "phone: 123456789 501234567", True),
    BenchmarkCase(Category.PESEL, "44051401458", True),
    BenchmarkCase(Category.PESEL, "44051401459", False),
    BenchmarkCase(Category.IBAN, "PL61 1090 1014 0000 0712 1981 2874", True),
    BenchmarkCase(Category.IBAN, "PL62 1090 1014 0000 0712 1981 2874", False),
    BenchmarkCase(Category.PAYMENT_CARD, "4111 1111 1111 1111", True),
    BenchmarkCase(Category.PAYMENT_CARD, "4111 1111 1111 1112", False),
    BenchmarkCase(
        Category.RECOVERY_KEY,
        "111111-222222-333333-444444-555555-666666-700007-720885",
        True,
    ),
    BenchmarkCase(
        Category.RECOVERY_KEY,
        "111111-222222-333333-444444-555555-666666-700007-720884",
        False,
    ),
    BenchmarkCase(Category.HOME_PATH, "/home/example/private.txt", True),
    BenchmarkCase(Category.HOME_PATH, "/srv/example/public.txt", False),
    BenchmarkCase(Category.IP_ADDRESS, "192.0.2.10", True),
    BenchmarkCase(Category.IP_ADDRESS, "999.999.999.999", False),
    BenchmarkCase(
        Category.URL_CREDENTIALS,
        "https://synthetic-user:synthetic-pass@example.invalid/path",
        True,
    ),
    BenchmarkCase(Category.URL_CREDENTIALS, "https://example.invalid/path", False),
    BenchmarkCase(
        Category.AUTHORIZATION,
        "Authorization: Bearer CPBINSYNTHETIC012345",
        True,
    ),
    BenchmarkCase(Category.AUTHORIZATION, "Authorization is required", False),
    BenchmarkCase(
        Category.PRIVATE_KEY,
        "-----BEGIN PRIVATE KEY-----\nCPBIN_SYNTHETIC_BODY",
        True,
    ),
    BenchmarkCase(Category.PRIVATE_KEY, "-----BEGIN PUBLIC KEY-----", False),
    BenchmarkCase(
        Category.OPENAI_API_KEY,
        "sk-proj-CPBINSYNTHETIC0123456789abcdef",
        True,
    ),
    BenchmarkCase(Category.OPENAI_API_KEY, "sk-example", False),
    BenchmarkCase(
        Category.ANTHROPIC_API_KEY,
        "sk-ant-api03-CPBINSYNTHETIC0123456789abcdef",
        True,
    ),
    BenchmarkCase(Category.ANTHROPIC_API_KEY, "sk-ant-example-short", False),
    BenchmarkCase(
        Category.GOOGLE_API_KEY,
        "AIzaCpbSynthetic_0123456789abcdefghijkl",
        True,
    ),
    BenchmarkCase(Category.GOOGLE_API_KEY, "AIza-example-documentation", False),
    BenchmarkCase(
        Category.GITHUB_TOKEN,
        "github_pat_CPBIN_SYNTHETIC_0123456789abcdef",
        True,
    ),
    BenchmarkCase(Category.GITHUB_TOKEN, "github_pat_example", False),
    BenchmarkCase(Category.SLACK_TOKEN, "xoxb-CPBINSYNTHETIC-0123456789", True),
    BenchmarkCase(Category.SLACK_TOKEN, "xoxb-example", False),
    BenchmarkCase(Category.STRIPE_KEY, "sk_live_CPBINSYNTHETIC0123456789", True),
    BenchmarkCase(Category.STRIPE_KEY, "sk_live_example", False),
    BenchmarkCase(Category.AWS_ACCESS_KEY, "AKIACPBINSYNTHETIC12", True),
    BenchmarkCase(Category.AWS_ACCESS_KEY, "AKIAEXAMPLE", False),
    BenchmarkCase(
        Category.JWT,
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJzeW50aGV0aWMifQ.CPBINSYNTHETICSIGNATURE",
        True,
    ),
    BenchmarkCase(
        Category.JWT,
        "eyJhbGciOiJub25lIn0.eyJzdWIiOiJzeW50aGV0aWMifQ.CPBINSIGNATURE",
        False,
    ),
    BenchmarkCase(
        Category.DATABASE_URL,
        "postgresql://cpbin_user:synthetic_password@db.invalid/cpbin",
        True,
    ),
    BenchmarkCase(Category.DATABASE_URL, "https://db.invalid/cpbin", False),
    BenchmarkCase(Category.SECRET_ASSIGNMENT, "API_KEY=CPBIN_SYNTHETIC_ONLY", True),
    BenchmarkCase(Category.SECRET_ASSIGNMENT, "API_VERSION=synthetic", False),
    BenchmarkCase(
        Category.TOKEN,
        "A7f9K2mQ8xR4vN6pT3zW5cY1",
        True,
    ),
    BenchmarkCase(Category.TOKEN, "order-confirmation-2026-10-11", False),
    BenchmarkCase(
        Category.POSSIBLE_SEED_PHRASE,
        "abandon abandon abandon abandon abandon abandon abandon abandon "
        "abandon abandon abandon about",
        True,
    ),
    BenchmarkCase(
        Category.POSSIBLE_SEED_PHRASE,
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
        False,
    ),
    BenchmarkCase(Category.MONEY_AMOUNT_PLN_USD, "1 234,56 PLN", True),
    BenchmarkCase(Category.MONEY_AMOUNT_PLN_USD, "123456", False),
    BenchmarkCase(Category.CRYPTO_AMOUNT_BTC_XRP, "0.25 BTC", True),
    BenchmarkCase(Category.CRYPTO_AMOUNT_BTC_XRP, "BTC", False),
)


def run() -> int:
    metrics = defaultdict(lambda: {"detected": 0, "missed": 0, "false_alarms": 0})
    for case in CASES:
        detected = case.category in {
            detection.category for detection in analyze_text(case.text).detections
        }
        if case.should_detect:
            metrics[case.category]["detected" if detected else "missed"] += 1
        elif detected:
            metrics[case.category]["false_alarms"] += 1

    print(f"CopyPasteBin detection benchmark — ruleset {RULESET_VERSION}")
    print("category                         detected  missed  false_alarms")
    for category in sorted(metrics, key=lambda item: item.value):
        values = metrics[category]
        print(
            f"{category.value:32}"
            f"{values['detected']:9}"
            f"{values['missed']:8}"
            f"{values['false_alarms']:14}"
        )
    detected_total = sum(values["detected"] for values in metrics.values())
    missed_total = sum(values["missed"] for values in metrics.values())
    false_alarm_total = sum(values["false_alarms"] for values in metrics.values())
    print(
        f"TOTAL{detected_total:36}{missed_total:8}{false_alarm_total:14}"
    )
    return 1 if missed_total or false_alarm_total else 0


if __name__ == "__main__":
    raise SystemExit(run())
