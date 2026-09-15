from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from .collector import collect_all as collect_base
from .config import LeagueConfig, PublicationConfig
from .nflverse import NFLVerseClient
from .rankings import RankingsClient
from .review import build_editorial_review, render_editorial_review
from .sleeper import SleeperClient


def collect_all(
    leagues: list[LeagueConfig],
    week: int,
    output_root: Path,
    client: SleeperClient | None = None,
    publications: dict[str, PublicationConfig] | None = None,
    rankings_client: RankingsClient | None = None,
    nflverse_client: NFLVerseClient | None = None,
) -> list[Path]:
    """Run the existing collector, then enrich publication dossiers for review."""
    sleeper = client or SleeperClient()
    nflverse = nflverse_client or NFLVerseClient()
    generated = collect_base(
        leagues,
        week,
        output_root,
        client=sleeper,
        publications=publications,
        rankings_client=rankings_client,
        nflverse_client=nflverse,
    )

    snapshot_paths = {
        path.parent.name: path
        for path in generated
        if path.name == "snapshot.json" and path.exists()
    }
    publication_configs = [league for league in leagues if league.publication_enabled]
    if not publication_configs or not snapshot_paths:
        return generated

    first_snapshot = json.loads(next(iter(snapshot_paths.values())).read_text(encoding="utf-8"))
    season = str(
        (first_snapshot.get("nfl_state") or {}).get("season")
        or (first_snapshot.get("league") or {}).get("season")
        or "unknown"
    )
    shared = _collect_deep_nfl_context(nflverse, season, week)
    player_directory = sleeper.players()

    for config in publication_configs:
        snapshot_path = snapshot_paths.get(config.key)
        if snapshot_path is None:
            continue
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        _apply_player_context(snapshot, player_directory)
        _apply_context_scope(snapshot, shared, include_deep=config.tier == "flagship")
        _write_json(snapshot_path, snapshot)

        dossier = build_editorial_review(snapshot)
        directory = snapshot_path.parent
        _write_json(directory / "dossier.json", dossier)
        (directory / "dossier.md").write_text(
            render_editorial_review(dossier), encoding="utf-8"
        )

    return generated


def _collect_deep_nfl_context(
    client: NFLVerseClient, season: str, week: int
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for name, fetcher in (
        ("player_stats", client.player_stats),
        ("snap_counts", client.snap_counts),
        ("play_by_play", client.play_by_play),
    ):
        try:
            records = fetcher(season, week)
            if not isinstance(records, list):
                raise ValueError("NFL context response was not a list")
            sources[name] = {"status": "available", "records": records}
        except (requests.RequestException, ValueError, KeyError, OSError) as exc:
            sources[name] = {
                "status": "unavailable",
                "records": [],
                "error": str(exc),
            }
    return sources


def _apply_player_context(
    snapshot: dict[str, Any], player_directory: dict[str, Any]
) -> None:
    """Retain the rookie marker needed by every publication tier."""
    for player_id, player in (snapshot.get("players") or {}).items():
        source = player_directory.get(str(player_id)) or {}
        player["years_exp"] = source.get("years_exp")


def _apply_context_scope(
    snapshot: dict[str, Any],
    shared: dict[str, Any],
    *,
    include_deep: bool,
) -> None:
    context = snapshot.setdefault("nfl_context", {})
    # Complete weekly player stats are intentionally retained for every
    # publication so Free Agent of the Week can consider genuinely unrostered
    # players rather than only players already present in the league snapshot.
    context["player_stats"] = dict(shared.get("player_stats") or {})
    if include_deep:
        context["snap_counts"] = dict(shared.get("snap_counts") or {})
        context["play_by_play"] = dict(shared.get("play_by_play") or {})
    else:
        context["snap_counts"] = {"status": "not_collected", "records": []}
        context["play_by_play"] = {"status": "not_collected", "records": []}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
