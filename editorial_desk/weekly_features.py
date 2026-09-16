from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .metrics import _eligible, optimal_lineup, starter_slots


NFLVERSE_SCORING_FIELDS = {
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pass_int": "passing_interceptions",
    "pass_cmp": "completions",
    "pass_att": "attempts",
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "rush_fd": "rushing_first_downs",
    "rush_att": "carries",
    "rec": "receptions",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "rec_fd": "receiving_first_downs",
    "fum_lost": "fumbles_lost_total",
    "pass_2pt": "passing_2pt_conversions",
    "rush_2pt": "rushing_2pt_conversions",
    "rec_2pt": "receiving_2pt_conversions",
}


def apply_weekly_features(
    snapshot: dict[str, Any], dossier: dict[str, Any]
) -> dict[str, Any]:
    """Attach deterministic magazine features and editorial lineup efficiency."""
    lineup = _lineup_efficiency(snapshot)
    dossier["lineup_efficiency"] = lineup
    _replace_manager_of_week(snapshot, dossier, lineup)
    features = {
        "lineup_efficiency_top_three": lineup[:3],
        "top_scorers_by_position": _top_scorers_by_position(snapshot),
        "benchwarmer_of_the_week": _benchwarmer_of_week(snapshot),
        "rookie_of_the_week": _rookie_of_week(snapshot),
        "free_agent_of_the_week": _free_agent_of_week(snapshot),
    }
    editorial = snapshot.get("editorial") or {}
    profile = editorial.get("publication_profile") or {}
    weekly_contract_features = set(profile.get("weekly_features") or [])
    if (
        not profile
        or editorial.get("tier") == "flagship"
        or "divisional_started_mvps" in weekly_contract_features
    ):
        features["divisional_mvp_nominees"] = _divisional_mvp_nominees(snapshot)
    dossier["weekly_features"] = features
    return dossier


