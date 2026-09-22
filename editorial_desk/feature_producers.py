from __future__ import annotations

from collections import defaultdict
from typing import Any

from .feature_models import FeatureResult, ready, ready_no_items, unavailable
from .metrics import _eligible, starter_slots
from .preseason_features import (
    draft_adp_value,
    draft_results,
    dynasty_market,
    future_pick_ledger,
    keeper_value,
    offense_defense_splits,
    positional_strength,
    recruiting_class,
    rookie_draft,
    roster_age,
    streaming_roster_state,
)


def result_flipping_decisions(
    snapshot: dict[str, Any], dossier: dict[str, Any]
) -> list[dict[str, Any]]:
    games = _game_context(dossier)
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = _int(matchup.get("roster_id"))
        game = games.get(roster_id)
        if not game or game["result"] != "loss":
            continue
        points = _points_map(matchup)
        team_points = _number(matchup.get("points"))
        for candidate in _legal_start_bench_pairs(snapshot, matchup):
            starter_points = _number(points.get(candidate["starter_id"]))
            bench_points = _number(points.get(candidate["bench_id"]))
            swing = bench_points - starter_points
            if swing <= 0:
                continue
            hypothetical = team_points + swing
            if hypothetical <= game["opponent_points"]:
                continue
            rows.append(
                {
                    "roster_id": roster_id,
                    "team": _team_name(snapshot, roster_id),
                    "opponent": game.get("opponent"),
                    "slot": candidate["slot"],
                    "started_player_id": candidate["starter_id"],
                    "started_player": _player_name(candidate["starter_id"], players),
                    "started_points": round(starter_points, 2),
                    "bench_player_id": candidate["bench_id"],
                    "bench_player": _player_name(candidate["bench_id"], players),
                    "bench_points": round(bench_points, 2),
                    "point_swing": round(swing, 2),
                    "actual_team_points": round(team_points, 2),
                    "opponent_points": round(game["opponent_points"], 2),
                    "hypothetical_team_points": round(hypothetical, 2),
                    "would_flip_result": True,
                }
            )
    return sorted(rows, key=lambda row: (-row["point_swing"], row["team"]))


def winning_decision_swings(
    snapshot: dict[str, Any], dossier: dict[str, Any]
) -> list[dict[str, Any]]:
    games = _game_context(dossier)
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = _int(matchup.get("roster_id"))
        game = games.get(roster_id)
        if not game or game["result"] != "win":
            continue
        points = _points_map(matchup)
        best: dict[str, Any] | None = None
        for candidate in _legal_start_bench_pairs(snapshot, matchup):
            starter_points = _number(points.get(candidate["starter_id"]))
            bench_points = _number(points.get(candidate["bench_id"]))
            swing = starter_points - bench_points
            if swing < game["margin"]:
                continue
            row = {
                "roster_id": roster_id,
                "team": _team_name(snapshot, roster_id),
                "opponent": game.get("opponent"),
                "slot": candidate["slot"],
                "started_player_id": candidate["starter_id"],
                "started_player": _player_name(candidate["starter_id"], players),
                "started_points": round(starter_points, 2),
                "bench_player_id": candidate["bench_id"],
                "bench_player": _player_name(candidate["bench_id"], players),
                "bench_points": round(bench_points, 2),
                "point_swing": round(swing, 2),
                "victory_margin": round(game["margin"], 2),
                "protected_win": True,
            }
            if best is None or (row["point_swing"], row["started_points"]) > (
                best["point_swing"],
                best["started_points"],
            ):
                best = row
        if best is not None:
            rows.append(best)
    return sorted(rows, key=lambda row: (-row["point_swing"], row["team"]))


