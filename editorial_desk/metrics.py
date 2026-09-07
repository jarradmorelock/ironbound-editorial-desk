from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


NON_STARTER_SLOTS = {"BN", "IR", "TAXI"}
FLEX_ELIGIBILITY = {
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"WR", "RB"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "IDP_FLEX": {"DL", "LB", "DB", "DE", "DT", "CB", "S"},
}
POSITION_ALIASES = {
    "DL": {"DL", "DE", "DT"},
    "DB": {"DB", "CB", "S"},
    "DEF": {"DEF"},
}


def build_weekly_dossier(snapshot: dict[str, Any]) -> dict[str, Any]:
    teams = _team_directory(snapshot)
    matchup_rows = snapshot.get("matchups") or []
    scoreboard = _scoreboard(matchup_rows, teams)
    all_play = _all_play(matchup_rows, teams)
    lineup = _lineup_efficiency(snapshot, teams)
    winners = [row["winner"] for row in scoreboard if row.get("winner")]
    losers = [row["loser"] for row in scoreboard if row.get("loser")]

    manager_candidates = [
        row for row in lineup if row["roster_id"] in {team["roster_id"] for team in winners}
    ]
    manager_of_week = max(
        manager_candidates,
        key=lambda row: (row["efficiency"], row["actual_points"]),
        default=None,
    )

    bad_beat = max(losers, key=lambda row: row["points"], default=None)
    escape_artist = min(winners, key=lambda row: row["points"], default=None)
    if bad_beat:
        bad_beat = {**bad_beat, "all_play": all_play[str(bad_beat["roster_id"])]}
    if escape_artist:
        escape_artist = {
            **escape_artist,
            "all_play": all_play[str(escape_artist["roster_id"])],
        }

    result_flips = _result_flips(snapshot, scoreboard, teams)
    waiver_stars = _waiver_star_candidates(snapshot, scoreboard, teams)
    division_summary = _division_summary(snapshot, matchup_rows, teams)
    bench_mvp = _bench_mvp(snapshot, teams)
    weekly_mvp = _weekly_mvp(snapshot, teams)

    return {
        "schema_version": 1,
        "league": snapshot.get("editorial"),
        "sleeper_league_name": (snapshot.get("league") or {}).get("name"),
        "season": (snapshot.get("league") or {}).get("season"),
        "week": snapshot.get("week"),
        "information_current_through": snapshot.get("collected_at"),
        "scoreboard": scoreboard,
        "all_play": all_play,
        "lineup_efficiency": lineup,
        "awards": {
            "mvp_card_result": weekly_mvp,
            "manager_of_the_week": manager_of_week,
            "bench_mvp": bench_mvp,
            "bad_beat": bad_beat,
            "escape_artist": escape_artist,
            "result_flipping_decisions": result_flips,
            "waiver_star_candidates": waiver_stars,
            "giant_killer": None,
        },
        "weekly_records": _weekly_records(scoreboard, matchup_rows, teams),
        "divisions": division_summary,
        "transactions": _transaction_summary(snapshot.get("transactions") or []),
        "deferred_until_history_exists": [
            "Giant Killer based on prior power expectations",
            "completed and remaining strength of schedule",
            "season and all-time record watch",
            "trade-afterlife trees",
            "publication-to-publication editorial memory",
        ],
    }


def starter_slots(league: dict[str, Any]) -> list[str]:
    return [
        str(slot)
        for slot in (league.get("roster_positions") or [])
        if str(slot) not in NON_STARTER_SLOTS
    ]