def _lineup_efficiency(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    slots = starter_slots(snapshot.get("league") or {})
    rosters = {
        int(row["roster_id"]): row for row in snapshot.get("rosters") or []
    }
    teams = _teams(snapshot)
    rows: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        roster = rosters.get(roster_id, {})
        points = _points_map(matchup)
        starters = [str(player_id) for player_id in matchup.get("starters") or []]
        actual = sum(_number(points.get(player_id)) for player_id in starters)

        # Editorial MAX answers "what was the best legal active lineup?" Taxi and
        # reserve/IR players are intentionally excluded even when a platform's
        # own Max PF accounting chooses to include taxi production.
        reserve = {str(player_id) for player_id in roster.get("reserve") or []}
        taxi = {str(player_id) for player_id in roster.get("taxi") or []}
        inactive = reserve | taxi
        eligible_ids = [
            str(player_id)
            for player_id in matchup.get("players") or []
            if str(player_id) not in inactive
        ]
        optimal, assignment = optimal_lineup(eligible_ids, points, slots, players)
        rows.append(
            {
                **teams.get(roster_id, {"roster_id": roster_id}),
                "actual_points": round(actual, 2),
                "optimal_points": round(optimal, 2),
                "points_left_on_bench": round(max(0.0, optimal - actual), 2),
                "efficiency": round(actual / optimal, 4) if optimal > 0 else 0.0,
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
    return sorted(rows, key=lambda row: (-row["efficiency"], -row["actual_points"]))


def _replace_manager_of_week(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    lineup: list[dict[str, Any]],
) -> None:
    winner_games = {
        int(game["winner"]["roster_id"]): game
        for game in dossier.get("scoreboard") or []
        if game.get("winner")
    }
    candidates = [
        dict(row)
        for row in lineup
        if int(row.get("roster_id") or 0) in winner_games
    ]
    if not candidates:
        dossier.setdefault("awards", {})["manager_of_the_week"] = None
        return

    efficiency_ranks = _dense_ranks(
        {int(row["roster_id"]): _number(row.get("efficiency")) for row in candidates}
    )
    score_ranks = _dense_ranks(
        {int(row["roster_id"]): _number(row.get("actual_points")) for row in candidates}
    )
    evidence_by_roster = _management_tiebreak_evidence(snapshot, winner_games)

    for row in candidates:
        roster_id = int(row["roster_id"])
        game = winner_games[roster_id]
        evidence = evidence_by_roster.get(roster_id, [])
        row["head_to_head_result"] = "win"
        row["victory_margin"] = round(_number(game.get("margin")), 2)
        loser = game.get("loser") or {}
        row["opponent"] = loser.get("team")
        row["efficiency_rank_among_winners"] = efficiency_ranks[roster_id]
        row["score_rank_among_winners"] = score_ranks[roster_id]
        row["manager_rank_sum"] = (
            efficiency_ranks[roster_id] + score_ranks[roster_id]
        )
        row["management_tiebreak"] = {
            "count": len(evidence),
            "impact_points": round(
                sum(_number(item.get("impact_points")) for item in evidence), 2
            ),
            "evidence": evidence,
        }

    best_rank_sum = min(row["manager_rank_sum"] for row in candidates)
    finalists = [
        row for row in candidates if row["manager_rank_sum"] == best_rank_sum
    ]
    winner = max(
        finalists,
        key=lambda row: (
            (row.get("management_tiebreak") or {}).get("count", 0),
            (row.get("management_tiebreak") or {}).get("impact_points", 0.0),
            row.get("actual_points", 0.0),
            row.get("efficiency", 0.0),
        ),
    )
    winner["selection_basis"] = (
        "Winner-only award balancing weekly lineup-efficiency rank and scoring "
        "rank. Documented management decisions are used only to break an "
        "equal base rank sum."
    )
    dossier.setdefault("awards", {})["manager_of_the_week"] = winner


def _dense_ranks(values: dict[int, float]) -> dict[int, int]:
    ordered = sorted(set(values.values()), reverse=True)
    ranks = {value: index + 1 for index, value in enumerate(ordered)}
    return {roster_id: ranks[value] for roster_id, value in values.items()}


def _management_tiebreak_evidence(
    snapshot: dict[str, Any], winner_games: dict[int, dict[str, Any]]
) -> dict[int, list[dict[str, Any]]]:
    matchups = {
        int(row["roster_id"]): row for row in snapshot.get("matchups") or []
    }
    rosters = {
        int(row["roster_id"]): row for row in snapshot.get("rosters") or []
    }
    players = snapshot.get("players") or {}
    slots = starter_slots(snapshot.get("league") or {})
    scoring = (snapshot.get("league") or {}).get("scoring_settings") or {}
    projection_source = (
        (snapshot.get("ranking_inputs") or {}).get("sleeper_projections") or {}
    )
    projections = (
        projection_source.get("players") or {}
        if projection_source.get("status") == "available"
        else {}
    )
    evidence: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for roster_id, game in winner_games.items():
        matchup = matchups.get(roster_id) or {}
        roster = rosters.get(roster_id) or {}
        starters = [str(player_id) for player_id in matchup.get("starters") or []]
        starter_set = set(starters)
        inactive = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in roster.get(key) or []
        }
        bench = [
            str(player_id)
            for player_id in matchup.get("players") or []
            if str(player_id) not in starter_set | inactive
        ]
        points = _points_map(matchup)
        margin = _number(game.get("margin"))

        if projections and scoring:
            for index, starter_id in enumerate(starters[: len(slots)]):
                if starter_id not in projections:
                    continue
                slot = slots[index]
                starter_projection = _projected_points(
                    projections.get(starter_id) or {}, scoring
                )
                starter_actual = _number(points.get(starter_id))
                calls: list[dict[str, Any]] = []
                for bench_id in bench:
                    if bench_id not in projections:
                        continue
                    if not _eligible(bench_id, players.get(bench_id) or {}, slot):
                        continue
                    bench_projection = _projected_points(
                        projections.get(bench_id) or {}, scoring
                    )
                    bench_actual = _number(points.get(bench_id))
                    point_swing = starter_actual - bench_actual
                    if (
                        starter_projection >= bench_projection
                        or starter_actual <= bench_actual
                        or point_swing < margin
                    ):
                        continue
                    calls.append(
                        {
                            "type": "projection_start_sit",
                            "slot": slot,
                            "started_player_id": starter_id,
                            "started_player": _player_name(starter_id, players),
                            "started_projection": round(starter_projection, 2),
                            "started_points": round(starter_actual, 2),
                            "bench_player_id": bench_id,
                            "bench_player": _player_name(bench_id, players),
                            "bench_projection": round(bench_projection, 2),
                            "bench_points": round(bench_actual, 2),
                            "projection_gap": round(
                                bench_projection - starter_projection, 2
                            ),
                            "point_swing": round(point_swing, 2),
                            "victory_margin": round(margin, 2),
                            "impact_points": round(point_swing, 2),
                        }
                    )
                if calls:
                    evidence[roster_id].append(
                        max(
                            calls,
                            key=lambda row: (
                                row["point_swing"], row["projection_gap"]
                            ),
                        )
                    )

    for transaction in snapshot.get("transactions") or []:
        if transaction.get("status") != "complete":
            continue
        transaction_type = str(transaction.get("type") or "")
        if transaction_type not in {"waiver", "free_agent", "trade"}:
            continue
        for player_id, raw_roster_id in (transaction.get("adds") or {}).items():
            try:
                roster_id = int(raw_roster_id)
            except (TypeError, ValueError):
                continue
            if roster_id not in winner_games:
                continue
            matchup = matchups.get(roster_id) or {}
            player_id = str(player_id)
            if player_id not in {
                str(value) for value in matchup.get("starters") or []
            }:
                continue
            points = _number(_points_map(matchup).get(player_id))
            margin = _number(winner_games[roster_id].get("margin"))
            if points < margin:
                continue
            settings = transaction.get("settings") or {}
            evidence[roster_id].append(
                {
                    "type": "transaction_start",
                    "transaction_type": transaction_type,
                    "transaction_id": transaction.get("transaction_id"),
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "points": round(points, 2),
                    "victory_margin": round(margin, 2),
                    "faab": settings.get("waiver_bid"),
                    "impact_points": round(points, 2),
                }
            )

    return dict(evidence)


def _projected_points(
    projection: dict[str, Any], scoring_settings: dict[str, Any]
) -> float:
    return sum(
        _number(projection.get(stat)) * _number(multiplier)
        for stat, multiplier in scoring_settings.items()
        if stat in projection
    )


def _divisional_mvp_nominees(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    rosters = {
        int(row["roster_id"]): row for row in snapshot.get("rosters") or []
    }
    teams = _teams(snapshot)
    metadata = (snapshot.get("league") or {}).get("metadata") or {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        division = (rosters.get(roster_id, {}).get("settings") or {}).get("division")
        if division is None:
            continue
        division_id = str(division)
        points = _points_map(matchup)
        for player_id in matchup.get("starters") or []:
            player_id = str(player_id)
            grouped[division_id].append(
                {
                    **teams.get(roster_id, {"roster_id": roster_id}),
                    "division_id": division_id,
                    "division_name": str(
                        metadata.get(f"division_{division_id}")
                        or f"Division {division_id}"
                    ),
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "position": _position(players.get(player_id) or {}),
                    "points": round(_number(points.get(player_id)), 2),
                    "status": "STARTED",
                    "gold_foil": False,
                }
            )

    nominees = [
        max(rows, key=lambda row: (row["points"], row["player"]))
        for _, rows in sorted(grouped.items())
        if rows
    ]
    if nominees:
        gold = max(nominees, key=lambda row: (row["points"], row["player"]))
        gold["gold_foil"] = True
    return nominees


def _top_scorers_by_position(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    leaders: dict[str, dict[str, Any]] = {}
    for row in _rostered_player_weeks(snapshot):
        position = str(row.get("position") or "")
        if not position:
            continue
        current = leaders.get(position)
        if current is None or (row["points"], row["player"]) > (
            current["points"],
            current["player"],
        ):
            leaders[position] = row
    return leaders


def _benchwarmer_of_week(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        row for row in _rostered_player_weeks(snapshot) if row["status"] == "BENCH"
    ]
    winner = max(candidates, key=lambda row: (row["points"], row["player"]), default=None)
    return winner if winner and winner["points"] > 0 else None


def _rookie_of_week(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    players = snapshot.get("players") or {}
    candidates = []
    for row in _rostered_player_weeks(snapshot):
        player = players.get(row["player_id"]) or {}
        years_exp = player.get("years_exp")
        if years_exp is None or _position(player) == "DEF":
            continue
        if _integer(years_exp) == 0:
            candidates.append(row)
    winner = max(candidates, key=lambda row: (row["points"], row["player"]), default=None)
    return winner if winner and winner["points"] > 0 else None


def _free_agent_of_week(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    source = (snapshot.get("nfl_context") or {}).get("player_stats") or {}
    if source.get("status") != "available":
        return None

    rostered_gsis, rostered_signatures = _current_rostered_identities(snapshot)
    scoring = (snapshot.get("league") or {}).get("scoring_settings") or {}
    candidates: list[dict[str, Any]] = []
    for stat_row in source.get("records") or []:
        player_id = str(stat_row.get("player_id") or "")
        signature = _identity_signature(
            stat_row.get("player_display_name") or stat_row.get("player_name"),
            stat_row.get("team"),
            stat_row.get("position"),
        )
        if (
            not player_id
            or player_id in rostered_gsis
            or (signature and signature in rostered_signatures)
        ):
            continue
        points = _score_nflverse_row(stat_row, scoring)
        if points <= 0:
            continue
        candidates.append(
            {
                "player_id": player_id,
                "player": str(
                    stat_row.get("player_display_name")
                    or stat_row.get("player_name")
                    or player_id
                ),
                "position": stat_row.get("position"),
                "team": stat_row.get("team"),
                "points": round(points, 2),
                "status": "FREE_AGENT",
            }
        )
    return max(candidates, key=lambda row: (row["points"], row["player"]), default=None)


def _current_rostered_identities(snapshot: dict[str, Any]) -> tuple[set[str], set[tuple[str, str, str]]]:
    players = snapshot.get("players") or {}
    current_ids: set[str] = set()
    for roster in snapshot.get("rosters") or []:
        for field in ("players", "taxi", "reserve"):
            current_ids.update(str(player_id) for player_id in (roster.get(field) or []))

    gsis: set[str] = set()
    signatures: set[tuple[str, str, str]] = set()
    for player_id in current_ids:
        player = players.get(player_id) or {}
        if player.get("gsis_id"):
            gsis.add(str(player["gsis_id"]))
        signature = _identity_signature(
            _player_name(player_id, players), player.get("team"), _position(player)
        )
        if signature:
            signatures.add(signature)
    return gsis, signatures


def _score_nflverse_row(
    row: dict[str, Any], scoring_settings: dict[str, Any]
) -> float:
    total = 0.0
    for sleeper_stat, nflverse_field in NFLVERSE_SCORING_FIELDS.items():
        if sleeper_stat not in scoring_settings:
            continue
        total += _number(row.get(nflverse_field)) * _number(
            scoring_settings.get(sleeper_stat)
        )
    return total


def _rostered_player_weeks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    rosters = {
        int(row["roster_id"]): row for row in snapshot.get("rosters") or []
    }
    teams = _teams(snapshot)
    rows: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        roster = rosters.get(roster_id, {})
        starters = {str(player_id) for player_id in matchup.get("starters") or []}
        taxi = {str(player_id) for player_id in roster.get("taxi") or []}
        reserve = {str(player_id) for player_id in roster.get("reserve") or []}
        points = _points_map(matchup)
        for player_id in matchup.get("players") or []:
            player_id = str(player_id)
            if player_id in starters:
                status = "STARTED"
            elif player_id in taxi:
                status = "TAXI"
            elif player_id in reserve:
                status = "RESERVE"
            else:
                status = "BENCH"
            player = players.get(player_id) or {}
            rows.append(
                {
                    **teams.get(roster_id, {"roster_id": roster_id}),
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "position": _position(player),
                    "points": round(_number(points.get(player_id)), 2),
                    "status": status,
                }
            )
    return rows


def _teams(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    teams: dict[int, dict[str, Any]] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster["roster_id"])
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        teams[roster_id] = {
            "roster_id": roster_id,
            "owner_id": roster.get("owner_id"),
            "manager": owner.get("display_name") or str(roster.get("owner_id") or ""),
            "team": metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}",
        }
    return teams


def _points_map(matchup: dict[str, Any]) -> dict[str, float]:
    raw = matchup.get("players_points") or matchup.get("players_points_custom") or {}
    return {str(player_id): _number(points) for player_id, points in raw.items()}


def _player_name(player_id: str, players: dict[str, dict[str, Any]]) -> str:
    player = players.get(str(player_id)) or {}
    return str(
        player.get("full_name")
        or " ".join(
            part for part in (player.get("first_name"), player.get("last_name")) if part
        ).strip()
        or player_id
    )


def _position(player: dict[str, Any]) -> str | None:
    position = player.get("position")
    if position:
        return str(position)
    fantasy_positions = player.get("fantasy_positions") or []
    return str(fantasy_positions[0]) if fantasy_positions else None


def _identity_signature(name: Any, team: Any, position: Any) -> tuple[str, str, str] | None:
    normalized = _normalize_name(str(name or ""))
    team_text = str(team or "").upper()
    position_text = str(position or "").upper()
    if not normalized or not team_text or not position_text:
        return None
    return normalized, team_text, position_text


def _normalize_name(value: str) -> str:
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value.casefold())
    return re.sub(r"[^a-z0-9]", "", value)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0
