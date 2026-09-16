from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .timing import build_game_timing


NON_STARTER_SLOTS = {"BN", "IR", "RESERVE", "TAXI"}
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
    league_median = _league_median(snapshot, teams)
    median_by_roster = {
        int(row["roster_id"]): row for row in league_median.get("results") or []
    }
    lineup = _lineup_efficiency(snapshot, teams)
    rankings = _rankings(snapshot, teams)
    game_timing = build_game_timing(snapshot, teams, scoreboard)
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
        roster_id = int(bad_beat["roster_id"])
        bad_beat = {
            **bad_beat,
            "all_play": all_play[str(roster_id)],
            "league_median": median_by_roster.get(roster_id),
        }
    if escape_artist:
        roster_id = int(escape_artist["roster_id"])
        escape_artist = {
            **escape_artist,
            "all_play": all_play[str(roster_id)],
            "league_median": median_by_roster.get(roster_id),
        }

    result_flips = _result_flips(snapshot, scoreboard, teams)
    waiver_stars = _waiver_star_candidates(snapshot, scoreboard, teams)
    editorial = snapshot.get("editorial") or {}
    profile = editorial.get("publication_profile") or {}
    weekly_features = set(profile.get("weekly_features") or [])
    division_summary = (
        _division_summary(snapshot, matchup_rows, scoreboard, league_median, teams)
        if editorial.get("tier") == "flagship" or "division_metrics" in weekly_features
        else []
    )
    bench_mvp = _bench_mvp(snapshot, teams)
    weekly_mvp = _weekly_mvp(snapshot, teams)
    flagship_supplement = _flagship_supplement(snapshot, teams, rankings)
    deferred = [
        "Giant Killer based on prior power expectations",
        "all-time and cross-season record watch",
        "trade-afterlife trees",
        "publication-to-publication editorial memory",
    ]
    if not flagship_supplement:
        deferred.insert(1, "completed and remaining strength of schedule")

    return {
        "schema_version": 1,
        "league": snapshot.get("editorial"),
        "sleeper_league_name": (snapshot.get("league") or {}).get("name"),
        "season": (snapshot.get("league") or {}).get("season"),
        "week": snapshot.get("week"),
        "information_current_through": snapshot.get("collected_at"),
        "scoreboard": scoreboard,
        "all_play": all_play,
        "league_median": league_median,
        "lineup_efficiency": lineup,
        "rankings": rankings,
        "game_timing": game_timing,
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
        "flagship_supplement": flagship_supplement,
        "publication_sections": (
            ((snapshot.get("editorial") or {}).get("publication_profile") or {}).get(
                "recurring_sections"
            )
            or []
        ),
        "brand_departments": (
            ((snapshot.get("editorial") or {}).get("publication_profile") or {}).get(
                "brand_departments"
            )
            or []
        ),
        "editorial_priorities": (
            ((snapshot.get("editorial") or {}).get("publication_profile") or {}).get(
                "editorial_priorities"
            )
            or []
        ),
        "deferred_until_history_exists": deferred,
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


def _league_median(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    league = snapshot.get("league") or {}
    enabled = bool((league.get("settings") or {}).get("league_average_match"))
    scores = sorted(
        (
            int(row["roster_id"]),
            _number(row.get("points")),
        )
        for row in (snapshot.get("matchups") or [])
    )
    if not scores:
        return {"enabled": enabled, "points": None, "results": []}

    ordered = sorted(score for _, score in scores)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / 2

    results = []
    for roster_id, score in scores:
        result = "tie"
        if score > median:
            result = "win"
        elif score < median:
            result = "loss"
        results.append(
            {
                **teams[roster_id],
                "points": round(score, 2),
                "result": result,
                "difference": round(score - median, 2),
            }
        )
    return {
        "enabled": enabled,
        "points": round(median, 2),
        "results": results if enabled else [],
    }


def _rankings(
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    league = snapshot.get("league") or {}
    metadata = league.get("metadata") or {}
    rosters = snapshot.get("rosters") or []
    official_rows: list[dict[str, Any]] = []
    for roster in rosters:
        roster_id = int(roster["roster_id"])
        settings = roster.get("settings") or {}
        wins = int(settings.get("wins") or 0)
        losses = int(settings.get("losses") or 0)
        ties = int(settings.get("ties") or 0)
        games = wins + losses + ties
        division_id = settings.get("division")
        official_rows.append(
            {
                **teams[roster_id],
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_percentage": round((wins + ties * 0.5) / games, 4)
                if games
                else 0.0,
                "points_for": _roster_points(settings),
                "division_id": division_id,
                "division_name": str(
                    metadata.get(f"division_{division_id}")
                    or (f"Division {division_id}" if division_id is not None else "")
                ),
            }
        )
    official_rows.sort(
        key=lambda row: (
            -row["win_percentage"],
            -row["wins"],
            -row["points_for"],
            row["team"].casefold(),
        )
    )
    for rank, row in enumerate(official_rows, start=1):
        row["rank"] = rank
    official_status = (
        "active"
        if any(row["wins"] or row["losses"] or row["ties"] for row in official_rows)
        else "season_not_started"
    )

    component_rows, source_status = _ranking_components(
        snapshot,
        teams,
        official_rows,
    )
    editorial = snapshot.get("editorial") or {}
    ranking_model = str(editorial.get("ranking_model") or "")
    if ranking_model == "redraft_projection_starters_record":
        data_power_ranking = _redraft_power_ranking(component_rows, source_status)
    else:
        data_power_ranking = _dynasty_power_ranking(component_rows, source_status)

    return {
        "league_format": editorial.get("league_format"),
        "ranking_model": ranking_model,
        "sources": source_status,
        "official_standings_status": official_status,
        "official_standings": official_rows,
        "data_power_ranking": data_power_ranking,
        "prior_published_ranking": {
            "status": "awaiting_publication_archive",
            "rows": [],
        },
        "editorial_note": data_power_ranking["editorial_note"],
    }


def _ranking_components(
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    official_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    league = snapshot.get("league") or {}
    scoring_settings = league.get("scoring_settings") or {}
    slots = starter_slots(league)
    players = snapshot.get("players") or {}
    inputs = snapshot.get("ranking_inputs") or {}
    sleeper_source = inputs.get("sleeper_projections") or {}
    dynasty_source = inputs.get("dynasty_daddy") or {}
    projections = sleeper_source.get("players") or {}
    dynasty_values = dynasty_source.get("players") or {}
    matchup_starters = {
        int(row["roster_id"]): [str(value) for value in row.get("starters") or []]
        for row in (snapshot.get("matchups") or [])
    }
    records = {
        int(row["roster_id"]): _number(row["win_percentage"])
        for row in official_rows
    }
    is_superflex = "SUPER_FLEX" in slots
    component_rows: list[dict[str, Any]] = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster["roster_id"])
        excluded = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in (roster.get(key) or [])
        }
        roster_ids = [
            str(player_id)
            for player_id in (roster.get("players") or [])
            if str(player_id) not in excluded
        ]
        projection_points = {
            player_id: _projected_player_points(
                projections.get(player_id) or {},
                scoring_settings,
            )
            for player_id in roster_ids
        }
        submitted = [
            str(player_id)
            for player_id in (
                matchup_starters.get(roster_id) or roster.get("starters") or []
            )
        ]
        submitted_projection = sum(
            projection_points.get(player_id, 0.0) for player_id in submitted
        )
        optimal_projection, _ = optimal_lineup(
            roster_ids,
            projection_points,
            slots,
            players,
        )
        starter_values = {
            player_id: _starter_market_score(dynasty_values.get(player_id) or {})
            for player_id in roster_ids
        }
        starter_market_value, _ = optimal_lineup(
            roster_ids,
            starter_values,
            slots,
            players,
        )
        value_field = "sf_trade_value" if is_superflex else "trade_value"
        total_dynasty_value = sum(
            _number((dynasty_values.get(player_id) or {}).get(value_field))
            for player_id in roster_ids
        )
        component_rows.append(
            {
                **teams[roster_id],
                "submitted_lineup_projection": round(submitted_projection, 2),
                "optimal_starting_lineup_projection": round(
                    optimal_projection, 2
                ),
                "dynasty_starter_strength": round(starter_market_value, 2),
                "dynasty_roster_value": round(total_dynasty_value, 2),
                "win_loss_percentage": records.get(roster_id, 0.0),
            }
        )

    for field in (
        "submitted_lineup_projection",
        "optimal_starting_lineup_projection",
        "dynasty_starter_strength",
        "dynasty_roster_value",
        "win_loss_percentage",
    ):
        ranks = _metric_ranks(
            {int(row["roster_id"]): _number(row[field]) for row in component_rows}
        )
        for row in component_rows:
            row[f"{field}_rank"] = ranks[int(row["roster_id"])]

    source_status = {
        "sleeper_projections": sleeper_source.get("status", "not_collected"),
        "dynasty_daddy": dynasty_source.get("status", "not_collected"),
    }
    return component_rows, source_status


def _redraft_power_ranking(
    rows: list[dict[str, Any]], source_status: dict[str, Any]
) -> dict[str, Any]:
    ready = source_status["sleeper_projections"] == "available" and any(
        row["submitted_lineup_projection"]
        or row["optimal_starting_lineup_projection"]
        for row in rows
    )
    ranked_rows = []
    if ready:
        for row in rows:
            component_ranks = {
                "projection": row["submitted_lineup_projection_rank"],
                "starting_lineup": row["optimal_starting_lineup_projection_rank"],
                "win_loss_record": row["win_loss_percentage_rank"],
            }
            ranked_rows.append(
                {
                    **row,
                    "component_ranks": component_ranks,
                    "consensus_rank_average": round(
                        sum(component_ranks.values()) / len(component_ranks), 3
                    ),
                }
            )
        ranked_rows.sort(
            key=lambda row: (
                row["consensus_rank_average"],
                -row["submitted_lineup_projection"],
                row["team"].casefold(),
            )
        )
        for rank, row in enumerate(ranked_rows, start=1):
            row["rank"] = rank
    return {
        "status": "calculated" if ready else "awaiting_projection_data",
        "methodology": {
            "components": [
                "submitted lineup projection",
                "optimal starting lineup projection",
                "win-loss record",
            ],
            "aggregation": "Equal average of the three league-relative ranks.",
            "excluded": [
                "dynasty roster value",
                "future draft capital",
                "all-play",
                "lineup efficiency",
            ],
        },
        "rows": ranked_rows,
        "editorial_note": (
            "Redraft power rankings use only projection, starting lineup, and "
            "win-loss record."
        ),
    }


def _dynasty_power_ranking(
    rows: list[dict[str, Any]], source_status: dict[str, Any]
) -> dict[str, Any]:
    available = [
        "projected scoring",
        "starter strength",
        "current dynasty roster value",
        "win-loss record",
    ]
    missing = [
        "playoff probability",
        "title probability",
        "schedule context",
        "roster-balance editorial review",
        "future-pick portfolio value",
    ]
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            row["dynasty_starter_strength_rank"],
            row["optimal_starting_lineup_projection_rank"],
            row["team"].casefold(),
        ),
    )
    sources_ready = all(
        source_status[source] == "available"
        for source in ("sleeper_projections", "dynasty_daddy")
    )
    return {
        "status": (
            "component_inputs_collected" if sources_ready else "awaiting_sources"
        ),
        "methodology": {
            "model": "The Ironbound Weekly / Unbound Weekly dynasty model",
            "available_components": available,
            "pending_components": missing,
            "aggregation": (
                "Editorial synthesis led by starter strength and projected "
                "scoring; no substitute weighted formula is applied."
            ),
        },
        "rows": ranked_rows,
        "editorial_note": (
            "Dynasty teams use the flagship Ironbound/Unbound method. The desk "
            "preserves every component and does not replace it with the redraft "
            "formula."
        ),
    }


