from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import requests

from .config import LeagueConfig, PublicationConfig
from .metrics import build_weekly_dossier
from .nflverse import NFLVerseClient
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
    nflverse_client: NFLVerseClient | None = None,
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
    nfl_context = _collect_nfl_week_context(
        nflverse_client or NFLVerseClient(), season, week
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
            nfl_context,
        )
        directory = output_root / season / f"week-{week:02d}" / league_config.key
        directory.mkdir(parents=True, exist_ok=True)

        snapshot_path = directory / "snapshot.json"
        _write_json(snapshot_path, snapshot)
        analysis = build_weekly_dossier(snapshot)
        if league_config.publication_enabled:
            dossier_path = directory / "dossier.json"
            markdown_path = directory / "dossier.md"
            _write_json(dossier_path, analysis)
            markdown_path.write_text(render_markdown(analysis), encoding="utf-8")
            generated.extend((snapshot_path, dossier_path, markdown_path))
        else:
            analysis_path = directory / "analysis.json"
            _write_json(analysis_path, analysis)
            generated.extend((snapshot_path, analysis_path))

    return generated


def collect_league(
    config: LeagueConfig,
    week: int,
    state: dict[str, Any],
    player_directory: dict[str, Any],
    client: SleeperClient,
    publication: PublicationConfig | None = None,
    ranking_sources: dict[str, Any] | None = None,
    nfl_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    league = client.league(config.sleeper_league_id)
    users = client.users(config.sleeper_league_id)
    rosters = client.rosters(config.sleeper_league_id)
    matchups = client.matchups(config.sleeper_league_id, week)
    transactions = client.transactions(config.sleeper_league_id, week)
    traded_picks = client.traded_picks(config.sleeper_league_id)
    flagship_context = (
        _collect_flagship_context(
            client,
            config.sleeper_league_id,
            str(state.get("season") or league.get("season") or "unknown"),
            week,
            matchups,
            transactions,
        )
        if config.tier == "flagship"
        else None
    )

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
    if flagship_context:
        for rows in (
            (flagship_context.get("schedule") or {}).get("weeks") or {}
        ).values():
            for matchup in rows:
                rostered_ids.update(
                    str(player_id) for player_id in (matchup.get("players") or [])
                )
        for records in (
            (flagship_context.get("transactions") or {}).get("weeks") or {}
        ).values():
            for transaction in records:
                rostered_ids.update(
                    str(player_id) for player_id in (transaction.get("adds") or {})
                )
                rostered_ids.update(
                    str(player_id) for player_id in (transaction.get("drops") or {})
                )
        for draft in (flagship_context.get("drafts") or {}).get("records") or []:
            rostered_ids.update(
                str(pick["player_id"])
                for pick in draft.get("picks") or []
                if pick.get("player_id") is not None
            )
        next_week = flagship_context.get("next_week_projections") or {}
        flagship_context["next_week_projections"] = _trim_ranking_sources(
            {"sleeper_projections": next_week},
            rostered_ids,
        )["sleeper_projections"]
    players = {
        player_id: _trim_player(
            player_directory.get(player_id) or {},
            include_editorial_context=config.tier == "flagship",
        )
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
            "publication_enabled": config.publication_enabled,
            "publication": config.publication,
            "publication_profile": {
                "key": publication.key,
                "recurring_sections": list(publication.recurring_sections),
                "brand_departments": list(publication.brand_departments),
                "editorial_priorities": list(publication.editorial_priorities),
            }
            if publication
            else None,
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
        "nfl_context": _trim_nfl_context(nfl_context or {}, players),
        "flagship_sleeper": flagship_context,
    }


def _collect_flagship_context(
    client: SleeperClient,
    league_id: str,
    season: str,
    week: int,
    current_matchups: list[dict[str, Any]],
    current_transactions: list[dict[str, Any]],
) -> dict[str, Any]:
    schedule_weeks: dict[str, list[dict[str, Any]]] = {}
    schedule_errors: dict[str, str] = {}
    transaction_weeks: dict[str, list[dict[str, Any]]] = {}
    transaction_errors: dict[str, str] = {}
    for schedule_week in range(1, 19):
        try:
            schedule_weeks[str(schedule_week)] = (
                current_matchups
                if schedule_week == week
                else client.matchups(league_id, schedule_week)
            )
        except (requests.RequestException, ValueError, KeyError) as exc:
            schedule_errors[str(schedule_week)] = str(exc)
        try:
            transaction_weeks[str(schedule_week)] = (
                current_transactions
                if schedule_week == week
                else client.transactions(league_id, schedule_week)
            )
        except (requests.RequestException, ValueError, KeyError) as exc:
            transaction_errors[str(schedule_week)] = str(exc)

    drafts = _optional_list(client.drafts, league_id)
    draft_records: list[dict[str, Any]] = []
    draft_errors: dict[str, str] = {}
    for draft in drafts.get("records") or []:
        draft_id = str(draft.get("draft_id") or "")
        if not draft_id:
            continue
        picks = _optional_list(client.draft_picks, draft_id)
        traded = _optional_list(client.draft_traded_picks, draft_id)
        draft_records.append(
            {
                "draft": draft,
                "picks": picks.get("records") or [],
                "traded_picks": traded.get("records") or [],
            }
        )
        if picks.get("status") != "available":
            draft_errors[f"{draft_id}:picks"] = str(picks.get("error"))
        if traded.get("status") != "available":
            draft_errors[f"{draft_id}:traded_picks"] = str(traded.get("error"))

    winners = _optional_list(client.winners_bracket, league_id)
    losers = _optional_list(client.losers_bracket, league_id)

    if week < 18:
        try:
            next_week_projections = {
                "status": "available",
                "season": season,
                "week": week + 1,
                "players": client.projections(season, week + 1),
            }
        except (requests.RequestException, ValueError, KeyError) as exc:
            next_week_projections = {
                "status": "unavailable",
                "season": season,
                "week": week + 1,
                "players": {},
                "error": str(exc),
            }
    else:
        next_week_projections = {
            "status": "not_applicable",
            "season": season,
            "week": None,
            "players": {},
        }

    schedule_status = "available"
    if schedule_errors:
        schedule_status = "partial" if schedule_weeks else "unavailable"
    transaction_status = "available"
    if transaction_errors:
        transaction_status = (
            "partial" if transaction_weeks else "unavailable"
        )
    drafts_status = drafts.get("status")
    if draft_errors and draft_records:
        drafts_status = "partial"

    return {
        "schedule": {
            "status": schedule_status,
            "weeks": schedule_weeks,
            "errors": schedule_errors,
        },
        "transactions": {
            "status": transaction_status,
            "weeks": transaction_weeks,
            "errors": transaction_errors,
        },
        "drafts": {
            "status": drafts_status,
            "records": draft_records,
            "errors": draft_errors,
        },
        "playoff_brackets": {
            "status": (
                "available"
                if winners.get("status") == losers.get("status") == "available"
                else "partial"
            ),
            "winners": winners.get("records") or [],
            "losers": losers.get("records") or [],
            "errors": {
                key: value
                for key, value in {
                    "winners": winners.get("error"),
                    "losers": losers.get("error"),
                }.items()
                if value
            },
        },
        "next_week_projections": next_week_projections,
    }


def _optional_list(fetcher: Any, *args: Any) -> dict[str, Any]:
    try:
        records = fetcher(*args)
        if not isinstance(records, list):
            raise ValueError("Sleeper response was not a list")
        return {"status": "available", "records": records}
    except (requests.RequestException, ValueError, KeyError) as exc:
        return {"status": "unavailable", "records": [], "error": str(exc)}


def _collect_nfl_week_context(
    client: NFLVerseClient, season: str, week: int
) -> dict[str, Any]:
    sources = {}
    for name, fetcher in (
        ("schedule", client.schedule),
        ("player_stats", client.player_stats),
        ("noteworthy_late_plays", client.noteworthy_late_plays),
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
    return {
        "provider": "nflverse",
        "season": season,
        "week": week,
        **sources,
    }


def _trim_nfl_context(
    context: dict[str, Any], players: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    gsis_ids = {
        str(player["gsis_id"])
        for player in players.values()
        if player.get("gsis_id")
    }
    result = {
        key: value
        for key, value in context.items()
        if key not in {"schedule", "player_stats", "noteworthy_late_plays"}
    }
    result["schedule"] = dict(context.get("schedule") or {})
    stats = dict(context.get("player_stats") or {})
    stats["records"] = [
        row
        for row in stats.get("records") or []
        if str(row.get("player_id") or "") in gsis_ids
    ]
    result["player_stats"] = stats
    plays = dict(context.get("noteworthy_late_plays") or {})
    plays["records"] = [
        row
        for row in plays.get("records") or []
        if gsis_ids.intersection(
            str(player_id) for player_id in row.get("player_ids") or []
        )
    ]
    result["noteworthy_late_plays"] = plays
    return result


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


def _trim_player(
    player: dict[str, Any], include_editorial_context: bool = False
) -> dict[str, Any]:
    fields = [
        "player_id",
        "full_name",
        "first_name",
        "last_name",
        "position",
        "fantasy_positions",
        "team",
        "status",
        "injury_status",
        "gsis_id",
    ]
    if include_editorial_context:
        fields.extend(
            [
                "age",
                "years_exp",
                "college",
                "number",
                "depth_chart_position",
                "depth_chart_order",
                "practice_participation",
                "injury_start_date",
                "news_updated",
            ]
        )
    return {
        key: player.get(key)
        for key in fields
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
