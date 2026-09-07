from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    """Raised when a league configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class LeagueConfig:
    key: str
    name: str
    sleeper_league_id: str
    publication: str
    tier: str


def load_leagues(path: Path) -> list[LeagueConfig]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in {path}: {exc.msg}") from exc

    raw_leagues = document.get("leagues") if isinstance(document, dict) else None
    if not isinstance(raw_leagues, list) or not raw_leagues:
        raise ConfigurationError("Configuration must contain a non-empty leagues list")

    leagues: list[LeagueConfig] = []
    keys: set[str] = set()
    ids: set[str] = set()
    for index, raw in enumerate(raw_leagues):
        if not isinstance(raw, dict):
            raise ConfigurationError(f"leagues[{index}] must be an object")
        if raw.get("enabled", True) is False:
            continue
        league = _parse_league(raw, index)
        if league.key in keys:
            raise ConfigurationError(f"Duplicate league key: {league.key}")
        if league.sleeper_league_id in ids:
            raise ConfigurationError(
                f"Duplicate Sleeper league ID: {league.sleeper_league_id}"
            )
        keys.add(league.key)
        ids.add(league.sleeper_league_id)
        leagues.append(league)

    if not leagues:
        raise ConfigurationError("Configuration has no enabled leagues")
    return leagues


def _parse_league(raw: dict[str, Any], index: int) -> LeagueConfig:
    def required(field: str) -> str:
        value = str(raw.get(field) or "").strip()
        if not value:
            raise ConfigurationError(f"leagues[{index}].{field} is required")
        return value

    key = required("key")
    name = required("name")
    league_id = required("sleeper_league_id")
    publication = required("publication")
    tier = required("tier").lower()

    if not key.replace("_", "").isalnum():
        raise ConfigurationError(f"{name}: key must use letters, numbers, and underscores")
    if not league_id.isdigit():
        raise ConfigurationError(f"{name}: sleeper_league_id must be numeric")
    if tier not in {"flagship", "newspaper"}:
        raise ConfigurationError(f"{name}: tier must be flagship or newspaper")

    return LeagueConfig(key, name, league_id, publication, tier)
