from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import requests

from .config import LeagueConfig, PublicationConfig
from .metrics import build_weekly_dossier
from .rankings import RankingsClient
from .render import render_markdown
from .sleeper import SleeperClient


def collect_all(
    leagues: list[LeagueConfig],
    week: int,
    output_root: Path,
    client: SleeperClient | None = None,
    publications: dict[str, PublicationConfig] | None = None,
    rankings_client: RankingsClient | None = None,
) -> list[Path]:
    client = client or SleeperClient()
    rankings_client = rankings_client or RankingsClient()
    state = client.nfl_state()
    player_directory = client.players()
    season = str(state.get("season") or "unknown")
    ranking_sources = _collect_ranking_sources(
        rankings_client,
        client,
        season,
        week,
    )
    generated: list[Path] = []

    for league_config in leagues:
        snapshot = collect_league(
            league_config,
            week,
            state,
            player_directory,
            client,
            (publications or {}).get(league_config.publication_profile),
            ranking_sources,
        )
        directory = output_root / season / f"week-{week:02d}" / league_config.key
        directory.mkdir(parents=True, exist_ok=True)

        snapshot_path = directory / "snapshot.json"
        dossier_path = directory / "dossier.json"
        markdown_path = directory / "dossier.md"
        dossier = build_weekly_dossier(snapshot)

        _write_json(snapshot_path, snapshot)
        _write_json(dossier_path, dossier)
        markdown_path.write_text(render_markdown(dossier), encoding="utf-8")
        generated.extend((snapshot_path, dossier_path, markdown_path))

    return generated


def collect_league(
    config: LeagueConfig,
    week: int,
    state: dict[str, Any],
    player_directory: dict[str, Any],
    client: SleeperClient,
    publication: PublicationConfig | None = None,
    ranking_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    league = client.league(config.sleeper_league_id)
    users = client.users(config.sleeper_league_id)
    rosters = client.rosters(config.sleeper_league_id)
    matchups = client.matchups(config.sleeper_league_id, week)
    transactions = client.transactions(config.sleeper_league_id, week)
    traded_picks = client.traded_picks(config.sleeper_league_id)

    rostered_ids = {
        str(player_id)
        for matchup in matchups
        for player_id in (matchup.get("players") or [])
    }
    for transaction in transactions:
        rostered_ids.update(
            str(player_id) for player_id in (transaction.get("adds") or {})
        )
        rostered_ids.update(
            str(player_id) for player_id in (transaction.get("drops") or {})
        )
    for roster in rosters:
        rostered_ids.update(
            str(player_id) for player_id in (roster.get("players") or [])
        )
    players = {
        player_id: _trim_player(player_directory.get(player_id) or {})
        for player_id in sorted(rostered_ids)
    }

    return {
        "schema_version": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "week": week,
        "nfl_state": state,
        "editorial": {
            "league_key": config.key,
            "configured_name": config.name,
            "publication": config.publication,
            "publication_profile": {
                "key": publication.key,
                "recurring_sections": list(publication.recurring_sections),
                "brand_departments": list(publication.brand_departments),
                "editorial_priorities": list(publication.editorial_priorities),
            }
            if publication
            else {"key": config.publication_profile},
            "tier": config.tier,
            "league_format": config.league_format,
            "ranking_model": config.ranking_model,
        },
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups": matchups,
        "transactions": transactions,
        "traded_picks": traded_picks,
        "players": players,
        "ranking_inputs": _trim_ranking_sources(
            ranking_sources or {},
            rostered_ids,
        ),
    }


def _collect_ranking_sources(
    rankings_client: RankingsClient,
    sleeper_client: SleeperClient,
    season: str,
    week: int,
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    try:
        rows = rankings_client.dynasty_daddy_player_values()
        sources["dynasty_daddy"] = {
            "status": "available",
            "players": {
                str(row["sleeper_id"]): row
                for row in rows
                if row.get("sleeper_id") is not None
            },
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
        sources["dynasty_daddy"] = {
            "status": "unavailable",
            "error": str(exc),
            "players": {},
        }

    try:
        sources["sleeper_projections"] = {
            "status": "available",
            "season": season,
            "week": week,
            "players": sleeper_client.projections(season, week),
        }
    except (requests.RequestException, ValueError) as exc:
        sources["sleeper_projections"] = {
            "status": "unavailable",
            "season": season,
            "week": week,
            "error": str(exc),
            "players": {},
        }
    return sources


def _trim_ranking_sources(
    sources: dict[str, Any], player_ids: set[str]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source_name, source in sources.items():
        players = source.get("players") or {}
        trimmed = {
            player_id: _trim_ranking_player(source_name, players.get(player_id) or {})
            for player_id in sorted(player_ids)
            if player_id in players
        }
        result[source_name] = {
            key: value for key, value in source.items() if key != "players"
        }
        result[source_name]["players"] = trimmed
    return result


def _trim_ranking_player(source_name: str, player: dict[str, Any]) -> dict[str, Any]:
    if source_name == "dynasty_daddy":
        fields = (
            "full_name",
            "position",
            "sleeper_id",
            "trade_value",
            "sf_trade_value",
            "overall_rank",
            "sf_overall_rank",
            "avg_adp",
            "avg_ros",
            "injury_status",
            "date",
        )
        return {field: player.get(field) for field in fields}
    return dict(player)


def _trim_player(player: dict[str, Any]) -> dict[str, Any]:
    return {
        key: player.get(key)
        for key in (
            "player_id",
            "full_name",
            "first_name",
            "last_name",
            "position",
            "fantasy_positions",
            "team",
            "status",
            "injury_status",
        )
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
