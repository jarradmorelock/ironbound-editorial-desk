from __future__ import annotations

from typing import Any

from .publication_policy import publication_view, divisions_disabled, DIVISION_FEATURES
from .config import PublicationConfig
from .feature_models import FeatureResult, ready, ready_no_items, unavailable
from .feature_producers import (
    bench_blast,
    bench_leader,
    divisional_started_mvps,
    draft_adp_value,
    draft_results,
    dynasty_market,
    future_pick_ledger,
    game_window_context,
    keeper_value,
    league_wide_started_mvp,
    offense_defense_splits,
    positional_strength,
    position_leaders,
    recruiting_class,
    record_watch,
    result_flipping_decisions,
    roster_age,
    rookie_draft,
    streaming_roster_state,
    waiver_impact,
    winning_decision_swings,
    workload_stat_lines,
)
from .health import build_roster_health
from .publication_contracts import evaluate_dependencies
from .preseason_features import (
    draft_bargains,
    draft_market,
    draft_reach,
    draft_value_board,
)
from .preseason_support import preseason_support

POSITION_BOARD_POSITIONS = {
    "QB", "RB", "WR", "TE", "LB", "DL", "DE", "DT", "NT", "DB", "CB", "S"
}


def build_publication_packet(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    publication_config: PublicationConfig,
    phase: str,
    chronicle_history: dict[str, Any] | None = None,
    chronicle_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy = {"publication_key": publication_config.key}
    snapshot = publication_view(snapshot, policy)
    dossier = publication_view(dossier, policy)
    departments: list[dict[str, Any]] = []
    blocked_features: set[str] = set()
    for contract in publication_config.contracts_for(phase):
        if divisions_disabled(policy) and contract.feature in DIVISION_FEATURES:
            continue
        result = _resolve_feature(
            contract.feature,
            snapshot,
            dossier,
            chronicle_history=chronicle_history,
            chronicle_events=chronicle_events,
        )
        blocked_reason, warnings = evaluate_dependencies(contract, snapshot)
        if blocked_reason:
            blocked_features.add(contract.feature)
            result = unavailable(contract.feature, blocked_reason)
        degraded = bool(result.degraded or warnings)
        departments.append(
            {
                "feature": contract.feature,
                "display_name": contract.display_name,
                "required_in_phase": contract.required_in_phase,
                "status": result.status,
                "data": result.data,
                "reason": result.reason,
                "freshness": result.freshness,
                "degraded": degraded,
                "dependency_warnings": warnings,
            }
        )

    blocking_unavailable = [
        row
        for row in departments
        if row["required_in_phase"]
        and row["status"] == "unavailable"
        and (row["feature"] in blocked_features or not row["degraded"])
    ]
    degraded_departments = [row for row in departments if row["degraded"]]
    packet_status = (
        "unavailable"
        if blocking_unavailable
        else "degraded"
        if degraded_departments
        else "ready"
    )
    return publication_view({
        "schema_version": 1,
        "publication_key": publication_config.key,
        "publication": publication_config.name,
        "phase": phase,
        "week": snapshot.get("week"),
        "status": packet_status,
        "departments": departments,
    }, policy)


def _resolve_feature(
    feature: str,
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    *,
    chronicle_history: dict[str, Any] | None,
    chronicle_events: list[dict[str, Any]] | None,
) -> FeatureResult:
    if feature in {"weekly_results", "final_scorecard"}:
        return _value_result(feature, dossier.get("scoreboard"))
    if feature in {"standings", "official_table"}:
        standings = dossier.get("standings")
        if standings is None:
            standings = (dossier.get("rankings") or {}).get("official_standings")
        return _value_result(feature, standings)
    if feature == "ranking_movement":
        return _ranking_wire(dossier)
    if feature == "division_metrics":
        return _value_result(feature, dossier.get("division_metrics") or dossier.get("divisions"))
    if feature == "lineup_efficiency":
        return _value_result(feature, dossier.get("lineup_efficiency"))
    if feature == "lineup_flip_candidates":
        return _list_result(feature, result_flipping_decisions(snapshot, dossier))
    if feature == "manager_decision_evidence":
        return _list_result(feature, winning_decision_swings(snapshot, dossier))
    if feature == "league_wide_started_mvp":
        return _single_result(feature, league_wide_started_mvp(snapshot))
    if feature == "divisional_started_mvps":
        return _list_result(feature, divisional_started_mvps(snapshot))
    if feature == "player_position_leaders":
        return _mapping_result(feature, position_leaders(snapshot))
    if feature == "idp_position_metrics":
        leaders = {
            position: row
            for position, row in position_leaders(snapshot).items()
            if str(position).upper() in POSITION_BOARD_POSITIONS
        }
        return _mapping_result(feature, leaders)
    if feature == "bench_leaders":
        return _single_result(feature, bench_leader(snapshot))
    if feature == "bench_blast":
        return _single_result(feature, bench_blast(snapshot))
    if feature == "waiver_impact":
        return _list_result(feature, waiver_impact(snapshot, dossier))
    if feature == "record_watch":
        value = record_watch(dossier, chronicle_history)
        if not value.get("records") and dossier.get("weekly_records"):
            value = {
                **value,
                "records": _weekly_record_rows(dossier.get("weekly_records")),
            }
        return ready(feature, value)
    if feature == "workload_stat_lines":
        return workload_stat_lines(snapshot)
    if feature == "game_window_context":
        return game_window_context(snapshot, dossier, chronicle_events)
    if feature in {"opening_statement_inputs", "lead_inputs"}:
        return _weekly_lead_inputs(feature, snapshot, dossier, chronicle_events)
    if feature == "hollywood_board":
        return _hollywood_board_inputs(snapshot, dossier, chronicle_events)
    if feature == "weekly_briefs":
        return _weekly_briefs(snapshot, dossier, chronicle_events)
    if feature == "health_status":
        return _health_result(snapshot)
    if feature == "manager_of_week":
        return _single_result(feature, (dossier.get("awards") or {}).get("manager_of_the_week"))
    if feature in {"bad_beat", "escape_artist"}:
        return _single_result(feature, (dossier.get("awards") or {}).get(feature))
    if feature in {"weekly_honors", "weekly_honors_support"}:
        return _mapping_result(feature, _weekly_honors(dossier))
    if feature == "weekly_desk_honors":
        honors = _weekly_honors(dossier)
        saturday = {
            "benchwarmer": honors.get("benchwarmer"),
            "rookie": honors.get("rookie"),
            "free_agent": honors.get("free_agent"),
            "bad_beat": honors.get("bad_beat"),
        }
        return _mapping_result(feature, {key: value for key, value in saturday.items() if value is not None})
    if feature == "rookie_of_week":
        return _single_result(feature, (dossier.get("weekly_features") or {}).get("rookie_of_the_week"))
    if feature == "free_agent_of_week":
        return _single_result(feature, (dossier.get("weekly_features") or {}).get("free_agent_of_the_week"))
    if feature == "transactions":
        return _list_result(feature, _newspaper_transactions(snapshot))
    if feature == "draft_results" or feature == "draft_board":
        result = draft_results(snapshot)
        return _rename_result(result, feature)
    if feature == "draft_adp_value":
        return draft_adp_value(snapshot)
    if feature == "draft_value_board":
        return draft_value_board(snapshot)
    if feature == "draft_reach":
        return draft_reach(snapshot)
    if feature == "draft_bargains":
        return draft_bargains(snapshot)
    if feature == "draft_market":
        return draft_market(snapshot)
    if feature in {"keeper_costs", "keeper_value"}:
        result = keeper_value(snapshot)
        return _rename_result(result, feature)
    if feature == "roster_age":
        return roster_age(snapshot)
    if feature == "positional_strength":
        return positional_strength(snapshot)
    if feature == "future_picks":
        result = future_pick_ledger(snapshot)
        return _rename_result(result, feature)
    if feature == "rookie_draft":
        return rookie_draft(snapshot)
    if feature == "recruiting_class":
        return recruiting_class(snapshot)
    if feature in {"dynasty_market", "dynasty_market_values"}:
        result = dynasty_market(snapshot)
        return _rename_result(result, feature)
    if feature == "offense_defense_splits":
        return offense_defense_splits(snapshot)
    if feature == "streaming_roster_state":
        return streaming_roster_state(snapshot)
    if feature == "next_matchups":
        return _next_matchups_result(snapshot)

    support = preseason_support(feature, snapshot, dossier)
    if support is not None:
        return support

    direct = _direct_feature_value(feature, snapshot, dossier)
    if direct is not _MISSING:
        return _value_result(feature, direct)
    return unavailable(feature, f"No neutral producer is implemented for {feature}")


def _weekly_lead_inputs(
    feature: str,
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    chronicle_events: list[dict[str, Any]] | None,
) -> FeatureResult:
    scoreboard = list(dossier.get("scoreboard") or [])
    teams = [team for game in scoreboard for team in (game.get("teams") or [])]
    lineup = list(dossier.get("lineup_efficiency") or [])
    timing = dossier.get("game_timing") or {}
    starter_timing = list(timing.get("starter_game_days") or [])
    late_window = game_window_context(snapshot, dossier, chronicle_events)

    values = {
        "high_score": max(teams, key=lambda row: float(row.get("points") or 0), default=None),
        "largest_margin": max(scoreboard, key=lambda row: float(row.get("margin") or 0), default=None),
        "closest_finish": min(scoreboard, key=lambda row: float(row.get("margin") or 0), default=None),
        "high_score_efficiency": max(
            lineup,
            key=lambda row: (
                float(row.get("actual_points") or 0),
                float(row.get("efficiency") or 0),
            ),
            default=None,
        ),
        "late_window_swings": [
            row
            for row in (late_window.data or [])
            if isinstance(row, dict) and row.get("swung_result")
        ]
        if late_window.status == "ready"
        else [],
        "projection_overperformers": sorted(
            (
                row
                for row in starter_timing
                if row.get("projection_difference") is not None
                and float(row.get("projection_difference") or 0) > 0
            ),
            key=lambda row: float(row.get("projection_difference") or 0),
            reverse=True,
        ),
    }
    usable = {key: value for key, value in values.items() if value not in (None, [], {})}
    if not usable:
        return ready_no_items(feature, reason="No deterministic weekly lead inputs qualified")
    return ready(feature, usable)


def _hollywood_board_inputs(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    chronicle_events: list[dict[str, Any]] | None,
) -> FeatureResult:
    lead = _weekly_lead_inputs("lead_inputs", snapshot, dossier, chronicle_events)
    flips = result_flipping_decisions(snapshot, dossier)
    late = game_window_context(snapshot, dossier, chronicle_events)
    late_swings = [
        row
        for row in (late.data or [])
        if isinstance(row, dict) and row.get("swung_result")
    ] if late.status == "ready" else []

    board = {
        "top_billing": lead.data if lead.status == "ready" else None,
        "scene_stealer": league_wide_started_mvp(snapshot),
        "plot_twist": flips[0] if flips else (late_swings[0] if late_swings else None),
        "bad_beat": (dossier.get("awards") or {}).get("bad_beat"),
    }
    if all(value is None for value in board.values()):
        return ready_no_items("hollywood_board", reason="No Hollywood Board facts qualified")
    return ready("hollywood_board", board)


def _weekly_briefs(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    chronicle_events: list[dict[str, Any]] | None,
) -> FeatureResult:
    """Build compact team dailies instead of duplicating the health department."""
    efficiency = {
        int(row.get("roster_id") or 0): row
        for row in dossier.get("lineup_efficiency") or []
    }
    health_source = dossier.get("roster_health") or build_roster_health(snapshot)
    health_by_roster: dict[int, list[str]] = {}
    if health_source.get("status") == "available":
        for row in health_source.get("players") or []:
            if not _meaningful_health_row(row):
                continue
            health_by_roster.setdefault(int(row.get("roster_id") or 0), []).append(
                str(row.get("player") or row.get("player_id") or "")
            )
    transactions = _newspaper_transactions(snapshot)
    tx_by_roster: dict[int, int] = {}
    for row in transactions:
        for roster_id in row.get("roster_ids") or []:
            tx_by_roster[int(roster_id)] = tx_by_roster.get(int(roster_id), 0) + 1

    rows: list[dict[str, Any]] = []
    for game in dossier.get("scoreboard") or []:
        teams = game.get("teams") or []
        if len(teams) != 2:
            continue
        for side in teams:
            roster_id = int(side.get("roster_id") or 0)
            opponent = next(
                (row for row in teams if int(row.get("roster_id") or 0) != roster_id),
                {},
            )
            eff = efficiency.get(roster_id) or {}
            winner = game.get("winner") or {}
            rows.append(
                {
                    "roster_id": roster_id,
                    "team": side.get("team"),
                    "opponent": opponent.get("team"),
                    "result": (
                        "W"
                        if int(winner.get("roster_id") or 0) == roster_id
                        else "L"
                        if winner
                        else "T"
                    ),
                    "score": side.get("points"),
                    "opponent_score": opponent.get("points"),
                    "efficiency": eff.get("efficiency"),
                    "transactions": tx_by_roster.get(roster_id, 0),
                    "health_flags": health_by_roster.get(roster_id, []),
                }
            )
    if not rows and not transactions and not chronicle_events:
        return ready_no_items("weekly_briefs", reason="No completed team dailies qualified")
    bundle = {
        "teams": sorted(rows, key=lambda row: str(row.get("team") or "").casefold()),
        "transactions": transactions,
        "health": [
            row
            for row in health_source.get("players") or []
            if _meaningful_health_row(row)
        ] if health_source.get("status") == "available" else [],
        "chronicle_events": list(chronicle_events or []),
    }
    return ready(
        "weekly_briefs",
        bundle,
        degraded=health_source.get("status") != "available",
        reason=(
            None
            if health_source.get("status") == "available"
            else str(health_source.get("error") or "Roster health source unavailable")
        ),
    )


def _weekly_honors(dossier: dict[str, Any]) -> dict[str, Any]:
    awards = dossier.get("awards") or {}
    weekly = dossier.get("weekly_features") or {}
    values = {
        "manager": awards.get("manager_of_the_week"),
        "bad_beat": awards.get("bad_beat"),
        "escape_artist": awards.get("escape_artist"),
        "benchwarmer": weekly.get("benchwarmer_of_the_week") or awards.get("bench_mvp"),
        "rookie": weekly.get("rookie_of_the_week"),
        "free_agent": weekly.get("free_agent_of_the_week"),
    }
    return {key: value for key, value in values.items() if value is not None}


def _next_matchups_result(snapshot: dict[str, Any]) -> FeatureResult:
    source = snapshot.get("next_matchups")
    if source is None:
        return unavailable("next_matchups", "Next-week Sleeper matchups were not collected")
    if isinstance(source, dict) and "status" in source:
        if source.get("status") != "available":
            return unavailable(
                "next_matchups",
                str(source.get("reason") or source.get("error") or "Next-week matchups unavailable"),
            )
        records = list(source.get("records") or [])
        next_week = source.get("week")
    elif isinstance(source, list):
        records = list(source)
        next_week = None
    else:
        return unavailable("next_matchups", "Next-week matchup source had an unsupported shape")
    if not records:
        return ready_no_items("next_matchups", reason="No next-week matchups returned")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        matchup_id = row.get("matchup_id")
        if matchup_id is None:
            continue
        grouped.setdefault(str(matchup_id), []).append(row)
    games = []
    for matchup_id, sides in sorted(grouped.items()):
        if len(sides) != 2:
            continue
        ordered = sorted(sides, key=lambda row: int(row.get("roster_id") or 0))
        games.append(
            {
                "week": next_week,
                "matchup_id": int(matchup_id) if matchup_id.isdigit() else matchup_id,
                "teams": [
                    {
                        "roster_id": int(side.get("roster_id") or 0),
                        "team": _fantasy_team_name(snapshot, int(side.get("roster_id") or 0)),
                    }
                    for side in ordered
                ],
            }
        )
    if not games:
        return ready_no_items("next_matchups", reason="No complete next-week matchup pairs returned")
    return ready("next_matchups", games)


def _weekly_record_rows(value: Any) -> list[dict[str, Any]]:
    """Normalize the metrics weekly_records mapping into renderer-safe rows."""
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []

    rows: list[dict[str, Any]] = []
    status = value.get("status")
    for record_type in (
        "highest_score",
        "lowest_score",
        "largest_margin",
        "smallest_margin",
    ):
        record = value.get(record_type)
        if not isinstance(record, dict):
            continue
        rows.append(
            {
                "record_type": record_type,
                "status": status,
                **record,
            }
        )
    return rows


def _ranking_wire(dossier: dict[str, Any]) -> FeatureResult:
    rankings = dossier.get("rankings") or {}
    power = rankings.get("data_power_ranking") or {}
    if isinstance(power, list):
        rows = list(power)
        power_status = "calculated"
    elif isinstance(power, dict):
        rows = list(power.get("rows") or [])
        power_status = str(power.get("status") or "Data Power ranking inputs unavailable")
    else:
        rows = []
        power_status = "Data Power ranking inputs unavailable"
    if not rows:
        return unavailable("ranking_movement", power_status)
    previous = {
        int(row.get("roster_id") or 0): row
        for row in ((rankings.get("prior_published_ranking") or {}).get("rows") or [])
        if row.get("roster_id") is not None
    }
    rendered = []
    for index, row in enumerate(rows, start=1):
        roster_id = int(row.get("roster_id") or 0)
        current_rank = int(row.get("rank") or index)
        prior = previous.get(roster_id) or {}
        previous_rank = prior.get("rank")
        movement = (
            int(previous_rank) - current_rank
            if previous_rank is not None
            else None
        )
        rendered.append(
            {
                "roster_id": roster_id,
                "team": row.get("team"),
                "rank": current_rank,
                "previous_rank": previous_rank,
                "movement": movement,
                "movement_status": (
                    "available" if previous_rank is not None else "prior_publication_unavailable"
                ),
                "consensus_rank_average": row.get("consensus_rank_average"),
                "starter_strength_rank": row.get("dynasty_starter_strength_rank"),
                "projection_rank": row.get("optimal_starting_lineup_projection_rank"),
            }
        )
    return ready(
        "ranking_movement",
        rendered,
        reason=(
            None
            if previous
            else "Current Data Power order is available; prior published ranking baseline is not yet archived, so movement is not claimed."
        ),
    )


def _newspaper_transactions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    players = snapshot.get("players") or {}
    rows = []
    for transaction in snapshot.get("transactions") or []:
        if str(transaction.get("status") or "").casefold() not in {"complete", "completed"}:
            continue
        adds = transaction.get("adds") or {}
        drops = transaction.get("drops") or {}
        moves = []
        for player_id in sorted(set(adds) | set(drops)):
            moves.append(
                {
                    "player_id": str(player_id),
                    "player": str((players.get(str(player_id)) or {}).get("full_name") or player_id),
                    "from_roster_id": drops.get(player_id),
                    "from_team": (
                        _fantasy_team_name(snapshot, int(drops[player_id]))
                        if player_id in drops
                        else "Free agency"
                    ),
                    "to_roster_id": adds.get(player_id),
                    "to_team": (
                        _fantasy_team_name(snapshot, int(adds[player_id]))
                        if player_id in adds
                        else "Free agency"
                    ),
                }
            )
        rows.append(
            {
                "transaction_id": transaction.get("transaction_id"),
                "type": transaction.get("type"),
                "roster_ids": [int(value) for value in transaction.get("roster_ids") or []],
                "moves": moves,
                "faab": (transaction.get("settings") or {}).get("waiver_bid"),
                "draft_picks": transaction.get("draft_picks") or [],
            }
        )
    return rows


def _fantasy_team_name(snapshot: dict[str, Any], roster_id: int) -> str:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    roster = next(
        (row for row in snapshot.get("rosters") or [] if int(row.get("roster_id") or 0) == int(roster_id)),
        {},
    )
    owner = users.get(str(roster.get("owner_id"))) or {}
    metadata = owner.get("metadata") or {}
    return str(metadata.get("team_name") or owner.get("display_name") or f"Roster {roster_id}")


def _meaningful_health_row(row: dict[str, Any]) -> bool:
    return bool(
        row.get("on_ir")
        or row.get("injury_status")
        or row.get("injury")
        or row.get("report_status")
        or row.get("practice_participation")
    )


def _health_result(snapshot: dict[str, Any]) -> FeatureResult:
    health = build_roster_health(snapshot)
    if health.get("status") != "available":
        return unavailable(
            "health_status",
            str(health.get("error") or "Sleeper health source unavailable"),
        )
    players = list(health.get("players") or [])
    if not players:
        return ready_no_items("health_status", reason="No roster health flags returned")
    return ready("health_status", players)


_MISSING = object()


def _direct_feature_value(feature: str, snapshot: dict[str, Any], dossier: dict[str, Any]) -> Any:
    aliases = {
        "league_median": ("league_median", "median"),
        "weekly_ledger": ("weekly_ledger", "weekly_records"),
        "opening_statement_inputs": ("opening_statement_inputs",),
        "lead_inputs": ("lead_inputs",),
        "hollywood_board": ("hollywood_board", "weekly_hollywood_board"),
        "weekly_briefs": ("weekly_briefs", "dailies"),
        "late_show_context": ("late_show_context", "game_timing"),
        "production_delays": ("production_delays",),
        "dailies": ("dailies",),
    }
    for key in aliases.get(feature, (feature,)):
        if key in dossier:
            return dossier[key]
        if key in snapshot:
            return snapshot[key]
    return _MISSING


def _rename_result(result: FeatureResult, feature: str) -> FeatureResult:
    return FeatureResult(
        feature=feature,
        status=result.status,
        data=result.data,
        reason=result.reason,
        freshness=result.freshness,
        degraded=result.degraded,
    )


def _value_result(feature: str, value: Any) -> FeatureResult:
    if value is None:
        return unavailable(feature, f"{feature} source value is unavailable")
    if value in ([], {}, ()):
        return ready_no_items(feature, reason=f"{feature} has no qualifying items")
    return ready(feature, value)


def _list_result(feature: str, rows: list[Any]) -> FeatureResult:
    if not rows:
        return ready_no_items(feature, reason=f"{feature} has no qualifying items")
    return ready(feature, rows)


def _mapping_result(feature: str, rows: dict[str, Any]) -> FeatureResult:
    if not rows:
        return ready_no_items(feature, reason=f"{feature} has no qualifying items")
    return ready(feature, rows)


def _single_result(feature: str, row: Any) -> FeatureResult:
    if row is None:
        return ready_no_items(feature, reason=f"{feature} has no qualifying item")
    return ready(feature, row)
