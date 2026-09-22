from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any


class ExternalInputError(ValueError):
    """Raised when a manually supplied editorial-input packet is invalid."""


@dataclass(frozen=True)
class OfficialPowerRanking:
    franchise_key: str | None
    rank: int
    roster_id: int | None = None
    team: str | None = None
    previous_rank: int | None = None
    movement: int | None = None
    score: float | None = None


@dataclass(frozen=True)
class ExternalEditorialInputs:
    publication_key: str
    official_power_rankings: tuple[OfficialPowerRanking, ...] = ()
    war: tuple[dict[str, Any], ...] = ()
    cwar: tuple[dict[str, Any], ...] = ()
    usage: tuple[dict[str, Any], ...] = ()
    playoff_odds: tuple[dict[str, Any], ...] = ()
    publication_assets: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    source_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def power_rankings_supplied(self) -> bool:
        return bool(self.official_power_rankings)

    @property
    def war_supplied(self) -> bool:
        return bool(self.war)

    @property
    def cwar_supplied(self) -> bool:
        return bool(self.cwar)

    @property
    def usage_supplied(self) -> bool:
        return bool(self.usage)

    @property
    def playoff_odds_supplied(self) -> bool:
        return bool(self.playoff_odds)

    def ranking_for(self, franchise_key: str) -> int | None:
        wanted = str(franchise_key)
        for row in self.official_power_rankings:
            if row.franchise_key == wanted:
                return row.rank
        return None

    def ranking_for_roster(
        self,
        roster_id: int,
        *,
        franchise_key: str | None = None,
        team: str | None = None,
    ) -> OfficialPowerRanking | None:
        wanted_roster = int(roster_id)
        wanted_franchise = str(franchise_key or "").strip()
        wanted_team = str(team or "").strip().casefold()
        for row in self.official_power_rankings:
            if row.roster_id is not None and int(row.roster_id) == wanted_roster:
                return row
        if wanted_franchise:
            for row in self.official_power_rankings:
                if str(row.franchise_key or "") == wanted_franchise:
                    return row
        if wanted_team:
            for row in self.official_power_rankings:
                if str(row.team or "").strip().casefold() == wanted_team:
                    return row
        return None