def _metric_ranks(values: dict[int, float]) -> dict[int, int]:
    ordered = sorted(set(values.values()), reverse=True)
    ranks = {value: index + 1 for index, value in enumerate(ordered)}
    return {roster_id: ranks[value] for roster_id, value in values.items()}


def _projected_player_points(
    projection: dict[str, Any], scoring_settings: dict[str, Any]
) -> float:
    return round(
        sum(
            _number(projection.get(stat)) * _number(multiplier)
            for stat, multiplier in scoring_settings.items()
            if stat in projection
        ),
        4,
    )


def _starter_market_score(player: dict[str, Any]) -> float:
    rank = _number(player.get("avg_ros") or player.get("avg_adp"))
    return max(0.0, 1000.0 - rank) if rank else 0.0


def _roster_points(settings: dict[str, Any]) -> float:
    whole = _number(settings.get("fpts"))
    decimal = _number(settings.get("fpts_decimal")) / 100
    return round(whole + decimal, 2)


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
    winner = max(candidates, key=lambda row: row["points"], default=None)
    return winner if winner and winner["points"] > 0 else None


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
    if not any(row["points"] for row in scores):
        return {
            "status": "awaiting_scores",
            "highest_score": None,
            "lowest_score": None,
            "largest_margin": None,
            "smallest_margin": None,
        }
    completed = [game for game in scoreboard if game.get("winner")]
    return {
        "status": "scoring_available",
        "highest_score": max(scores, key=lambda row: row["points"]),
        "lowest_score": min(scores, key=lambda row: row["points"]),
        "largest_margin": max(completed, key=lambda row: row["margin"], default=None),
        "smallest_margin": min(completed, key=lambda row: row["margin"], default=None),
    }


