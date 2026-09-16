from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


class ExternalInputError(ValueError):
    """Raised when a manually supplied editorial-input packet is invalid."""


@dataclass(frozen=True)
class OfficialPowerRanking:
    franchise_key: str
    rank: int


@dataclass(frozen=True)
class ExternalEditorialInputs:
    publication_key: str
    official_power_rankings: tuple[OfficialPowerRanking, ...] = ()
    war: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()
    source_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def power_rankings_supplied(self) -> bool:
        return bool(self.official_power_rankings)

    @property
    def war_supplied(self) -> bool:
        return bool(self.war)

    def ranking_for(self, franchise_key: str) -> int | None:
        wanted = str(franchise_key)
        for row in self.official_power_rankings:
            if row.franchise_key == wanted:
                return row.rank
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
        franchise_key = str(row.get("franchise_key") or "").strip()
        if not franchise_key:
            raise ExternalInputError(
                f"official_power_rankings[{index}].franchise_key is required"
            )
        rank = row.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
            raise ExternalInputError("Official rank must be a positive integer")
        if rank in seen_ranks:
            raise ExternalInputError(f"Duplicate official rank: {rank}")
        if franchise_key in seen_franchises:
            raise ExternalInputError(f"Duplicate franchise_key: {franchise_key}")
        seen_ranks.add(rank)
        seen_franchises.add(franchise_key)
        rankings.append(OfficialPowerRanking(franchise_key=franchise_key, rank=rank))

    war_raw = raw.get("war") or []
    if not isinstance(war_raw, list) or any(not isinstance(row, dict) for row in war_raw):
        raise ExternalInputError("war must be a list of objects")
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
        notes=tuple(str(note) for note in notes_raw),
        source_metadata=dict(source_metadata),
    )