def optimal_lineup(
    player_ids: Iterable[str],
    player_points: dict[str, float],
    slots: list[str],
    players: dict[str, dict[str, Any]],
) -> tuple[float, dict[int, str]]:
    """Return the maximum score and a legal player assignment for the slots."""
    ids = [str(player_id) for player_id in dict.fromkeys(player_ids)]
    if not slots:
        return 0.0, {}

    dp: dict[int, tuple[float, dict[int, str]]] = {0: (0.0, {})}
    for player_id in ids:
        score = _number(player_points.get(player_id))
        eligible_slots = [
            index
            for index, slot in enumerate(slots)
            if _eligible(player_id, players.get(player_id) or {}, slot)
        ]
        if not eligible_slots:
            continue
        next_dp = dict(dp)
        for mask, (total, assignment) in dp.items():
            for index in eligible_slots:
                bit = 1 << index
                if mask & bit:
                    continue
                candidate_mask = mask | bit
                candidate_total = total + score
                existing = next_dp.get(candidate_mask)
                if existing is None or candidate_total > existing[0]:
                    next_dp[candidate_mask] = (
                        candidate_total,
                        {**assignment, index: player_id},
                    )
        dp = next_dp

    full_mask = (1 << len(slots)) - 1
    if full_mask in dp:
        return dp[full_mask]
    best_mask, result = max(
        dp.items(),
        key=lambda item: (item[0].bit_count(), item[1][0]),
    )
    return result


def _lineup_efficiency(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    slots = starter_slots(snapshot.get("league") or {})
    rosters = {
        int(row["roster_id"]): row for row in (snapshot.get("rosters") or [])
    }
    results: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        roster = rosters.get(roster_id, {})
        points = _points_map(matchup)
        starters = [str(player_id) for player_id in matchup.get("starters") or []]
        actual = sum(_number(points.get(player_id)) for player_id in starters)
        excluded = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in (roster.get(key) or [])
        }
        eligible_ids = [
            str(player_id)
            for player_id in matchup.get("players") or []
            if str(player_id) not in excluded
        ]
        optimal, assignment = optimal_lineup(eligible_ids, points, slots, players)
        efficiency = actual / optimal if optimal > 0 else 0.0
        results.append(
            {
                **teams[roster_id],
                "actual_points": round(actual, 2),
                "optimal_points": round(optimal, 2),
                "points_left_on_bench": round(max(0.0, optimal - actual), 2),
                "efficiency": round(efficiency, 4),
                "optimal_lineup": [
                    {
                        "slot": slots[index],
                        "player_id": player_id,
                        "player": _player_name(player_id, players),
                        "points": round(_number(points.get(player_id)), 2),
                    }
                    for index, player_id in sorted(assignment.items())
                ],
            }
        )
    return sorted(results, key=lambda row: (-row["efficiency"], -row["actual_points"]))


