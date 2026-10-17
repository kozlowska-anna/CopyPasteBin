from __future__ import annotations

from dataclasses import dataclass

from .detection import (
    RULESET_VERSION,
    CustomLiteralExclusion,
    CustomLiteralRule,
    analyze_text,
)
from .history import HistoryStore
from .models import AnalysisResult, Category, RiskLevel


NO_GUARANTEE = "Nie wykryto znanych wzorców. To nie gwarantuje, że tekst jest bezpieczny."


@dataclass(frozen=True, slots=True, repr=False)
class OperationResult:
    operation_id: str
    analysis: AnalysisResult

    def __repr__(self) -> str:
        return f"OperationResult(operation_id={self.operation_id!r}, content_redacted=True)"


def inspect_and_record(text: str, *, source_kind: str, purpose: str, history: HistoryStore, status: str = "warned", custom_rules: tuple[CustomLiteralRule, ...] = (), disabled_categories: frozenset[Category] = frozenset(), custom_exclusions: tuple[CustomLiteralExclusion, ...] = (), source_application: str = "unknown", destination_application: str = "unknown") -> OperationResult:
    analysis = analyze_text(
        text,
        custom_rules,
        disabled_categories,
        custom_exclusions,
    )
    ruleset_version = RULESET_VERSION + (
        "+custom" if custom_rules or custom_exclusions else ""
    )
    operation_id = history.record(text, source_kind, purpose, analysis, status, ruleset_version=ruleset_version, source_application=source_application, destination_application=destination_application)
    return OperationResult(operation_id, analysis)


def requires_high_risk_confirmation(result: AnalysisResult) -> bool:
    return result.highest_risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