def _division_summary(
    snapshot: dict[str, Any],
    matchups: list[dict[str, Any]],
    scoreboard: list[dict[str, Any]],
    league_median: dict[str, Any],
    teams: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rosters = {
        int(row["roster_id"]): row for row in (snapshot.get("rosters") or [])
    }
    league = snapshot.get("league") or {}
    metadata = league.get("metadata") or {}
    outcomes: dict[int, str] = {}
    for game in scoreboard:
        if game.get("winner"):
            outcomes[int(game["winner"]["roster_id"])] = "win"
            outcomes[int(game["loser"]["roster_id"])] = "loss"
        else:
            for team in game.get("teams") or []:
                outcomes[int(team["roster_id"])] = "tie"
    median_results = {
        int(row["roster_id"]): row["result"]
        for row in league_median.get("results") or []
    }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for matchup in matchups:
        roster_id = int(matchup["roster_id"])
        raw_division = (rosters.get(roster_id, {}).get("settings") or {}).get(
            "division"
        )
        division = str(raw_division) if raw_division is not None else "unassigned"
        grouped[division].append(
            {
                **teams[roster_id],
                "points": _number(matchup.get("points")),
                "head_to_head_result": outcomes.get(roster_id),
                "median_result": median_results.get(roster_id),
            }
        )
    if not grouped or set(grouped) == {"unassigned"}:
        return []

    summaries = []
    for division, rows in grouped.items():
        summaries.append(
            {
                "division_id": division,
                "division_name": str(
                    metadata.get(f"division_{division}") or f"Division {division}"
                ),
                "teams": rows,
                "average_points": round(
                    sum(row["points"] for row in rows) / len(rows), 2
                ),
                "head_to_head_record": {
                    "wins": sum(row["head_to_head_result"] == "win" for row in rows),
                    "losses": sum(row["head_to_head_result"] == "loss" for row in rows),
                    "ties": sum(row["head_to_head_result"] == "tie" for row in rows),
                },
                "above_median_teams": sum(
                    row["median_result"] == "win" for row in rows
                )
                if league_median.get("enabled")
                else None,
                "highest_scoring_team": max(rows, key=lambda row: row["points"]),
            }
        )
    summaries.sort(key=lambda row: (-row["average_points"], row["division_id"]))
    for rank, summary in enumerate(summaries, start=1):
        summary["weekly_scoring_rank"] = rank
    return summaries


def _flagship_supplement(
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    rankings: dict[str, Any],
) -> dict[str, Any] | None:
    context = snapshot.get("flagship_sleeper")
    if not context:
        return None

    schedule_source = context.get("schedule") or {}
    schedule_weeks = schedule_source.get("weeks") or {}
    league = snapshot.get("league") or {}
    settings = league.get("settings") or {}
    playoff_week_start = int(settings.get("playoff_week_start") or 15)
    regular_season_end = max(1, playoff_week_start - 1)
    decoded_schedule = {
        str(week): _schedule_pairings(rows, teams)
        for week, rows in sorted(
            schedule_weeks.items(), key=lambda item: int(item[0])
        )
    }
    schedule_strength = _schedule_strength(
        schedule_weeks,
        snapshot,
        teams,
        rankings,
        regular_season_end,
    )

    return {
        "source_status": {
            "schedule": schedule_source.get("status", "not_collected"),
            "transactions": (context.get("transactions") or {}).get(
                "status", "not_collected"
            ),
            "drafts": (context.get("drafts") or {}).get(
                "status", "not_collected"
            ),
            "playoff_brackets": (context.get("playoff_brackets") or {}).get(
                "status", "not_collected"
            ),
            "next_week_projections": (
                context.get("next_week_projections") or {}
            ).get("status", "not_collected"),
        },
        "schedule": {
            "weeks_collected": len(schedule_weeks),
            "regular_season_end": regular_season_end,
            "games_by_week": decoded_schedule,
            "strength": schedule_strength,
            "division_context": _division_schedule_context(
                schedule_weeks,
                snapshot,
                teams,
                rankings,
                regular_season_end,
                schedule_strength,
            ),
        },
        "current_week_lineups": _matchup_lineups(snapshot, teams),
        "season_records": _season_records(
            schedule_weeks, snapshot, teams, int(snapshot.get("week") or 0)
        ),
        "next_week": _next_week_preview(snapshot, teams, decoded_schedule),
        "draft_archive": _draft_archive(snapshot, teams),
        "playoff_brackets": _decoded_brackets(context, teams),
        "transaction_ledger": _transaction_ledger(snapshot, teams),
        "traded_pick_ledger": _decoded_traded_picks(snapshot, teams),
        "roster_availability": _roster_availability(snapshot, teams),
    }


def _schedule_pairings(
    rows: list[dict[str, Any]], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("matchup_id")].append(row)
    games = []
    for matchup_id, sides in grouped.items():
        if matchup_id is None or len(sides) != 2:
            continue
        games.append(
            {
                "matchup_id": matchup_id,
                "teams": [
                    {
                        **_team_for(teams, int(side["roster_id"])),
                        "points": round(_number(side.get("points")), 2),
                    }
                    for side in sorted(sides, key=lambda row: int(row["roster_id"]))
                ],
            }
        )
    return sorted(games, key=lambda row: str(row["matchup_id"]))


def _matchup_lineups(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    league = snapshot.get("league") or {}
    slots = starter_slots(league)
    scoring = league.get("scoring_settings") or {}
    players = snapshot.get("players") or {}
    projections = (
        ((snapshot.get("ranking_inputs") or {}).get("sleeper_projections") or {}).get(
            "players"
        )
        or {}
    )
    rosters = {
        int(row["roster_id"]): row for row in snapshot.get("rosters") or []
    }
    rows = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup["roster_id"])
        roster = rosters.get(roster_id, {})
        starters = [str(player_id) for player_id in matchup.get("starters") or []]
        excluded = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in (roster.get(key) or [])
        }
        points = _points_map(matchup)

        def player_row(player_id: str, slot: str | None = None) -> dict[str, Any]:
            row = {
                "player_id": player_id,
                "player": _player_name(player_id, players),
                "position": (players.get(player_id) or {}).get("position"),
                "points": round(_number(points.get(player_id)), 2),
                "projected_points": _projected_player_points(
                    projections.get(player_id) or {}, scoring
                ),
            }
            if slot is not None:
                row["slot"] = slot
            return row

        bench = [
            str(player_id)
            for player_id in matchup.get("players") or []
            if str(player_id) not in set(starters) | excluded
        ]
        starter_rows = [
            player_row(player_id, slots[index] if index < len(slots) else "STARTER")
            for index, player_id in enumerate(starters)
        ]
        bench_rows = sorted(
            (player_row(player_id) for player_id in bench),
            key=lambda row: (-row["points"], row["player"]),
        )
        rows.append(
            {
                **_team_for(teams, roster_id),
                "actual_points": round(_number(matchup.get("points")), 2),
                "submitted_projection": round(
                    sum(row["projected_points"] for row in starter_rows), 2
                ),
                "starters": starter_rows,
                "bench": bench_rows,
            }
        )
    return sorted(rows, key=lambda row: row["team"].casefold())


