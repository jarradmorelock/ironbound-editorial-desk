from __future__ import annotations

from collections import defaultdict
from typing import Any


TEAM_ALIASES = {
    "JAC": "JAX",
    "LA": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
    "WSH": "WAS",
}


def build_game_timing(
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    scoreboard: list[dict[str, Any]],
) -> dict[str, Any]:
    context = snapshot.get("nfl_context") or {}
    schedule_source = context.get("schedule") or {}
    stats_source = context.get("player_stats") or {}
    plays_source = context.get("noteworthy_late_plays") or {}
    schedule = schedule_source.get("records") or []
    games_by_id = {
        str(game["game_id"]): game for game in schedule if game.get("game_id")
    }
    games_by_team = {}
    for game in schedule:
        for field in ("away_team", "home_team"):
            if game.get(field):
                games_by_team[_team_code(game[field])] = game

    players = snapshot.get("players") or {}
    stats_by_gsis = {
        str(row["player_id"]): row
        for row in stats_source.get("records") or []
        if row.get("player_id")
    }
    projections = (
        ((snapshot.get("ranking_inputs") or {}).get("sleeper_projections") or {}).get(
            "players"
        )
        or {}
    )
    scoring = (snapshot.get("league") or {}).get("scoring_settings") or {}
    roster_rows = {
        int(row["roster_id"]): row for row in snapshot.get("rosters") or []
    }
    starters_by_roster: dict[int, list[dict[str, Any]]] = defaultdict(list)
    starter_by_gsis: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        points = {
            str(player_id): _number(value)
            for player_id, value in (matchup.get("players_points") or {}).items()
        }
        roster = roster_rows.get(roster_id, {})
        submitted = matchup.get("starters") or roster.get("starters") or []
        for raw_player_id in submitted:
            player_id = str(raw_player_id)
            player = players.get(player_id) or {}
            gsis_id = str(player.get("gsis_id") or "") or None
            stats = stats_by_gsis.get(gsis_id or "")
            game = games_by_id.get(str((stats or {}).get("game_id") or ""))
            if game is None:
                game = games_by_team.get(_team_code(player.get("team")))
            projection_available = player_id in projections
            projected_points = (
                _projected_points(projections[player_id], scoring)
                if projection_available
                else None
            )
            game_complete = bool(
                game
                and game.get("away_score") is not None
                and game.get("home_score") is not None
            )
            row = {
                **teams.get(
                    roster_id,
                    {
                        "roster_id": roster_id,
                        "team": f"Roster {roster_id}",
                        "owner": f"Roster {roster_id}",
                    },
                ),
                "player_id": player_id,
                "gsis_id": gsis_id,
                "player": str(player.get("full_name") or player_id),
                "position": player.get("position"),
                "nfl_team": player.get("team"),
                "fantasy_points": round(points.get(player_id, 0.0), 2),
                "projected_points": projected_points,
                "projection_difference": (
                    round(points.get(player_id, 0.0) - projected_points, 2)
                    if projected_points is not None and game_complete
                    else None
                ),
                "game_complete": game_complete,
                "game": game,
                "weekday": (game or {}).get("weekday"),
                "gameday": (game or {}).get("gameday"),
                "gametime": (game or {}).get("gametime"),
                "opponent": _opponent(game, player.get("team")),
                "nfl_stats": stats,
                "nfl_stat_line": _stat_line(stats),
            }
            starters_by_roster[roster_id].append(row)
            if gsis_id:
                starter_by_gsis[gsis_id].append(row)

    thursday_games = _day_matchups("Thursday", scoreboard, starters_by_roster)
    early_days = ("Wednesday", "Thursday", "Friday", "Saturday")
    early_week_games = _day_matchups(
        early_days, scoreboard, starters_by_roster
    )
    monday_games = _day_matchups("Monday", scoreboard, starters_by_roster)
    thursday_players = [
        player
        for players_on_team in starters_by_roster.values()
        for player in players_on_team
        if _is_day(player.get("weekday"), "Thursday")
        and player.get("projection_difference") is not None
    ]
    monday_late_plays = _linked_monday_plays(
        plays_source.get("records") or [],
        games_by_id,
        starter_by_gsis,
        monday_games,
    )
    early_week_players = [
        player
        for players_on_team in starters_by_roster.values()
        for player in players_on_team
        if _matches_days(player.get("weekday"), early_days)
        and player.get("projection_difference") is not None
    ]

    return {
        "provider": context.get("provider"),
        "source_status": {
            "schedule": schedule_source.get("status", "not_collected"),
            "player_stats": stats_source.get("status", "not_collected"),
            "noteworthy_late_plays": plays_source.get(
                "status", "not_collected"
            ),
        },
        "nfl_games": schedule,
        "starter_game_days": [
            row
            for roster_id in sorted(starters_by_roster)
            for row in starters_by_roster[roster_id]
        ],
        "thursday": {
            "matchups": thursday_games,
            "positive_performances": sorted(
                (row for row in thursday_players if row["projection_difference"] > 0),
                key=lambda row: row["projection_difference"],
                reverse=True,
            ),
            "negative_performances": sorted(
                (row for row in thursday_players if row["projection_difference"] < 0),
                key=lambda row: row["projection_difference"],
            ),
            "margin_suppliers": [
                row for row in thursday_games if row.get("margin_supplied_by_day")
            ],
        },
        "early_week": {
            "weekdays": list(early_days),
            "matchups": early_week_games,
            "positive_performances": sorted(
                (
                    row
                    for row in early_week_players
                    if row["projection_difference"] > 0
                ),
                key=lambda row: row["projection_difference"],
                reverse=True,
            ),
            "negative_performances": sorted(
                (
                    row
                    for row in early_week_players
                    if row["projection_difference"] < 0
                ),
                key=lambda row: row["projection_difference"],
            ),
            "margin_suppliers": [
                row
                for row in early_week_games
                if row.get("margin_supplied_by_day")
            ],
        },
        "monday": {
            "matchups": monday_games,
            "lead_changes": [
                row for row in monday_games if row.get("lead_changed_on_day")
            ],
            "tie_breakers": [
                row for row in monday_games if row.get("tie_broken_on_day")
            ],
            "active_close_finishes": sorted(
                (
                    row
                    for row in monday_games
                    if row.get("completed") and row.get("day_was_active")
                ),
                key=lambda row: row.get("final_margin", 999999),
            ),
            "late_play_candidates": monday_late_plays,
        },
    }


