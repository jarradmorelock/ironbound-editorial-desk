from __future__ import annotations

from typing import Any

from .config import FeatureContractConfig
from .health import build_roster_health


def evaluate_dependencies(
    contract: FeatureContractConfig, snapshot: dict[str, Any]
) -> tuple[str | None, list[str]]:
    """Return a blocking required-source reason and preferred-source warnings."""
    warnings: list[str] = []
    for dependency in contract.dependencies:
        available, reason = dependency_available(snapshot, dependency.source)
        if available:
            continue
        detail = reason or f"{dependency.source} unavailable"
        if dependency.strength == "required":
            return f"Required dependency {dependency.source} unavailable: {detail}", warnings
        if dependency.strength == "preferred":
            warnings.append(f"Preferred dependency {dependency.source} unavailable: {detail}")
    return None, warnings


def dependency_available(
    snapshot: dict[str, Any], source: str
) -> tuple[bool, str | None]:
    if source == "sleeper_health":
        health = build_roster_health(snapshot)
        if health.get("status") == "available":
            return True, None
        return False, str(health.get("error") or "Sleeper health source unavailable")

    # Publication contracts use the semantic name `dynasty_market`; the
    # authoritative collected source is Dynasty Daddy under ranking_inputs.
    if source == "dynasty_market":
        value = (snapshot.get("ranking_inputs") or {}).get("dynasty_daddy")
        return _status_available(value, "dynasty_daddy")

    for container_name in ("ranking_inputs", "nfl_context"):
        container = snapshot.get(container_name) or {}
        if source in container:
            return _status_available(container.get(source), source)

    if source in snapshot:
        return _status_available(snapshot.get(source), source)

    return False, f"{source} was not collected"


def _status_available(value: Any, source: str) -> tuple[bool, str | None]:
    if isinstance(value, dict) and "status" in value:
        if value.get("status") == "available":
            return True, None
        return False, str(
            value.get("reason")
            or value.get("error")
            or f"{source} status is {value.get('status')}"
        )
    if value is None:
        return False, f"{source} is missing"
    return True, None