def _season_records(
    schedule_weeks: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    reviewed_week: int,
) -> dict[str, Any]:
    players = snapshot.get("players") or {}
    team_scores = []
    margins = []
    player_scores = []
    starter_scores = []
    for raw_week, rows in schedule_weeks.items():
        week = int(raw_week)
        if week > reviewed_week or not any(_number(row.get("points")) for row in rows):
            continue
        games: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            roster_id = int(row["roster_id"])
            team_scores.append(
                {
                    "week": week,
                    **_team_for(teams, roster_id),
                    "points": round(_number(row.get("points")), 2),
                }
            )
            games[row.get("matchup_id")].append(row)
            point_map = _points_map(row)
            starters = {str(player_id) for player_id in row.get("starters") or []}
            for player_id, points in point_map.items():
                player = players.get(player_id) or {}
                record = {
                    "week": week,
                    **_team_for(teams, roster_id),
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "position": player.get("position"),
                    "points": round(points, 2),
                }
                player_scores.append(record)
                if player_id in starters:
                    starter_scores.append(record)
        for sides in games.values():
            if len(sides) != 2:
                continue
            ordered = sorted(
                sides, key=lambda row: _number(row.get("points")), reverse=True
            )
            if _number(ordered[0].get("points")) == _number(
                ordered[1].get("points")
            ):
                continue
            winner_id = int(ordered[0]["roster_id"])
            loser_id = int(ordered[1]["roster_id"])
            margins.append(
                {
                    "week": week,
                    "winner": _team_for(teams, winner_id),
                    "loser": _team_for(teams, loser_id),
                    "margin": round(
                        _number(ordered[0].get("points"))
                        - _number(ordered[1].get("points")),
                        2,
                    ),
                    "score": [
                        round(_number(ordered[0].get("points")), 2),
                        round(_number(ordered[1].get("points")), 2),
                    ],
                }
            )
    if not team_scores:
        return {"status": "awaiting_scores"}

    by_position = {}
    positions = sorted(
        {str(row["position"]) for row in starter_scores if row.get("position")}
    )
    for position in positions:
        by_position[position] = max(
            (row for row in starter_scores if row.get("position") == position),
            key=lambda row: row["points"],
        )
    return {
        "status": "calculated",
        "weeks_with_scores": len({row["week"] for row in team_scores}),
        "highest_team_score": max(team_scores, key=lambda row: row["points"]),
        "lowest_team_score": min(team_scores, key=lambda row: row["points"]),
        "largest_margin": max(margins, key=lambda row: row["margin"], default=None),
        "closest_finish": min(margins, key=lambda row: row["margin"], default=None),
        "highest_player_score": max(
            player_scores, key=lambda row: row["points"], default=None
        ),
        "highest_started_player_score": max(
            starter_scores, key=lambda row: row["points"], default=None
        ),
        "started_player_records_by_position": by_position,
    }


