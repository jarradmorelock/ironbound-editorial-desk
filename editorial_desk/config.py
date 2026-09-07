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
    publication: str | None
    publication_profile: str | None
    tier: str
    league_format: str
    ranking_model: str
    publication_enabled: bool


@dataclass(frozen=True)
class PublicationConfig:
    key: str
    name: str
    tier: str
    source_files: tuple[str, ...]
    recurring_sections: tuple[str, ...]
    brand_departments: tuple[str, ...]
    editorial_priorities: tuple[str, ...]


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


def load_publications(path: Path) -> dict[str, PublicationConfig]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(
            f"Publication configuration not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in {path}: {exc.msg}") from exc

    raw_profiles = (
        document.get("publications") if isinstance(document, dict) else None
    )
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ConfigurationError(
            "Publication configuration must contain a non-empty publications list"
        )

    profiles: dict[str, PublicationConfig] = {}
    for index, raw in enumerate(raw_profiles):
        if not isinstance(raw, dict):
            raise ConfigurationError(f"publications[{index}] must be an object")

        def required(field: str) -> str:
            value = str(raw.get(field) or "").strip()
            if not value:
                raise ConfigurationError(f"publications[{index}].{field} is required")
            return value

        key = required("key")
        name = required("name")
        tier = required("tier").lower()
        if key in profiles:
            raise ConfigurationError(f"Duplicate publication key: {key}")
        if not key.replace("_", "").isalnum():
            raise ConfigurationError(f"{name}: key must use letters, numbers, and underscores")
        if tier not in {"flagship", "newspaper"}:
            raise ConfigurationError(f"{name}: tier must be flagship or newspaper")

        profiles[key] = PublicationConfig(
            key=key,
            name=name,
            tier=tier,
            source_files=_string_tuple(raw, "source_files", index),
            recurring_sections=_string_tuple(raw, "recurring_sections", index),
            brand_departments=_string_tuple(raw, "brand_departments", index),
            editorial_priorities=_string_tuple(raw, "editorial_priorities", index),
        )
    return profiles


def validate_publication_mappings(
    leagues: list[LeagueConfig], publications: dict[str, PublicationConfig]
) -> None:
    for league in leagues:
        if not league.publication_enabled:
            continue
        profile = publications.get(league.publication_profile)
        if profile is None:
            raise ConfigurationError(
                f"{league.name}: unknown publication profile {league.publication_profile}"
            )
        if profile.name != league.publication:
            raise ConfigurationError(
                f"{league.name}: publication name does not match profile {profile.name}"
            )
        if profile.tier != league.tier:
            raise ConfigurationError(
                f"{league.name}: publication tier does not match profile {profile.tier}"
            )


def _parse_league(raw: dict[str, Any], index: int) -> LeagueConfig:
    def required(field: str) -> str:
        value = str(raw.get(field) or "").strip()
        if not value:
            raise ConfigurationError(f"leagues[{index}].{field} is required")
        return value

    key = required("key")
    name = required("name")
    league_id = required("sleeper_league_id")
    publication_enabled = raw.get("publication_enabled", True)
    if not isinstance(publication_enabled, bool):
        raise ConfigurationError(
            f"{name}: publication_enabled must be true or false"
        )
    if publication_enabled:
        publication = required("publication")
        publication_profile = str(raw.get("publication_profile") or key).strip()
        tier = required("tier").lower()
    else:
        publication = None
        publication_profile = None
        tier = "data_only"
    league_format = required("league_format").lower()
    ranking_model = required("ranking_model")

    if not key.replace("_", "").isalnum():
        raise ConfigurationError(f"{name}: key must use letters, numbers, and underscores")
    if not league_id.isdigit():
        raise ConfigurationError(f"{name}: sleeper_league_id must be numeric")
    if publication_enabled and tier not in {"flagship", "newspaper"}:
        raise ConfigurationError(f"{name}: tier must be flagship or newspaper")
    if league_format not in {"dynasty", "redraft"}:
        raise ConfigurationError(f"{name}: league_format must be dynasty or redraft")
    allowed_models = {
        "dynasty": "ironbound_dynasty",
        "redraft": "redraft_projection_starters_record",
    }
    if ranking_model != allowed_models[league_format]:
        raise ConfigurationError(
            f"{name}: {league_format} leagues must use "
            f"{allowed_models[league_format]} ranking_model"
        )

    return LeagueConfig(
        key,
        name,
        league_id,
        publication,
        publication_profile,
        tier,
        league_format,
        ranking_model,
        publication_enabled,
    )


def _string_tuple(raw: dict[str, Any], field: str, index: int) -> tuple[str, ...]:
    values = raw.get(field) or []
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ConfigurationError(
            f"publications[{index}].{field} must be a list of non-empty strings"
        )
    return tuple(value.strip() for value in values)
