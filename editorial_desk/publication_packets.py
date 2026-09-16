from __future__ import annotations

from typing import Any

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

IDP_POSITIONS = {"DL", "DE", "DT", "NT", "LB", "DB", "CB", "S"}


def build_publication_packet(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    publication_config: PublicationConfig,
    phase: str,
    chronicle_history: dict[str, Any] | None = None,
    chronicle_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    departments: list[dict[str, Any]] = []
    for contract in publication_config.contracts_for(phase):
        result = _resolve_feature(
            contract.feature,
            snapshot,
            dossier,
            chronicle_history=chronicle_history,
            chronicle_events=chronicle_events,
        )
        blocked_reason, warnings = evaluate_dependencies(contract, snapshot)
        if blocked_reason:
            result = unavailable(contract.feature, blocked_reason)
        degraded = bool(result.degraded or (warnings and result.status != "unavailable"))
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

    required_unavailable = [
        row
        for row in departments
        if row["required_in_phase"] and row["status"] == "unavailable"
    ]
    return {
        "schema_version": 1,
        "publication_key": publication_config.key,
        "publication": publication_config.name,
        "phase": phase,
        "week": snapshot.get("week"),
        "status": "unavailable" if required_unavailable else "ready",
        "departments": departments,
    }


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
        return _value_result(feature, dossier.get("ranking_movement") or dossier.get("rankings"))
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
            if str(position).upper() in IDP_POSITIONS
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
            value = {**value, "records": list(dossier.get("weekly_records") or [])}
        return ready(feature, value)
    if feature == "workload_stat_lines":
        return workload_stat_lines(snapshot)
    if feature == "game_window_context":
        return game_window_context(snapshot, dossier, chronicle_events)
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
        return _list_result(feature, snapshot.get("transactions") or [])
    if feature == "draft_results" or feature == "draft_board":
        result = draft_results(snapshot)
        return _rename_result(result, feature)
    if feature == "draft_adp_value":
        return draft_adp_value(snapshot)
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

    direct = _direct_feature_value(feature, snapshot, dossier)
    if direct is not _MISSING:
        return _value_result(feature, direct)
    return unavailable(feature, f"No neutral producer is implemented for {feature}")


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
        if not records:
            return ready_no_items("next_matchups", reason="No next-week matchups returned")
        return ready("next_matchups", records)
    if isinstance(source, list):
        return _list_result("next_matchups", source)
    return unavailable("next_matchups", "Next-week matchup source had an unsupported shape")


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