def _next_week_preview(
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    decoded_schedule: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source = (snapshot.get("flagship_sleeper") or {}).get(
        "next_week_projections"
    ) or {}
    next_week = source.get("week")
    if next_week is None:
        return {"status": source.get("status", "not_collected"), "week": None}

    league = snapshot.get("league") or {}
    scoring = league.get("scoring_settings") or {}
    slots = starter_slots(league)
    players = snapshot.get("players") or {}
    projections = source.get("players") or {}
    team_projections: dict[int, dict[str, Any]] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster["roster_id"])
        excluded = {
            str(player_id)
            for key in ("reserve", "taxi")
            for player_id in (roster.get(key) or [])
        }
        roster_ids = [
            str(player_id)
            for player_id in roster.get("players") or []
            if str(player_id) not in excluded
        ]
        projected_points = {
            player_id: _projected_player_points(
                projections.get(player_id) or {}, scoring
            )
            for player_id in roster_ids
        }
        submitted = [str(player_id) for player_id in roster.get("starters") or []]
        optimal_points, _ = optimal_lineup(
            roster_ids, projected_points, slots, players
        )
        team_projections[roster_id] = {
            "submitted_projection": round(
                sum(projected_points.get(player_id, 0.0) for player_id in submitted),
                2,
            ),
            "optimal_projection": round(optimal_points, 2),
        }

    games = []
    for game in decoded_schedule.get(str(next_week)) or []:
        games.append(
            {
                "matchup_id": game["matchup_id"],
                "teams": [
                    {
                        **team,
                        **team_projections.get(int(team["roster_id"]), {}),
                    }
                    for team in game["teams"]
                ],
            }
        )
    return {
        "status": source.get("status", "not_collected"),
        "week": next_week,
        "games": games,
    }