def load_external_inputs(
    path: Path | None, publication_key: str
) -> ExternalEditorialInputs:
    publication_key = str(publication_key).strip()
    if not publication_key:
        raise ExternalInputError("publication_key is required")
    if path is None:
        return ExternalEditorialInputs(publication_key=publication_key)

    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExternalInputError(f"External input file not found: {source_path}") from exc
    except json.JSONDecodeError as exc:
        raise ExternalInputError(
            f"Invalid JSON in external input file {source_path}: {exc.msg}"
        ) from exc

    if not isinstance(raw, dict):
        raise ExternalInputError("External editorial input must be a JSON object")
    supplied_key = str(raw.get("publication_key") or "").strip()
    if supplied_key != publication_key:
        raise ExternalInputError(
            f"External input publication_key {supplied_key!r} does not match "
            f"requested {publication_key!r}"
        )

    rankings_raw = raw.get("official_power_rankings") or []
    if not isinstance(rankings_raw, list):
        raise ExternalInputError("official_power_rankings must be a list")
    rankings: list[OfficialPowerRanking] = []
    seen_ranks: set[int] = set()
    seen_franchises: set[str] = set()
    for index, row in enumerate(rankings_raw):
        if not isinstance(row, dict):
            raise ExternalInputError(
                f"official_power_rankings[{index}] must be an object"
            )
        franchise_key = str(row.get("franchise_key") or "").strip() or None
        roster_id_raw = row.get("roster_id")
        roster_id = None
        if roster_id_raw is not None:
            if isinstance(roster_id_raw, bool):
                raise ExternalInputError("roster_id must be a positive integer")
            try:
                roster_id = int(roster_id_raw)
            except (TypeError, ValueError) as exc:
                raise ExternalInputError("roster_id must be a positive integer") from exc
            if roster_id <= 0:
                raise ExternalInputError("roster_id must be a positive integer")
        team = str(row.get("team") or "").strip() or None
        if not franchise_key and roster_id is None and not team:
            raise ExternalInputError(
                f"official_power_rankings[{index}] requires franchise_key, roster_id, or team"
            )
        rank = row.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
            raise ExternalInputError("Official rank must be a positive integer")
        if rank in seen_ranks:
            raise ExternalInputError(f"Duplicate official rank: {rank}")
        if franchise_key and franchise_key in seen_franchises:
            raise ExternalInputError(f"Duplicate franchise_key: {franchise_key}")
        seen_ranks.add(rank)
        if franchise_key:
            seen_franchises.add(franchise_key)
        rankings.append(
            OfficialPowerRanking(
                franchise_key=franchise_key,
                rank=rank,
                roster_id=roster_id,
                team=team,
                previous_rank=_optional_int(row.get("previous_rank")),
                movement=_optional_int(row.get("movement")),
                score=_optional_float(row.get("score")),
            )
        )

    war_raw = raw.get("war") or []
    if not isinstance(war_raw, list) or any(not isinstance(row, dict) for row in war_raw):
        raise ExternalInputError("war must be a list of objects")
    cwar_raw = raw.get("cwar") or []
    if not isinstance(cwar_raw, list) or any(not isinstance(row, dict) for row in cwar_raw):
        raise ExternalInputError("cwar must be a list of objects")
    usage_raw = raw.get("usage") or []
    if not isinstance(usage_raw, list) or any(not isinstance(row, dict) for row in usage_raw):
        raise ExternalInputError("usage must be a list of objects")
    playoff_odds_raw = raw.get("playoff_odds") or []
    if not isinstance(playoff_odds_raw, list) or any(not isinstance(row, dict) for row in playoff_odds_raw):
        raise ExternalInputError("playoff_odds must be a list of objects")
    assets_raw = raw.get("publication_assets") or {}
    if not isinstance(assets_raw, dict):
        raise ExternalInputError("publication_assets must be an object")
    publication_assets: dict[str, dict[str, Any]] = {}
    for key, row in assets_raw.items():
        if not isinstance(row, dict):
            raise ExternalInputError(f"publication_assets.{key} must be an object")
        filename = str(row.get("filename") or "").strip()
        if not filename or Path(filename).name != filename:
            raise ExternalInputError(
                f"publication_assets.{key}.filename must be a basename"
            )
        media_type = str(row.get("media_type") or "").strip()
        if media_type != "image/png":
            raise ExternalInputError(
                f"publication_assets.{key}.media_type must be image/png"
            )
        local_path = source_path.parent / "assets" / filename
        available = local_path.is_file()
        expected_sha = str(row.get("sha256") or "").strip().lower()
        actual_sha = None
        if available:
            actual_sha = hashlib.sha256(local_path.read_bytes()).hexdigest()
            if expected_sha and expected_sha != actual_sha:
                raise ExternalInputError(
                    f"publication asset checksum mismatch for {filename}"
                )
        publication_assets[str(key)] = {
            **dict(row),
            "filename": filename,
            "media_type": media_type,
            "local_path": str(local_path),
            "available": available,
            "actual_sha256": actual_sha,
        }

    notes_raw = raw.get("notes") or []
    if not isinstance(notes_raw, list) or any(not isinstance(note, str) for note in notes_raw):
        raise ExternalInputError("notes must be a list of strings")
    source_metadata = raw.get("source_metadata") or {}
    if not isinstance(source_metadata, dict):
        raise ExternalInputError("source_metadata must be an object")

    return ExternalEditorialInputs(
        publication_key=publication_key,
        official_power_rankings=tuple(rankings),
        war=tuple(dict(row) for row in war_raw),
        cwar=tuple(dict(row) for row in cwar_raw),
        usage=tuple(dict(row) for row in usage_raw),
        playoff_odds=tuple(dict(row) for row in playoff_odds_raw),
        publication_assets=publication_assets,
        notes=tuple(str(note) for note in notes_raw),
        source_metadata=dict(source_metadata),
    )



def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
