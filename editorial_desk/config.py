from __future__ import annotations

from dataclasses import dataclass, field
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
class FeatureDependencyConfig:
    source: str
    strength: str


@dataclass(frozen=True)
class FeatureContractConfig:
    feature: str
    display_name: str
    required_in_phase: bool
    dependencies: tuple[FeatureDependencyConfig, ...] = ()


@dataclass(frozen=True)
class PublicationConfig:
    key: str
    name: str
    tier: str
    source_files: tuple[str, ...]
    recurring_sections: tuple[str, ...]
    brand_departments: tuple[str, ...]
    editorial_priorities: tuple[str, ...]
    story_desk: bool = False
    feature_contracts: dict[str, tuple[FeatureContractConfig, ...]] = field(
        default_factory=dict
    )

    def contracts_for(self, phase: str) -> tuple[FeatureContractConfig, ...]:
        return self.feature_contracts.get(str(phase), ())


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

        def required(field_name: str) -> str:
            value = str(raw.get(field_name) or "").strip()
            if not value:
                raise ConfigurationError(
                    f"publications[{index}].{field_name} is required"
                )
            return value

        key = required("key")
        name = required("name")
        tier = required("tier").lower()
        if key in profiles:
            raise ConfigurationError(f"Duplicate publication key: {key}")
        if not key.replace("_", "").isalnum():
            raise ConfigurationError(
                f"{name}: key must use letters, numbers, and underscores"
            )
        if tier not in {"flagship", "newspaper"}:
            raise ConfigurationError(f"{name}: tier must be flagship or newspaper")

        story_desk = raw.get("story_desk", False)
        if not isinstance(story_desk, bool):
            raise ConfigurationError(f"{name}: story_desk must be true or false")

        profiles[key] = PublicationConfig(
            key=key,
            name=name,
            tier=tier,
            source_files=_string_tuple(raw, "source_files", index),
            recurring_sections=_string_tuple(raw, "recurring_sections", index),
            brand_departments=_string_tuple(raw, "brand_departments", index),
            editorial_priorities=_string_tuple(raw, "editorial_priorities", index),
            story_desk=story_desk,
            feature_contracts=_feature_contracts(raw, index, name),
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
    def required(field_name: str) -> str:
        value = str(raw.get(field_name) or "").strip()
        if not value:
            raise ConfigurationError(f"leagues[{index}].{field_name} is required")
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


def _string_tuple(raw: dict[str, Any], field_name: str, index: int) -> tuple[str, ...]:
    values = raw.get(field_name) or []
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ConfigurationError(
            f"publications[{index}].{field_name} must be a list of non-empty strings"
        )
    return tuple(value.strip() for value in values)


def _feature_contracts(
    raw: dict[str, Any], index: int, publication_name: str
) -> dict[str, tuple[FeatureContractConfig, ...]]:
    document = raw.get("feature_contracts") or {}
    if not isinstance(document, dict):
        raise ConfigurationError(
            f"{publication_name}: feature_contracts must be an object"
        )
    allowed_phases = {"weekly", "preseason", "offseason"}
    parsed: dict[str, tuple[FeatureContractConfig, ...]] = {}
    for phase, rows in document.items():
        if phase not in allowed_phases:
            raise ConfigurationError(
                f"{publication_name}: unsupported feature-contract phase {phase}"
            )
        if not isinstance(rows, list):
            raise ConfigurationError(
                f"{publication_name}: feature_contracts.{phase} must be a list"
            )
        contracts: list[FeatureContractConfig] = []
        seen: set[str] = set()
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ConfigurationError(
                    f"{publication_name}: {phase}[{row_index}] must be an object"
                )
            feature = str(row.get("feature") or "").strip()
            display_name = str(row.get("display_name") or "").strip()
            if not feature:
                raise ConfigurationError(
                    f"{publication_name}: {phase}[{row_index}].feature is required"
                )
            if not display_name:
                raise ConfigurationError(
                    f"{publication_name}: {phase}[{row_index}].display_name is required"
                )
            if feature in seen:
                raise ConfigurationError(
                    f"{publication_name}: Duplicate feature {feature} in phase {phase}"
                )
            seen.add(feature)
            required_in_phase = row.get("required_in_phase", True)
            if not isinstance(required_in_phase, bool):
                raise ConfigurationError(
                    f"{publication_name}: {phase}[{row_index}].required_in_phase "
                    "must be true or false"
                )
            dependencies_raw = row.get("dependencies") or []
            if not isinstance(dependencies_raw, list):
                raise ConfigurationError(
                    f"{publication_name}: {phase}[{row_index}].dependencies must be a list"
                )
            dependencies: list[FeatureDependencyConfig] = []
            for dependency_index, dependency in enumerate(dependencies_raw):
                if not isinstance(dependency, dict):
                    raise ConfigurationError(
                        f"{publication_name}: {phase}[{row_index}].dependencies"
                        f"[{dependency_index}] must be an object"
                    )
                source = str(dependency.get("source") or "").strip()
                strength = str(dependency.get("strength") or "").strip().lower()
                if not source:
                    raise ConfigurationError(
                        f"{publication_name}: dependency source is required"
                    )
                if strength not in {"required", "preferred", "optional"}:
                    raise ConfigurationError(
                        f"{publication_name}: dependency strength must be required, "
                        "preferred, or optional"
                    )
                dependencies.append(
                    FeatureDependencyConfig(source=source, strength=strength)
                )
            contracts.append(
                FeatureContractConfig(
                    feature=feature,
                    display_name=display_name,
                    required_in_phase=required_in_phase,
                    dependencies=tuple(dependencies),
                )
            )
        parsed[phase] = tuple(contracts)
    return parsed
