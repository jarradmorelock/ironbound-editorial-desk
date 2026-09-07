from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import LeagueConfig
from .metrics import build_weekly_dossier
from .render import render_markdown
from .sleeper import SleeperClient


def collect_all(
    leagues: list[LeagueConfig],
    week: int,
    output_root: Path,
    client: SleeperClient | None = None,
) -> list[Path]:
    client = client or SleeperClient()
    state = client.nfl_state()
    player_directory = client.players()
    season = str(state.get("season") or "unknown")
    generated: list[Path] = []

    for league_config in leagues:
        snapshot = collect_league(
            league_config,
            week,
            state,
            player_directory,
            client,
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
            "tier": config.tier,
        },
        "league": league,
        "users": users,
        "rosters": rosters,
        "matchups": matchups,
        "transactions": transactions,
        "traded_picks": traded_picks,
        "players": players,
    }


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
