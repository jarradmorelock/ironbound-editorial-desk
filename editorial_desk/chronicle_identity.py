from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Iterable


class IdentityError(ValueError):
    """Raised when stable identity cannot be resolved safely."""


class IdentityAmbiguityError(IdentityError):
    pass


def _stable_key(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


@dataclass(frozen=True)
class AliasRecord:
    season: str
    name: str


@dataclass(frozen=True)
class ManagerTenure:
    season: str
    owner_id: str
    manager_key: str


@dataclass(frozen=True)
class IdentityOverride:
    league_key: str
    season: str
    roster_id: int
    franchise_key: str
    reason: str


@dataclass(frozen=True)
class IdentityAmbiguity:
    league_key: str
    season: str
    roster_id: int
    owner_id: str
    candidate_franchise_keys: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DynastySeasonMapping:
    league_key: str
    season: str
    roster_id: int
    owner_id: str
    franchise_key: str


@dataclass(frozen=True)
class RedraftSeasonMapping:
    league_key: str
    season: str
    roster_id: int
    owner_id: str
    manager_key: str


@dataclass(frozen=True)
class IdentityBootstrapResult:
    mappings: tuple[DynastySeasonMapping, ...]
    ambiguities: tuple[IdentityAmbiguity, ...]


class IdentityRegistry:
    def __init__(self) -> None:
        self._dynasty: dict[tuple[str, str, int], DynastySeasonMapping] = {}
        self._redraft: dict[tuple[str, str, int], RedraftSeasonMapping] = {}
        self._aliases: dict[str, list[AliasRecord]] = {}
        self._manager_aliases: dict[str, list[AliasRecord]] = {}
        self._tenures: dict[str, list[ManagerTenure]] = {}
        self._overrides: dict[tuple[str, str, int], IdentityOverride] = {}
        self._ambiguities: dict[tuple[str, str, int], IdentityAmbiguity] = {}

    @classmethod
    def empty(cls) -> "IdentityRegistry":
        return cls()

    def apply_override(self, override: IdentityOverride) -> None:
        key = (override.league_key, str(override.season), int(override.roster_id))
        self._overrides[key] = override
        self._ambiguities.pop(key, None)

    def register_dynasty_season(
        self,
        *,
        league_key: str,
        season: str,
        roster_id: int,
        owner_id: str,
        team_name: str | None = None,
        manager_name: str | None = None,
    ) -> DynastySeasonMapping:
        season = str(season)
        roster_id = int(roster_id)
        owner_id = str(owner_id or "")
        key = (league_key, season, roster_id)
        existing = self._dynasty.get(key)
        if existing is not None:
            self._record_dynasty_metadata(existing, team_name, manager_name)
            return existing

        override = self._overrides.get(key)
        if override is not None:
            franchise_key = override.franchise_key
        else:
            resolution = self._resolve_dynasty_candidate(
                league_key=league_key,
                season=season,
                roster_id=roster_id,
                owner_id=owner_id,
            )
            if isinstance(resolution, IdentityAmbiguity):
                self._ambiguities[key] = resolution
                raise IdentityAmbiguityError(resolution.reason)
            franchise_key = resolution or _stable_key(
                "franchise", league_key, season, roster_id
            )

        mapping = DynastySeasonMapping(
            league_key=league_key,
            season=season,
            roster_id=roster_id,
            owner_id=owner_id,
            franchise_key=franchise_key,
        )
        self._dynasty[key] = mapping
        self._ambiguities.pop(key, None)
        self._record_dynasty_metadata(mapping, team_name, manager_name)
        return mapping

    def bootstrap_dynasty_season(
        self,
        *,
        league_key: str,
        season: str,
        rosters: Iterable[dict[str, Any]],
    ) -> IdentityBootstrapResult:
        season = str(season)
        proposed: list[tuple[dict[str, Any], str | None]] = []
        ambiguities: list[IdentityAmbiguity] = []
        rows = list(rosters)

        for row in rows:
            roster_id = int(row["roster_id"])
            owner_id = str(row.get("owner_id") or "")
            key = (league_key, season, roster_id)
            override = self._overrides.get(key)
            if override is not None:
                proposed.append((row, override.franchise_key))
                continue
            resolution = self._resolve_dynasty_candidate(
                league_key=league_key,
                season=season,
                roster_id=roster_id,
                owner_id=owner_id,
            )
            if isinstance(resolution, IdentityAmbiguity):
                ambiguities.append(resolution)
            else:
                proposed.append((row, resolution))

        if ambiguities:
            for ambiguity in ambiguities:
                self._ambiguities[
                    (ambiguity.league_key, ambiguity.season, ambiguity.roster_id)
                ] = ambiguity
            return IdentityBootstrapResult((), tuple(ambiguities))

        mappings: list[DynastySeasonMapping] = []
        for row, candidate in proposed:
            roster_id = int(row["roster_id"])
            owner_id = str(row.get("owner_id") or "")
            mapping = DynastySeasonMapping(
                league_key=league_key,
                season=season,
                roster_id=roster_id,
                owner_id=owner_id,
                franchise_key=candidate
                or _stable_key("franchise", league_key, season, roster_id),
            )
            self._dynasty[(league_key, season, roster_id)] = mapping
            self._record_dynasty_metadata(
                mapping, row.get("team_name"), row.get("manager_name")
            )
            self._ambiguities.pop((league_key, season, roster_id), None)
            mappings.append(mapping)
        return IdentityBootstrapResult(tuple(mappings), ())

    def register_redraft_season(
        self,
        *,
        league_key: str,
        season: str,
        roster_id: int,
        owner_id: str,
        team_name: str | None = None,
        manager_name: str | None = None,
    ) -> RedraftSeasonMapping:
        season = str(season)
        roster_id = int(roster_id)
        owner_id = str(owner_id or "")
        if owner_id:
            manager_key = _stable_key("manager", league_key, owner_id)
        else:
            # An orphan slot is not a person. Keep it distinct instead of
            # collapsing all ownerless rosters into one fictional manager.
            manager_key = _stable_key("manager", league_key, "orphan", season, roster_id)
        mapping = RedraftSeasonMapping(
            league_key=league_key,
            season=season,
            roster_id=roster_id,
            owner_id=owner_id,
            manager_key=manager_key,
        )
        self._redraft[(league_key, season, roster_id)] = mapping
        alias = manager_name or team_name
        if alias:
            self._append_alias(
                self._manager_aliases, manager_key, season, str(alias)
            )
        return mapping

    def bootstrap_redraft_season(
        self,
        *,
        league_key: str,
        season: str,
        rosters: Iterable[dict[str, Any]],
    ) -> tuple[RedraftSeasonMapping, ...]:
        return tuple(
            self.register_redraft_season(
                league_key=league_key,
                season=str(season),
                roster_id=int(row["roster_id"]),
                owner_id=str(row.get("owner_id") or ""),
                team_name=row.get("team_name"),
                manager_name=row.get("manager_name"),
            )
            for row in rosters
        )

    def franchise_for(self, league_key: str, season: str, roster_id: int) -> str:
        mapping = self._dynasty.get((league_key, str(season), int(roster_id)))
        if mapping is None:
            raise IdentityError(
                f"No dynasty franchise mapping for {league_key} {season} roster {roster_id}"
            )
        return mapping.franchise_key

    def competitor_for(self, league_key: str, season: str, roster_id: int) -> str:
        key = (league_key, str(season), int(roster_id))
        dynasty = self._dynasty.get(key)
        if dynasty is not None:
            return dynasty.franchise_key
        redraft = self._redraft.get(key)
        if redraft is not None:
            return redraft.manager_key
        raise IdentityError(
            f"No competitor mapping for {league_key} {season} roster {roster_id}"
        )

    def manager_for(self, league_key: str, season: str, owner_id: str) -> str:
        owner_id = str(owner_id or "")
        if owner_id:
            for mapping in self._redraft.values():
                if (
                    mapping.league_key == league_key
                    and mapping.season == str(season)
                    and mapping.owner_id == owner_id
                ):
                    return mapping.manager_key
            for mapping in self._dynasty.values():
                if (
                    mapping.league_key == league_key
                    and mapping.season == str(season)
                    and mapping.owner_id == owner_id
                ):
                    return _stable_key("manager", league_key, owner_id)
        raise IdentityError(
            f"No manager mapping for {league_key} {season} owner {owner_id}"
        )

    def aliases(self, identity_key: str) -> list[AliasRecord]:
        return list(
            self._aliases.get(identity_key)
            or self._manager_aliases.get(identity_key)
            or []
        )

    def manager_tenures(self, franchise_key: str) -> list[ManagerTenure]:
        return list(self._tenures.get(franchise_key, []))

    def league_keys(self) -> tuple[str, ...]:
        keys = {mapping.league_key for mapping in self._dynasty.values()}
        keys.update(mapping.league_key for mapping in self._redraft.values())
        keys.update(row.league_key for row in self._ambiguities.values())
        return tuple(sorted(keys))

    def unresolved_for_league(self, league_key: str) -> tuple[IdentityAmbiguity, ...]:
        return tuple(
            row for row in self.unresolved_ambiguities() if row.league_key == league_key
        )

    def unresolved_ambiguities(self) -> tuple[IdentityAmbiguity, ...]:
        return tuple(self._ambiguities[key] for key in sorted(self._ambiguities))

    def to_dict(self) -> dict[str, Any]:
        return {
            "dynasty_mappings": [
                asdict(self._dynasty[key]) for key in sorted(self._dynasty)
            ],
            "redraft_mappings": [
                asdict(self._redraft[key]) for key in sorted(self._redraft)
            ],
            "aliases": {
                key: [asdict(row) for row in rows]
                for key, rows in sorted(self._aliases.items())
            },
            "manager_aliases": {
                key: [asdict(row) for row in rows]
                for key, rows in sorted(self._manager_aliases.items())
            },
            "manager_tenures": {
                key: [asdict(row) for row in rows]
                for key, rows in sorted(self._tenures.items())
            },
            "overrides": [
                asdict(self._overrides[key]) for key in sorted(self._overrides)
            ],
            "ambiguities": [
                asdict(self._ambiguities[key]) for key in sorted(self._ambiguities)
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "IdentityRegistry":
        registry = cls.empty()
        for row in value.get("dynasty_mappings") or []:
            mapping = DynastySeasonMapping(**row)
            registry._dynasty[
                (mapping.league_key, mapping.season, mapping.roster_id)
            ] = mapping
        for row in value.get("redraft_mappings") or []:
            mapping = RedraftSeasonMapping(**row)
            registry._redraft[
                (mapping.league_key, mapping.season, mapping.roster_id)
            ] = mapping
        registry._aliases = {
            key: [AliasRecord(**row) for row in rows]
            for key, rows in (value.get("aliases") or {}).items()
        }
        registry._manager_aliases = {
            key: [AliasRecord(**row) for row in rows]
            for key, rows in (value.get("manager_aliases") or {}).items()
        }
        registry._tenures = {
            key: [ManagerTenure(**row) for row in rows]
            for key, rows in (value.get("manager_tenures") or {}).items()
        }
        for row in value.get("overrides") or []:
            override = IdentityOverride(**row)
            registry._overrides[
                (override.league_key, override.season, override.roster_id)
            ] = override
        for row in value.get("ambiguities") or []:
            normalized = dict(row)
            normalized["candidate_franchise_keys"] = tuple(
                normalized.get("candidate_franchise_keys") or []
            )
            ambiguity = IdentityAmbiguity(**normalized)
            registry._ambiguities[
                (ambiguity.league_key, ambiguity.season, ambiguity.roster_id)
            ] = ambiguity
        return registry

    def _resolve_dynasty_candidate(
        self,
        *,
        league_key: str,
        season: str,
        roster_id: int,
        owner_id: str,
    ) -> str | IdentityAmbiguity | None:
        previous_season = self._latest_prior_dynasty_season(league_key, season)
        if previous_season is None:
            return None
        previous = [
            mapping
            for mapping in self._dynasty.values()
            if mapping.league_key == league_key and mapping.season == previous_season
        ]
        roster_match = next((m for m in previous if m.roster_id == roster_id), None)
        owner_match = (
            next((m for m in previous if owner_id and m.owner_id == owner_id), None)
            if owner_id
            else None
        )
        candidates = {
            mapping.franchise_key
            for mapping in (roster_match, owner_match)
            if mapping is not None
        }
        if roster_match is not None and roster_match.owner_id != owner_id:
            return IdentityAmbiguity(
                league_key=league_key,
                season=season,
                roster_id=roster_id,
                owner_id=owner_id,
                candidate_franchise_keys=tuple(
                    sorted(candidates or {roster_match.franchise_key})
                ),
                reason=(
                    "Dynasty ownership changed on a known roster slot; explicit "
                    "continuity confirmation is required"
                ),
            )
        if len(candidates) > 1:
            return IdentityAmbiguity(
                league_key=league_key,
                season=season,
                roster_id=roster_id,
                owner_id=owner_id,
                candidate_franchise_keys=tuple(sorted(candidates)),
                reason=(
                    "Roster-slot and owner continuity point to different dynasty "
                    "franchises"
                ),
            )
        if owner_match is not None:
            return owner_match.franchise_key
        if roster_match is not None:
            return roster_match.franchise_key
        return None

    def _latest_prior_dynasty_season(
        self, league_key: str, season: str
    ) -> str | None:
        seasons = sorted(
            {
                mapping.season
                for mapping in self._dynasty.values()
                if mapping.league_key == league_key and mapping.season < season
            }
        )
        return seasons[-1] if seasons else None

    def _record_dynasty_metadata(
        self,
        mapping: DynastySeasonMapping,
        team_name: str | None,
        manager_name: str | None,
    ) -> None:
        if team_name:
            self._append_alias(
                self._aliases, mapping.franchise_key, mapping.season, str(team_name)
            )
        manager_key = _stable_key("manager", mapping.league_key, mapping.owner_id)
        tenure = ManagerTenure(
            season=mapping.season,
            owner_id=mapping.owner_id,
            manager_key=manager_key,
        )
        rows = self._tenures.setdefault(mapping.franchise_key, [])
        if tenure not in rows:
            rows.append(tenure)
            rows.sort(key=lambda row: (row.season, row.owner_id, row.manager_key))
        if manager_name:
            self._append_alias(
                self._manager_aliases,
                manager_key,
                mapping.season,
                str(manager_name),
            )

    @staticmethod
    def _append_alias(
        bucket: dict[str, list[AliasRecord]],
        identity_key: str,
        season: str,
        name: str,
    ) -> None:
        alias = AliasRecord(str(season), str(name))
        rows = bucket.setdefault(identity_key, [])
        if alias not in rows:
            rows.append(alias)
            rows.sort(key=lambda row: (row.season, row.name))