def _scoreboard(
    matchups: list[dict[str, Any]], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in matchups:
        grouped[row.get("matchup_id")].append(row)

    games: list[dict[str, Any]] = []
    for matchup_id, sides in grouped.items():
        if matchup_id is None or len(sides) != 2:
            continue
        sides = sorted(sides, key=lambda row: int(row["roster_id"]))
        team_rows = [
            {
                **teams[int(side["roster_id"])],
                "points": round(_number(side.get("points")), 2),
            }
            for side in sides
        ]
        ordered = sorted(team_rows, key=lambda row: row["points"], reverse=True)
        winner = ordered[0] if ordered[0]["points"] > ordered[1]["points"] else None
        loser = ordered[1] if winner else None
        games.append(
            {
                "matchup_id": matchup_id,
                "teams": team_rows,
                "winner": winner,
                "loser": loser,
                "tie": winner is None,
                "margin": round(abs(team_rows[0]["points"] - team_rows[1]["points"]), 2),
            }
        )
    return sorted(games, key=lambda row: str(row["matchup_id"]))


def _all_play(
    matchups: list[dict[str, Any]], teams: dict[int, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    scores = [
        (int(row["roster_id"]), _number(row.get("points"))) for row in matchups
    ]
    result: dict[str, dict[str, Any]] = {}
    for roster_id, score in scores:
        wins = sum(score > other for other_id, other in scores if other_id != roster_id)
        losses = sum(score < other for other_id, other in scores if other_id != roster_id)
        ties = len(scores) - 1 - wins - losses
        games = wins + losses + ties
        result[str(roster_id)] = {
            **teams[roster_id],
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_percentage": round((wins + ties * 0.5) / games, 4) if games else 0.0,
        }
    return result


def _bench_mvp(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> dict[str, Any] | None:
    players = snapshot.get("players") or {}
    rosters = {
        int(row["roster_id"]): row for row in (snapshot.get("rosters") or [])
    }
    candidates: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        roster = rosters.get(roster_id, {})
        starters = {str(player_id) for player_id in matchup.get("starters") or []}
        excluded = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in (roster.get(key) or [])
        }
        points = _points_map(matchup)
        for player_id in matchup.get("players") or []:
            player_id = str(player_id)
            if player_id in starters or player_id in excluded:
                continue
            candidates.append(
                {
                    **teams[roster_id],
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "points": round(_number(points.get(player_id)), 2),
                }
            )
    winner = max(candidates, key=lambda row: row["points"], default=None)
    return winner if winner and winner["points"] > 0 else None


def _weekly_mvp(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> dict[str, Any] | None:
    players = snapshot.get("players") or {}
    candidates: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        points = _points_map(matchup)
        for player_id in matchup.get("starters") or []:
            player_id = str(player_id)
            candidates.append(
                {
                    **teams[roster_id],
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "points": round(_number(points.get(player_id)), 2),
                }
            )
    return max(candidates, key=lambda row: row["points"], default=None)


def _result_flips(
    snapshot: dict[str, Any],
    scoreboard: list[dict[str, Any]],
    teams: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    matchups = {
        int(row["roster_id"]): row for row in (snapshot.get("matchups") or [])
    }
    rosters = {
        int(row["roster_id"]): row for row in (snapshot.get("rosters") or [])
    }
    players = snapshot.get("players") or {}
    slots = starter_slots(snapshot.get("league") or {})
    results: list[dict[str, Any]] = []

    for game in scoreboard:
        loser = game.get("loser")
        winner = game.get("winner")
        if not loser or not winner:
            continue
        roster_id = int(loser["roster_id"])
        matchup = matchups[roster_id]
        roster = rosters.get(roster_id, {})
        starters = [str(player_id) for player_id in matchup.get("starters") or []]
        excluded = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in (roster.get(key) or [])
        }
        bench = [
            str(player_id)
            for player_id in matchup.get("players") or []
            if str(player_id) not in set(starters) | excluded
        ]
        points = _points_map(matchup)
        candidates: list[dict[str, Any]] = []
        for index, starter_id in enumerate(starters[: len(slots)]):
            slot = slots[index]
            for bench_id in bench:
                if not _eligible(bench_id, players.get(bench_id) or {}, slot):
                    continue
                delta = _number(points.get(bench_id)) - _number(points.get(starter_id))
                revised = loser["points"] + delta
                if revised <= winner["points"]:
                    continue
                candidates.append(
                    {
                        **teams[roster_id],
                        "opponent": winner["team"],
                        "slot": slot,
                        "started_player_id": starter_id,
                        "started_player": _player_name(starter_id, players),
                        "started_points": round(_number(points.get(starter_id)), 2),
                        "bench_player_id": bench_id,
                        "bench_player": _player_name(bench_id, players),
                        "bench_points": round(_number(points.get(bench_id)), 2),
                        "point_swing": round(delta, 2),
                        "revised_team_score": round(revised, 2),
                        "opponent_score": winner["points"],
                    }
                )
        if candidates:
            results.append(min(candidates, key=lambda row: row["point_swing"]))
    return sorted(results, key=lambda row: row["point_swing"])


def _waiver_star_candidates(
    snapshot: dict[str, Any],
    scoreboard: list[dict[str, Any]],
    teams: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    winners = {
        int(game["winner"]["roster_id"]): game
        for game in scoreboard
        if game.get("winner")
    }
    matchups = {
        int(row["roster_id"]): row for row in (snapshot.get("matchups") or [])
    }
    players = snapshot.get("players") or {}
    candidates: list[dict[str, Any]] = []
    for transaction in snapshot.get("transactions") or []:
        if transaction.get("status") != "complete":
            continue
        if transaction.get("type") not in {"waiver", "free_agent"}:
            continue
        settings = transaction.get("settings") or {}
        for player_id, raw_roster_id in (transaction.get("adds") or {}).items():
            roster_id = int(raw_roster_id)
            if roster_id not in winners or roster_id not in matchups:
                continue
            matchup = matchups[roster_id]
            player_id = str(player_id)
            if player_id not in {str(value) for value in matchup.get("starters") or []}:
                continue
            points = _number(_points_map(matchup).get(player_id))
            team_points = _number(matchup.get("points"))
            margin = _number(winners[roster_id].get("margin"))
            candidates.append(
                {
                    **teams[roster_id],
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "points": round(points, 2),
                    "share_of_team_score": round(points / team_points, 4)
                    if team_points
                    else 0.0,
                    "victory_margin": round(margin, 2),
                    "outscored_victory_margin": points > margin,
                    "faab": settings.get("waiver_bid"),
                    "transaction_id": transaction.get("transaction_id"),
                }
            )
    return sorted(
        candidates,
        key=lambda row: (row["outscored_victory_margin"], row["points"]),
        reverse=True,
    )


def _weekly_records(
    scoreboard: list[dict[str, Any]],
    matchups: list[dict[str, Any]],
    teams: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    scores = [
        {**teams[int(row["roster_id"])], "points": round(_number(row.get("points")), 2)}
        for row in matchups
    ]
    if not scores:
        return {}
    completed = [game for game in scoreboard if game.get("winner")]
    return {
        "highest_score": max(scores, key=lambda row: row["points"]),
        "lowest_score": min(scores, key=lambda row: row["points"]),
        "largest_margin": max(completed, key=lambda row: row["margin"], default=None),
        "smallest_margin": min(completed, key=lambda row: row["margin"], default=None),
    }


def _division_summary(
    snapshot: dict[str, Any],
    matchups: list[dict[str, Any]],
    teams: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rosters = {
        int(row["roster_id"]): row for row in (snapshot.get("rosters") or [])
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for matchup in matchups:
        roster_id = int(matchup["roster_id"])
        division = str((rosters.get(roster_id, {}).get("settings") or {}).get("division") or "unassigned")
        grouped[division].append(
            {**teams[roster_id], "points": _number(matchup.get("points"))}
        )
    return [
        {
            "division_id": division,
            "teams": rows,
            "average_points": round(sum(row["points"] for row in rows) / len(rows), 2),
        }
        for division, rows in sorted(grouped.items())
    ]


def _transaction_summary(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [row for row in transactions if row.get("status") == "complete"]
    return {
        "completed": len(complete),
        "trades": sum(row.get("type") == "trade" for row in complete),
        "waivers": sum(row.get("type") == "waiver" for row in complete),
        "free_agents": sum(row.get("type") == "free_agent" for row in complete),
        "records": complete,
    }


def _team_directory(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    teams: dict[int, dict[str, Any]] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster["roster_id"])
        user = users.get(str(roster.get("owner_id"))) or {}
        metadata = user.get("metadata") or {}
        owner = str(user.get("display_name") or user.get("username") or f"Roster {roster_id}")
        team_name = str(metadata.get("team_name") or owner)
        teams[roster_id] = {
            "roster_id": roster_id,
            "team": team_name,
            "owner": owner,
        }
    return teams


def _points_map(matchup: dict[str, Any]) -> dict[str, float]:
    return {
        str(player_id): _number(points)
        for player_id, points in (matchup.get("players_points") or {}).items()
    }


def _player_name(player_id: str, players: dict[str, dict[str, Any]]) -> str:
    player = players.get(str(player_id)) or {}
    return str(player.get("full_name") or player_id)


def _eligible(player_id: str, player: dict[str, Any], slot: str) -> bool:
    positions = {
        str(position).upper()
        for position in (player.get("fantasy_positions") or [])
        if position
    }
    if player.get("position"):
        positions.add(str(player["position"]).upper())
    if slot == "DEF" and not positions and player_id.isalpha():
        positions.add("DEF")
    allowed = FLEX_ELIGIBILITY.get(slot) or POSITION_ALIASES.get(slot) or {slot}
    return bool(positions & allowed)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