def league_wide_started_mvp(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [row for row in _player_weeks(snapshot) if row["status"] == "STARTED"]
    return max(candidates, key=_player_rank_key, default=None)


def divisional_started_mvps(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rosters = {
        _int(row.get("roster_id")): row for row in snapshot.get("rosters") or []
    }
    metadata = (snapshot.get("league") or {}).get("metadata") or {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _player_weeks(snapshot):
        if row["status"] != "STARTED":
            continue
        division = (rosters.get(row["roster_id"], {}).get("settings") or {}).get(
            "division"
        )
        if division is None:
            continue
        division_id = str(division)
        grouped[division_id].append(
            {
                **row,
                "division_id": division_id,
                "division_name": str(
                    metadata.get(f"division_{division_id}") or f"Division {division_id}"
                ),
                "gold_foil": False,
            }
        )
    mvps = [
        max(rows, key=_player_rank_key)
        for _, rows in sorted(grouped.items(), key=lambda item: item[0])
        if rows
    ]
    if mvps:
        gold = max(mvps, key=_player_rank_key)
        gold["gold_foil"] = True
    return mvps


def position_leaders(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    leaders: dict[str, dict[str, Any]] = {}
    for row in _player_weeks(snapshot):
        position = str(row.get("position") or "").strip()
        if not position:
            continue
        current = leaders.get(position)
        if current is None or _player_rank_key(row) > _player_rank_key(current):
            leaders[position] = row
    return leaders


def bench_leader(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [row for row in _player_weeks(snapshot) if row["status"] == "BENCH"]
    winner = max(candidates, key=_player_rank_key, default=None)
    if winner is None or winner["points"] <= 0:
        return None
    return winner


def bench_blast(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    return bench_leader(snapshot)


def waiver_impact(
    snapshot: dict[str, Any], dossier: dict[str, Any]
) -> list[dict[str, Any]]:
    games = _game_context(dossier)
    matchups = {
        _int(row.get("roster_id")): row for row in snapshot.get("matchups") or []
    }
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for transaction in snapshot.get("transactions") or []:
        if transaction.get("status") != "complete":
            continue
        transaction_type = str(transaction.get("type") or "")
        if transaction_type not in {"waiver", "free_agent"}:
            continue
        for player_id, raw_roster_id in (transaction.get("adds") or {}).items():
            roster_id = _int(raw_roster_id)
            matchup = matchups.get(roster_id) or {}
            starter_ids = {str(value) for value in matchup.get("starters") or []}
            points = _number(_points_map(matchup).get(str(player_id)))
            game = games.get(roster_id) or {}
            margin = _number(game.get("margin"))
            started = str(player_id) in starter_ids
            rows.append(
                {
                    "transaction_id": transaction.get("transaction_id"),
                    "transaction_type": transaction_type,
                    "roster_id": roster_id,
                    "team": _team_name(snapshot, roster_id),
                    "player_id": str(player_id),
                    "player": _player_name(str(player_id), players),
                    "faab": (transaction.get("settings") or {}).get("waiver_bid"),
                    "started": started,
                    "points": round(points, 2),
                    "victory_margin": round(margin, 2) if game.get("result") == "win" else None,
                    "result_relevant": bool(
                        started
                        and game.get("result") == "win"
                        and points >= margin
                    ),
                }
            )
    return rows


def record_watch(
    dossier: dict[str, Any], chronicle_history: dict[str, Any] | None
) -> dict[str, Any]:
    history = chronicle_history or {}
    coverage = history.get("coverage") or {}
    return {
        "records": list(dossier.get("record_watch") or []),
        "coverage_complete": bool(coverage.get("complete", True)),
        "coverage_warnings": list(coverage.get("warnings") or []),
    }


def workload_stat_lines(snapshot: dict[str, Any]) -> FeatureResult:
    """Return real-NFL workload leaders from players actually rostered in this league."""
    source = ((snapshot.get("nfl_context") or {}).get("player_stats") or {})
    if source.get("status") != "available":
        return unavailable(
            "workload_stat_lines",
            source.get("reason") or "NFL player-stat source unavailable",
        )
    records = [row for row in source.get("records") or [] if isinstance(row, dict)]
    if not records:
        return ready_no_items(
            "workload_stat_lines", reason="NFL player-stat source returned no records"
        )

    roster_by_player: dict[str, int] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = _int(roster.get("roster_id"))
        for player_id in roster.get("players") or []:
            roster_by_player[str(player_id)] = roster_id

    players = snapshot.get("players") or {}
    gsis_to_sleeper = {
        str(player.get("gsis_id")): str(player_id)
        for player_id, player in players.items()
        if player.get("gsis_id")
    }
    rostered_records: list[dict[str, Any]] = []
    for row in records:
        raw_player_id = str(row.get("player_id") or "")
        sleeper_id = gsis_to_sleeper.get(raw_player_id)
        if sleeper_id is None and raw_player_id in roster_by_player:
            sleeper_id = raw_player_id
        if not sleeper_id or sleeper_id not in roster_by_player:
            continue
        rostered_records.append(
            {
                **row,
                "sleeper_player_id": sleeper_id,
                "fantasy_team": _team_name(snapshot, roster_by_player[sleeper_id]),
            }
        )
    if not rostered_records:
        return ready_no_items(
            "workload_stat_lines",
            reason="No rostered players matched the weekly NFL player-stat source",
        )

    categories = {
        "passing_attempts": "attempts",
        "passing_yards": "passing_yards",
        "passing_touchdowns": "passing_tds",
        "rushing_attempts": "carries",
        "rushing_yards": "rushing_yards",
        "rushing_touchdowns": "rushing_tds",
        "receptions": "receptions",
        "targets": "targets",
        "receiving_yards": "receiving_yards",
        "receiving_touchdowns": "receiving_tds",
    }
    leaders: dict[str, dict[str, Any]] = {}
    for label, field in categories.items():
        candidates = [row for row in rostered_records if row.get(field) is not None]
        if candidates:
            leaders[label] = max(
                candidates,
                key=lambda row: (
                    _number(row.get(field)),
                    str(row.get("player_display_name") or row.get("player_name") or ""),
                ),
            )
    if not leaders:
        return ready_no_items(
            "workload_stat_lines",
            reason="Rostered NFL player-stat records contained no workload fields",
        )
    return ready("workload_stat_lines", leaders)


def game_window_context(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    chronicle_events: list[dict[str, Any]] | None = None,
) -> FeatureResult:
    windows = [
        row
        for row in ((snapshot.get("nfl_context") or {}).get("game_windows") or [])
        if isinstance(row, dict) and row.get("name")
    ]
    if not windows:
        monday_rows = _monday_timing_context(dossier)
        if monday_rows:
            return ready("game_window_context", monday_rows)
        return ready_no_items(
            "game_window_context", reason="No identifiable final game window"
        )

    players = snapshot.get("players") or {}
    matchups = {
        _int(row.get("roster_id")): row for row in snapshot.get("matchups") or []
    }
    opponents = _opponent_roster_ids(snapshot)
    games = _game_context(dossier)
    events = chronicle_events or []
    rows: list[dict[str, Any]] = []

    for window in windows:
        window_name = str(window.get("name"))
        window_player_ids = {str(value) for value in window.get("player_ids") or []}
        live_event = _latest_live_window_event(events, window_name)
        evidence = (live_event or {}).get("evidence") or {}
        live_scores = {
            str(key): _number(value) for key, value in (evidence.get("scores") or {}).items()
        }
        live_remaining = {
            str(key): [str(value) for value in values or []]
            for key, values in (evidence.get("remaining_starters") or {}).items()
        }

        for roster_id, matchup in matchups.items():
            starters = [str(value) for value in matchup.get("starters") or []]
            reconstructed_remaining = [
                player_id for player_id in starters if player_id in window_player_ids
            ]
            remaining = live_remaining.get(str(roster_id), reconstructed_remaining)
            if not remaining:
                continue

            opponent_id = opponents.get(roster_id)
            opponent_matchup = matchups.get(opponent_id or -1) or {}
            final_score = _number(matchup.get("points"))
            opponent_final_score = _number(opponent_matchup.get("points"))
            points = _points_map(matchup)
            opponent_points = _points_map(opponent_matchup)
            opponent_starters = [
                str(value) for value in opponent_matchup.get("starters") or []
            ]
            opponent_remaining = live_remaining.get(
                str(opponent_id),
                [player_id for player_id in opponent_starters if player_id in window_player_ids],
            )

            if live_event and str(roster_id) in live_scores:
                provenance = "observed_live"
                observed_at = live_event.get("observed_at")
                pre_window_score = live_scores[str(roster_id)]
                opponent_pre_window_score = live_scores.get(
                    str(opponent_id), opponent_final_score
                )
                window_points = final_score - pre_window_score
            else:
                provenance = "reconstructed"
                observed_at = None
                window_points = sum(_number(points.get(player_id)) for player_id in remaining)
                opponent_window_points = sum(
                    _number(opponent_points.get(player_id))
                    for player_id in opponent_remaining
                )
                pre_window_score = final_score - window_points
                opponent_pre_window_score = opponent_final_score - opponent_window_points

            game = games.get(roster_id) or {}
            rows.append(
                {
                    "window": window_name,
                    "roster_id": roster_id,
                    "team": _team_name(snapshot, roster_id),
                    "opponent_roster_id": opponent_id,
                    "opponent": game.get("opponent") or _team_name(snapshot, opponent_id or 0),
                    "provenance": provenance,
                    "observed_at": observed_at,
                    "pre_window_score": round(pre_window_score, 2),
                    "opponent_pre_window_score": round(opponent_pre_window_score, 2),
                    "remaining_players": [
                        {
                            "player_id": player_id,
                            "player": _player_name(player_id, players),
                            "points": round(_number(points.get(player_id)), 2),
                        }
                        for player_id in remaining
                    ],
                    "window_points": round(window_points, 2),
                    "final_score": round(final_score, 2),
                    "opponent_final_score": round(opponent_final_score, 2),
                    "final_margin": round(abs(final_score - opponent_final_score), 2),
                    "trailing_before_window": pre_window_score < opponent_pre_window_score,
                    "final_result": game.get("result"),
                    "swung_result": bool(
                        pre_window_score < opponent_pre_window_score
                        and final_score > opponent_final_score
                    ),
                }
            )

    if not rows:
        return ready_no_items(
            "game_window_context", reason="No fantasy starters remained in the final game window"
        )
    return ready(
        "game_window_context",
        sorted(rows, key=lambda row: (row["window"], row["roster_id"])),
    )


def _monday_timing_context(dossier: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize the dossier's already-built Monday timing evidence for newspapers."""
    monday = ((dossier.get("game_timing") or {}).get("monday") or {})
    rows: list[dict[str, Any]] = []
    for matchup in monday.get("matchups") or []:
        if not matchup.get("completed") or not matchup.get("day_was_active"):
            continue
        winner_name = str(matchup.get("final_winner") or "")
        loser_name = str(matchup.get("final_loser") or "")
        sides = {
            str(side.get("team") or ""): side
            for side in matchup.get("teams") or []
        }
        winner = sides.get(winner_name) or {}
        loser = sides.get(loser_name) or {}
        if not winner_name or not loser_name:
            continue
        rows.append(
            {
                "window": "Monday",
                "matchup_id": matchup.get("matchup_id"),
                "team": winner_name,
                "opponent": loser_name,
                "provenance": "reconstructed_from_game_timing",
                "pre_window_score": matchup.get("winner_score_before_day"),
                "opponent_pre_window_score": matchup.get("loser_score_before_day"),
                "remaining_players": [
                    {
                        "player_id": player.get("player_id"),
                        "player": player.get("player"),
                        "points": player.get("fantasy_points"),
                        "nfl_stat_line": player.get("nfl_stat_line"),
                    }
                    for player in winner.get("players") or []
                ],
                "opponent_remaining_players": [
                    {
                        "player_id": player.get("player_id"),
                        "player": player.get("player"),
                        "points": player.get("fantasy_points"),
                        "nfl_stat_line": player.get("nfl_stat_line"),
                    }
                    for player in loser.get("players") or []
                ],
                "window_points": winner.get("day_points"),
                "opponent_window_points": loser.get("day_points"),
                "final_score": winner.get("points"),
                "opponent_final_score": loser.get("points"),
                "final_margin": matchup.get("final_margin"),
                "trailing_before_window": bool(
                    (matchup.get("winner_score_before_day") or 0)
                    < (matchup.get("loser_score_before_day") or 0)
                ),
                "final_result": "win",
                "swung_result": bool(matchup.get("lead_changed_on_day")),
                "tie_broken": bool(matchup.get("tie_broken_on_day")),
                "margin_supplied_by_window": bool(matchup.get("margin_supplied_by_day")),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            not row.get("swung_result"),
            float(row.get("final_margin") or 999999),
            str(row.get("matchup_id") or ""),
        ),
    )


def _latest_live_window_event(
    events: list[dict[str, Any]], window_name: str
) -> dict[str, Any] | None:
    candidates = [
        event
        for event in events
        if event.get("event_type") == "MATCHUP_SCORE_SNAPSHOT"
        and event.get("provenance") == "observed_live"
        and str((event.get("evidence") or {}).get("window") or "") == window_name
    ]
    return max(candidates, key=lambda row: str(row.get("observed_at") or ""), default=None)


def _opponent_roster_ids(snapshot: dict[str, Any]) -> dict[int, int]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for matchup in snapshot.get("matchups") or []:
        matchup_id = matchup.get("matchup_id")
        if matchup_id is None:
            continue
        grouped[str(matchup_id)].append(_int(matchup.get("roster_id")))
    opponents: dict[int, int] = {}
    for roster_ids in grouped.values():
        if len(roster_ids) != 2:
            continue
        first, second = roster_ids
        opponents[first] = second
        opponents[second] = first
    return opponents


def _legal_start_bench_pairs(
    snapshot: dict[str, Any], matchup: dict[str, Any]
) -> list[dict[str, str]]:
    players = snapshot.get("players") or {}
    slots = starter_slots(snapshot.get("league") or {})
    rosters = {
        _int(row.get("roster_id")): row for row in snapshot.get("rosters") or []
    }
    roster_id = _int(matchup.get("roster_id"))
    roster = rosters.get(roster_id) or {}
    starters = [str(value) for value in matchup.get("starters") or []]
    inactive = {
        str(value)
        for key in ("reserve", "taxi")
        for value in roster.get(key) or []
    }
    starter_set = set(starters)
    bench = [
        str(value)
        for value in matchup.get("players") or []
        if str(value) not in starter_set | inactive
    ]
    pairs: list[dict[str, str]] = []
    for index, starter_id in enumerate(starters[: len(slots)]):
        slot = slots[index]
        for bench_id in bench:
            if _eligible(bench_id, players.get(bench_id) or {}, slot):
                pairs.append(
                    {
                        "slot": slot,
                        "starter_id": starter_id,
                        "bench_id": bench_id,
                    }
                )
    return pairs


def _player_weeks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    rows: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = _int(matchup.get("roster_id"))
        starters = {str(value) for value in matchup.get("starters") or []}
        points = _points_map(matchup)
        for player_id in matchup.get("players") or []:
            player_id = str(player_id)
            player = players.get(player_id) or {}
            rows.append(
                {
                    "roster_id": roster_id,
                    "team": _team_name(snapshot, roster_id),
                    "player_id": player_id,
                    "player": _player_name(player_id, players),
                    "position": _position(player),
                    "points": round(_number(points.get(player_id)), 2),
                    "status": "STARTED" if player_id in starters else "BENCH",
                }
            )
    return rows


def _game_context(dossier: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for game in dossier.get("scoreboard") or []:
        winner = game.get("winner") or {}
        loser = game.get("loser") or {}
        if winner.get("roster_id") is not None:
            result[_int(winner.get("roster_id"))] = {
                "result": "win",
                "margin": _number(game.get("margin")),
                "opponent": loser.get("team"),
                "opponent_points": _number(loser.get("points")),
            }
        if loser.get("roster_id") is not None:
            result[_int(loser.get("roster_id"))] = {
                "result": "loss",
                "margin": _number(game.get("margin")),
                "opponent": winner.get("team"),
                "opponent_points": _number(winner.get("points")),
            }
    return result


def _team_name(snapshot: dict[str, Any], roster_id: int) -> str:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    for roster in snapshot.get("rosters") or []:
        if _int(roster.get("roster_id")) != roster_id:
            continue
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        return str(
            metadata.get("team_name")
            or owner.get("display_name")
            or owner.get("username")
            or f"Roster {roster_id}"
        )
    return f"Roster {roster_id}"


def _player_name(player_id: str, players: dict[str, Any]) -> str:
    player = players.get(str(player_id)) or {}
    return str(
        player.get("full_name")
        or " ".join(
            value
            for value in [player.get("first_name"), player.get("last_name")]
            if value
        ).strip()
        or player_id
    )


def _position(player: dict[str, Any]) -> str:
    return str(
        player.get("position")
        or ((player.get("fantasy_positions") or [""])[0])
        or ""
    )


def _points_map(matchup: dict[str, Any]) -> dict[str, float]:
    raw = matchup.get("players_points") or matchup.get("players_points_dict") or {}
    return {str(key): _number(value) for key, value in raw.items()}


def _player_rank_key(row: dict[str, Any]) -> tuple[float, str]:
    return (_number(row.get("points")), str(row.get("player") or ""))


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