def _schedule_strength(
    schedule_weeks: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    rankings: dict[str, Any],
    regular_season_end: int,
) -> list[dict[str, Any]]:
    power_rows = (rankings.get("data_power_ranking") or {}).get("rows") or []
    strength_rank = {
        int(row["roster_id"]): int(
            row.get("dynasty_starter_strength_rank")
            or row.get("optimal_starting_lineup_projection_rank")
            or row.get("rank")
            or 0
        )
        for row in power_rows
    }
    reviewed_week = int(snapshot.get("week") or 0)
    opponents: dict[int, dict[str, list[int]]] = defaultdict(
        lambda: {"full": [], "completed": [], "remaining": []}
    )
    for raw_week, rows in schedule_weeks.items():
        week = int(raw_week)
        if week > regular_season_end:
            continue
        grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[row.get("matchup_id")].append(row)
        week_complete = week < reviewed_week or (
            week == reviewed_week and any(_number(row.get("points")) for row in rows)
        )
        for sides in grouped.values():
            if len(sides) != 2:
                continue
            first = int(sides[0]["roster_id"])
            second = int(sides[1]["roster_id"])
            if second in strength_rank:
                opponents[first]["full"].append(strength_rank[second])
                opponents[first]["completed" if week_complete else "remaining"].append(
                    strength_rank[second]
                )
            if first in strength_rank:
                opponents[second]["full"].append(strength_rank[first])
                opponents[second]["completed" if week_complete else "remaining"].append(
                    strength_rank[first]
                )

    results = []
    for roster_id in sorted(teams):
        buckets = opponents[roster_id]

        def average(values: list[int]) -> float | None:
            return round(sum(values) / len(values), 3) if values else None

        results.append(
            {
                **_team_for(teams, roster_id),
                "full_schedule_average_opponent_rank": average(buckets["full"]),
                "completed_average_opponent_rank": average(buckets["completed"]),
                "remaining_average_opponent_rank": average(buckets["remaining"]),
                "completed_games": len(buckets["completed"]),
                "remaining_games": len(buckets["remaining"]),
            }
        )
    for field, rank_field in (
        ("full_schedule_average_opponent_rank", "full_schedule_difficulty_rank"),
        ("remaining_average_opponent_rank", "remaining_schedule_difficulty_rank"),
    ):
        ordered = sorted(
            (row for row in results if row[field] is not None),
            key=lambda row: (row[field], row["team"].casefold()),
        )
        for rank, row in enumerate(ordered, start=1):
            row[rank_field] = rank
    return sorted(
        results,
        key=lambda row: (
            row.get("remaining_schedule_difficulty_rank", 999),
            row["team"].casefold(),
        ),
    )


def _division_schedule_context(
    schedule_weeks: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    rankings: dict[str, Any],
    regular_season_end: int,
    schedule_strength: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    league = snapshot.get("league") or {}
    metadata = league.get("metadata") or {}
    divisions = {
        int(roster["roster_id"]): str((roster.get("settings") or {}).get("division"))
        for roster in snapshot.get("rosters") or []
        if (roster.get("settings") or {}).get("division") is not None
    }
    if not divisions:
        return []

    power_rows = (rankings.get("data_power_ranking") or {}).get("rows") or []
    power_rank = {
        int(row["roster_id"]): int(
            row.get("dynasty_starter_strength_rank")
            or row.get("optimal_starting_lineup_projection_rank")
            or row.get("rank")
            or 0
        )
        for row in power_rows
    }
    schedule_by_team = {
        int(row["roster_id"]): row for row in schedule_strength
    }
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "team_ids": [],
            "intra_division_games": 0,
            "interdivision_games": 0,
            "interdivision_wins": 0,
            "interdivision_losses": 0,
            "interdivision_ties": 0,
            "interdivision_points": 0.0,
            "interdivision_completed_games": 0,
        }
    )
    for roster_id, division in divisions.items():
        grouped[division]["team_ids"].append(roster_id)

    reviewed_week = int(snapshot.get("week") or 0)
    for raw_week, rows in schedule_weeks.items():
        week = int(raw_week)
        if week > regular_season_end:
            continue
        matchups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            matchups[row.get("matchup_id")].append(row)
        for sides in matchups.values():
            if len(sides) != 2:
                continue
            first, second = sides
            first_id = int(first["roster_id"])
            second_id = int(second["roster_id"])
            first_division = divisions.get(first_id)
            second_division = divisions.get(second_id)
            if first_division is None or second_division is None:
                continue
            if first_division == second_division:
                grouped[first_division]["intra_division_games"] += 1
                continue
            grouped[first_division]["interdivision_games"] += 1
            grouped[second_division]["interdivision_games"] += 1
            if week > reviewed_week:
                continue
            first_points = _number(first.get("points"))
            second_points = _number(second.get("points"))
            if first_points == second_points == 0:
                continue
            grouped[first_division]["interdivision_points"] += first_points
            grouped[second_division]["interdivision_points"] += second_points
            grouped[first_division]["interdivision_completed_games"] += 1
            grouped[second_division]["interdivision_completed_games"] += 1
            if first_points > second_points:
                grouped[first_division]["interdivision_wins"] += 1
                grouped[second_division]["interdivision_losses"] += 1
            elif second_points > first_points:
                grouped[second_division]["interdivision_wins"] += 1
                grouped[first_division]["interdivision_losses"] += 1
            else:
                grouped[first_division]["interdivision_ties"] += 1
                grouped[second_division]["interdivision_ties"] += 1

    results = []
    for division, values in grouped.items():
        team_ids = values.pop("team_ids")
        power_values = [power_rank[team_id] for team_id in team_ids if team_id in power_rank]
        full_schedule = [
            schedule_by_team[team_id]["full_schedule_average_opponent_rank"]
            for team_id in team_ids
            if team_id in schedule_by_team
            and schedule_by_team[team_id]["full_schedule_average_opponent_rank"]
            is not None
        ]
        remaining_schedule = [
            schedule_by_team[team_id]["remaining_average_opponent_rank"]
            for team_id in team_ids
            if team_id in schedule_by_team
            and schedule_by_team[team_id]["remaining_average_opponent_rank"]
            is not None
        ]
        completed = values["interdivision_completed_games"]
        results.append(
            {
                "division_id": division,
                "division_name": str(
                    metadata.get(f"division_{division}") or f"Division {division}"
                ),
                "teams": [_team_for(teams, team_id) for team_id in team_ids],
                "average_current_power_rank": (
                    round(sum(power_values) / len(power_values), 3)
                    if power_values
                    else None
                ),
                "full_schedule_average_opponent_rank": (
                    round(sum(full_schedule) / len(full_schedule), 3)
                    if full_schedule
                    else None
                ),
                "remaining_average_opponent_rank": (
                    round(sum(remaining_schedule) / len(remaining_schedule), 3)
                    if remaining_schedule
                    else None
                ),
                **values,
                "interdivision_average_points": (
                    round(values["interdivision_points"] / completed, 2)
                    if completed
                    else None
                ),
            }
        )

    for field, rank_field in (
        ("average_current_power_rank", "division_strength_rank"),
        ("full_schedule_average_opponent_rank", "full_schedule_difficulty_rank"),
        (
            "remaining_average_opponent_rank",
            "remaining_schedule_difficulty_rank",
        ),
    ):
        ordered = sorted(
            (row for row in results if row[field] is not None),
            key=lambda row: (row[field], row["division_name"].casefold()),
        )
        for rank, row in enumerate(ordered, start=1):
            row[rank_field] = rank
    return sorted(
        results,
        key=lambda row: (
            row.get("division_strength_rank", 999),
            row["division_name"].casefold(),
        ),
    )