def _day_matchups(
    weekday: str | tuple[str, ...],
    scoreboard: list[dict[str, Any]],
    starters_by_roster: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    weekdays = (weekday,) if isinstance(weekday, str) else weekday
    results = []
    for game in scoreboard:
        sides = []
        for team in game.get("teams") or []:
            roster_id = int(team["roster_id"])
            players = [
                row
                for row in starters_by_roster.get(roster_id, [])
                if _matches_days(row.get("weekday"), weekdays)
            ]
            sides.append(
                {
                    **team,
                    "day_points": round(
                        sum(row["fantasy_points"] for row in players), 2
                    ),
                    "day_projected_points": round(
                        sum(
                            row["projected_points"]
                            for row in players
                            if row.get("projected_points") is not None
                        ),
                        2,
                    ),
                    "players": players,
                }
            )
        if len(sides) != 2 or not any(side["players"] for side in sides):
            continue
        winner = game.get("winner")
        loser = game.get("loser")
        completed = bool(winner and loser)
        result = {
            "matchup_id": game.get("matchup_id"),
            "weekdays": sorted(
                {
                    str(player.get("weekday"))
                    for side in sides
                    for player in side["players"]
                    if player.get("weekday")
                }
            ),
            "teams": sides,
            "completed": completed,
            "final_margin": game.get("margin") if completed else None,
            "final_winner": winner.get("team") if winner else None,
            "final_loser": loser.get("team") if loser else None,
            "day_was_active": any(side["day_points"] for side in sides),
            "margin_supplied_by_day": False,
            "lead_changed_on_day": False,
            "tie_broken_on_day": False,
        }
        if completed:
            sides_by_roster = {int(side["roster_id"]): side for side in sides}
            winner_side = sides_by_roster[int(winner["roster_id"])]
            loser_side = sides_by_roster[int(loser["roster_id"])]
            day_edge = winner_side["day_points"] - loser_side["day_points"]
            winner_before = winner_side["points"] - winner_side["day_points"]
            loser_before = loser_side["points"] - loser_side["day_points"]
            result.update(
                {
                    "day_edge_for_winner": round(day_edge, 2),
                    "winner_score_before_day": round(winner_before, 2),
                    "loser_score_before_day": round(loser_before, 2),
                    "margin_supplied_by_day": day_edge >= _number(game.get("margin")),
                    "lead_changed_on_day": winner_before < loser_before,
                    "tie_broken_on_day": winner_before == loser_before,
                }
            )
        results.append(result)
    return sorted(
        results,
        key=lambda row: (
            not row.get("lead_changed_on_day"),
            row.get("final_margin") if row.get("final_margin") is not None else 999999,
            str(row.get("matchup_id")),
        ),
    )


def _linked_monday_plays(
    plays: list[dict[str, Any]],
    games_by_id: dict[str, dict[str, Any]],
    starter_by_gsis: dict[str, list[dict[str, Any]]],
    monday_matchups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matchup_by_roster = {
        int(team["roster_id"]): matchup
        for matchup in monday_matchups
        for team in matchup.get("teams") or []
    }
    results = []
    for play in plays:
        game = games_by_id.get(str(play.get("game_id") or "")) or {}
        if not _is_day(game.get("weekday"), "Monday"):
            continue
        linked = {}
        for gsis_id in play.get("player_ids") or []:
            for player in starter_by_gsis.get(str(gsis_id), []):
                key = (int(player["roster_id"]), str(player["player_id"]))
                fantasy_matchup = matchup_by_roster.get(int(player["roster_id"]))
                linked[key] = {
                    "roster_id": player["roster_id"],
                    "team": player["team"],
                    "player_id": player["player_id"],
                    "player": player["player"],
                    "fantasy_points": player["fantasy_points"],
                    "nfl_stat_line": player["nfl_stat_line"],
                    "fantasy_result": (
                        {
                            "completed": fantasy_matchup.get("completed"),
                            "final_margin": fantasy_matchup.get("final_margin"),
                            "final_winner": fantasy_matchup.get("final_winner"),
                            "final_loser": fantasy_matchup.get("final_loser"),
                            "starter_team_won": (
                                fantasy_matchup.get("final_winner") == player["team"]
                            ),
                        }
                        if fantasy_matchup
                        else None
                    ),
                }
        if not linked:
            continue
        linked_players = list(linked.values())
        completed_margins = [
            row["fantasy_result"]["final_margin"]
            for row in linked_players
            if row.get("fantasy_result")
            and row["fantasy_result"].get("completed")
            and row["fantasy_result"].get("final_margin") is not None
        ]
        results.append(
            {
                **play,
                "game": game,
                "linked_fantasy_starters": linked_players,
                "smallest_linked_final_margin": (
                    min(completed_margins) if completed_margins else None
                ),
            }
        )
    return sorted(
        results,
        key=lambda row: (
            not row.get("walkoff_candidate"),
            row.get("smallest_linked_final_margin")
            if row.get("smallest_linked_final_margin") is not None
            else 999999,
            row.get("game_seconds_remaining", 999999),
        ),
    )


def _projected_points(
    projection: dict[str, Any], scoring: dict[str, Any]
) -> float:
    return round(
        sum(
            _number(projection.get(stat)) * _number(multiplier)
            for stat, multiplier in scoring.items()
            if stat in projection
        ),
        2,
    )


def _stat_line(stats: dict[str, Any] | None) -> str | None:
    if not stats:
        return None
    parts = []
    completions = _number(stats.get("completions"))
    attempts = _number(stats.get("attempts"))
    if attempts:
        parts.append(f"{completions:g}/{attempts:g} passing")
    _append_stat(parts, stats, "passing_yards", "pass yds")
    _append_stat(parts, stats, "passing_tds", "pass TD")
    _append_stat(parts, stats, "passing_interceptions", "INT")
    _append_stat(parts, stats, "carries", "carries")
    _append_stat(parts, stats, "rushing_yards", "rush yds")
    _append_stat(parts, stats, "rushing_tds", "rush TD")
    receptions = _number(stats.get("receptions"))
    targets = _number(stats.get("targets"))
    if receptions or targets:
        parts.append(f"{receptions:g}/{targets:g} receiving")
    _append_stat(parts, stats, "receiving_yards", "rec yds")
    _append_stat(parts, stats, "receiving_tds", "rec TD")
    _append_stat(parts, stats, "def_tackles_solo", "solo tackles")
    _append_stat(parts, stats, "def_tackle_assists", "assists")
    _append_stat(parts, stats, "def_sacks", "sacks")
    _append_stat(parts, stats, "def_interceptions", "def INT")
    _append_stat(parts, stats, "def_tds", "def TD")
    field_goals = _number(stats.get("fg_made"))
    field_goal_attempts = _number(stats.get("fg_att"))
    if field_goals or field_goal_attempts:
        parts.append(f"{field_goals:g}/{field_goal_attempts:g} FG")
    _append_stat(parts, stats, "fg_long", "long FG")
    _append_stat(parts, stats, "fumbles_lost_total", "fumbles lost")
    _append_stat(parts, stats, "special_teams_tds", "special-teams TD")
    return ", ".join(parts) or "Recorded no counting statistics"


def _append_stat(
    parts: list[str], stats: dict[str, Any], field: str, label: str
) -> None:
    value = _number(stats.get(field))
    if value:
        parts.append(f"{value:g} {label}")


def _opponent(
    game: dict[str, Any] | None, player_team: Any
) -> str | None:
    if not game or not player_team:
        return None
    team = _team_code(player_team)
    away = _team_code(game.get("away_team"))
    home = _team_code(game.get("home_team"))
    if team == away:
        return home
    if team == home:
        return away
    return None


def _team_code(value: Any) -> str:
    code = str(value or "").upper()
    return TEAM_ALIASES.get(code, code)


def _is_day(value: Any, expected: str) -> bool:
    return str(value or "").casefold().startswith(expected.casefold())


def _matches_days(value: Any, expected: tuple[str, ...]) -> bool:
    return any(_is_day(value, day) for day in expected)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
