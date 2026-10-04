from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Readiness = Literal["ready", "ready_no_items", "unavailable"]
Strength = Literal["required", "preferred", "optional"]


@dataclass(frozen=True)
class FeatureResult:
    feature: str
    status: Readiness
    data: Any = None
    reason: str | None = None
    freshness: dict[str, str] | None = None
    degraded: bool = False


def ready(
    feature: str,
    data: Any,
    *,
    reason: str | None = None,
    freshness: dict[str, str] | None = None,
    degraded: bool = False,
) -> FeatureResult:
    return FeatureResult(
        feature=feature,
        status="ready",
        data=data,
        reason=reason,
        freshness=freshness,
        degraded=degraded,
    )


def ready_no_items(
    feature: str,
    *,
    reason: str | None = None,
    freshness: dict[str, str] | None = None,
) -> FeatureResult:
    return FeatureResult(
        feature=feature,
        status="ready_no_items",
        data=[],
        reason=reason,
        freshness=freshness,
        degraded=False,
    )


def unavailable(
    feature: str,
    reason: str,
    *,
    freshness: dict[str, str] | None = None,
) -> FeatureResult:
    if not str(reason or "").strip():
        raise ValueError("unavailable feature result requires a reason")
    return FeatureResult(
        feature=feature,
        status="unavailable",
        data=None,
        reason=str(reason).strip(),
        freshness=freshness,
        degraded=False,
    )