def _draft_archive(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    records = (
        (((snapshot.get("flagship_sleeper") or {}).get("drafts") or {}).get(
            "records"
        ))
        or []
    )
    archive = []
    for record in records:
        draft = record.get("draft") or {}
        picks = sorted(
            record.get("picks") or [], key=lambda pick: int(pick.get("pick_no") or 0)
        )
        first_round = []
        for pick in picks:
            if int(pick.get("round") or 0) != 1:
                continue
            roster_id = int(pick.get("roster_id") or 0)
            player_id = str(pick.get("player_id") or "")
            metadata = pick.get("metadata") or {}
            name = _player_name(player_id, players)
            if name == player_id:
                name = " ".join(
                    value
                    for value in (
                        str(metadata.get("first_name") or "").strip(),
                        str(metadata.get("last_name") or "").strip(),
                    )
                    if value
                ) or player_id
            first_round.append(
                {
                    "pick_no": pick.get("pick_no"),
                    "round": pick.get("round"),
                    "draft_slot": pick.get("draft_slot"),
                    **_team_for(teams, roster_id),
                    "player_id": player_id,
                    "player": name,
                    "position": metadata.get("position"),
                    "nfl_team": metadata.get("team"),
                }
            )
        archive.append(
            {
                "draft_id": draft.get("draft_id"),
                "name": (draft.get("metadata") or {}).get("name"),
                "season": draft.get("season"),
                "type": draft.get("type"),
                "status": draft.get("status"),
                "rounds": (draft.get("settings") or {}).get("rounds"),
                "pick_count": len(picks),
                "first_round": first_round,
                "traded_pick_count": len(record.get("traded_picks") or []),
            }
        )
    return archive


def _decoded_brackets(
    context: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    source = context.get("playoff_brackets") or {}

    def decode(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decoded = []
        for row in rows:
            item = dict(row)
            for field in ("t1", "t2", "w", "l"):
                roster_id = row.get(field)
                item[f"{field}_team"] = (
                    _team_for(teams, int(roster_id))["team"]
                    if roster_id is not None
                    else None
                )
            decoded.append(item)
        return decoded

    return {
        "status": source.get("status", "not_collected"),
        "winners": decode(source.get("winners") or []),
        "losers": decode(source.get("losers") or []),
    }


def _transaction_ledger(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    source = (snapshot.get("flagship_sleeper") or {}).get("transactions") or {}
    transaction_weeks = source.get("weeks") or {}
    raw_records: dict[str, dict[str, Any]] = {}
    by_week = []
    for raw_week, rows in sorted(
        transaction_weeks.items(), key=lambda item: int(item[0])
    ):
        complete = [row for row in rows if row.get("status") == "complete"]
        by_week.append({"week": int(raw_week), "completed": len(complete)})
        for index, transaction in enumerate(complete):
            key = str(
                transaction.get("transaction_id")
                or f"week-{raw_week}-transaction-{index}"
            )
            raw_records[key] = transaction
    if not transaction_weeks:
        for index, transaction in enumerate(snapshot.get("transactions") or []):
            key = str(
                transaction.get("transaction_id") or f"current-transaction-{index}"
            )
            raw_records[key] = transaction

    records = _decoded_transactions(snapshot, teams, list(raw_records.values()))
    collected = datetime.fromisoformat(
        str(snapshot.get("collected_at") or "").replace("Z", "+00:00")
    )
    if collected.tzinfo is None:
        collected = collected.replace(tzinfo=timezone.utc)
    cutoff_ms = int((collected - timedelta(days=7)).timestamp() * 1000)
    recent = [row for row in records if int(row.get("created") or 0) >= cutoff_ms]
    return {
        "status": source.get("status", "current_week_only"),
        "weeks_collected": len(transaction_weeks),
        "by_week": by_week,
        "season_summary": {
            "completed": len(records),
            "trades": sum(row["type"] == "trade" for row in records),
            "waivers": sum(row["type"] == "waiver" for row in records),
            "free_agents": sum(row["type"] == "free_agent" for row in records),
        },
        "records": records,
        "recent_window_days": 7,
        "recent_records": recent,
    }


def _decoded_transactions(
    snapshot: dict[str, Any],
    teams: dict[int, dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    records = []
    for transaction in transactions:
        created = int(transaction.get("created") or 0)
        if transaction.get("status") != "complete":
            continue
        adds = transaction.get("adds") or {}
        drops = transaction.get("drops") or {}
        player_moves = []
        for player_id in sorted(set(adds) | set(drops)):
            from_roster = int(drops[player_id]) if player_id in drops else None
            to_roster = int(adds[player_id]) if player_id in adds else None
            player_moves.append(
                {
                    "player_id": str(player_id),
                    "player": _player_name(str(player_id), players),
                    "from_team": (
                        _team_for(teams, from_roster)["team"]
                        if from_roster is not None
                        else "Free agency"
                    ),
                    "to_team": (
                        _team_for(teams, to_roster)["team"]
                        if to_roster is not None
                        else "Free agency"
                    ),
                }
            )
        records.append(
            {
                "transaction_id": transaction.get("transaction_id"),
                "type": transaction.get("type"),
                "created": created,
                "occurred_at": (
                    datetime.fromtimestamp(created / 1000, timezone.utc).isoformat()
                    if created
                    else None
                ),
                "teams": [
                    _team_for(teams, int(roster_id))["team"]
                    for roster_id in transaction.get("roster_ids") or []
                ],
                "player_moves": player_moves,
                "draft_picks": [
                    {
                        "season": pick.get("season"),
                        "round": pick.get("round"),
                        "original_team": _team_for(
                            teams, int(pick.get("roster_id") or 0)
                        )["team"],
                        "from_team": _team_for(
                            teams, int(pick.get("previous_owner_id") or 0)
                        )["team"],
                        "to_team": _team_for(
                            teams, int(pick.get("owner_id") or 0)
                        )["team"],
                    }
                    for pick in transaction.get("draft_picks") or []
                ],
                "faab_bid": (transaction.get("settings") or {}).get("waiver_bid"),
                "faab_traded": transaction.get("waiver_budget") or [],
            }
        )
    return sorted(records, key=lambda row: row["created"], reverse=True)


def _decoded_traded_picks(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "season": pick.get("season"),
            "round": pick.get("round"),
            "original_team": _team_for(
                teams, int(pick.get("roster_id") or 0)
            )["team"],
            "previous_team": _team_for(
                teams, int(pick.get("previous_owner_id") or 0)
            )["team"],
            "current_team": _team_for(
                teams, int(pick.get("owner_id") or 0)
            )["team"],
        }
        for pick in snapshot.get("traded_picks") or []
    ]


def _roster_availability(
    snapshot: dict[str, Any], teams: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    alerts = []
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster["roster_id"])
        for player_id in roster.get("players") or []:
            player = players.get(str(player_id)) or {}
            status = str(player.get("status") or "")
            injury = player.get("injury_status")
            practice = player.get("practice_participation")
            if not injury and not practice and status.casefold() in {"", "active"}:
                continue
            alerts.append(
                {
                    **_team_for(teams, roster_id),
                    "player_id": str(player_id),
                    "player": _player_name(str(player_id), players),
                    "position": player.get("position"),
                    "nfl_team": player.get("team"),
                    "status": status or None,
                    "injury_status": injury,
                    "practice_participation": practice,
                    "injury_start_date": player.get("injury_start_date"),
                    "depth_chart_order": player.get("depth_chart_order"),
                }
            )
    return sorted(alerts, key=lambda row: (row["team"].casefold(), row["player"]))


def _team_for(
    teams: dict[int, dict[str, Any]], roster_id: int
) -> dict[str, Any]:
    return teams.get(
        roster_id,
        {
            "roster_id": roster_id,
            "team": f"Roster {roster_id}",
            "owner": f"Roster {roster_id}",
        },
    )


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
