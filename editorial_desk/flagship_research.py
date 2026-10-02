from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .context_events import build_context_events
from .honors import research_honors
from .weekly_features import _overall_player_of_week
from .external_inputs import ExternalEditorialInputs
from .chronicle_queries import ChronicleQueries
from .canonical_evidence import build_canonical_league_evidence


FLAGSHIP_PUBLICATIONS = {"ironbound_weekly", "unbound_weekly"}
CORE_POSITIONS = ("QB", "RB", "WR", "TE")


FLAGSHIP_DISPLAY_NAMES = {
    "ironbound_weekly": {
        "CONTENTS": "INSIDE THE ISSUE",
        "USAGE_DESK": "THE USAGE DESK",
        "ROSTER_HEALTH": "ROSTER HEALTH",
        "MARKET_DESK": "THE TRANSACTION DESK",
        "PRESSURE_POINTS": "PRESSURE POINTS",
        "DIVISION_ROAD_AHEAD": "DIVISION OF DEATH",
    },
    "unbound_weekly": {
        "CONTENTS": "INSIDE THE ISSUE",
        "USAGE_DESK": "USAGE DESK",
        "ROSTER_HEALTH": "AVAILABILITY WATCH",
        "MARKET_DESK": "MARKET MOVES",
        "PRESSURE_POINTS": "THE PRESSURE POINTS",
        "DIVISION_ROAD_AHEAD": "UNDER TENSION",
    },
}


def flagship_editorial_spine(publication_key: str, week: int) -> list[dict[str, Any]]:
    """Return the shared 25-page flagship architecture with branded labels."""
    names = FLAGSHIP_DISPLAY_NAMES.get(publication_key) or {}
    next_week = int(week) + 1
    modules = [
        ("COVER", "COVER"),
        ("CONTENTS", names.get("CONTENTS", "INSIDE THE ISSUE")),
        ("LEAD_ART_OPENER", "LEAD FEATURE OPENER"),
        ("LEAD_FEATURE", "LEAD FEATURE"),
        ("GAME_REPORTS", f"WEEK {week} GAME REPORTS"),
        ("GAME_REPORTS", f"WEEK {week} GAME REPORTS"),
        ("GAME_REPORTS", f"WEEK {week} GAME REPORTS"),
        ("SECONDARY_FEATURE", "SECONDARY FEATURE"),
        ("USAGE_DESK", names.get("USAGE_DESK", "USAGE DESK")),
        ("ROSTER_HEALTH", names.get("ROSTER_HEALTH", "ROSTER HEALTH")),
        ("MARKET_DESK", names.get("MARKET_DESK", "MARKET MOVES")),
        ("MANAGER_HONORS", "MANAGER HONORS & CUMULATIVE TEAM STATS"),
        ("PLAYER_HONORS", "PLAYER HONORS & SEASON LEADERS"),
        ("ROOKIE_WATCH", "ROOKIE WATCH"),
        ("PLAYOFF_FORECAST", f"WEEK {next_week} PLAYOFF FORECAST"),
        ("POWER_RANKINGS", f"WEEK {next_week} POWER RANKINGS"),
        ("POWER_BOARD", "THE POWER BOARD"),
        ("POWER_BOARD", "THE POWER BOARD"),
        ("POWER_BOARD", "THE POWER BOARD"),
        ("POWER_BOARD", "THE POWER BOARD"),
        ("PRESSURE_POINTS", names.get("PRESSURE_POINTS", "PRESSURE POINTS")),
        ("FULL_SLATE", f"WEEK {next_week} FULL SLATE"),
        ("DIVISION_ROAD_AHEAD", names.get("DIVISION_ROAD_AHEAD", "DIVISION / ROAD AHEAD")),
        ("WEEK_AHEAD", f"WEEK {next_week} PREVIEW"),
        ("SOURCES", "SOURCES & MODEL NOTES"),
    ]
    return [
        {"page": page, "module": module, "display_name": display,
         **({"game_report_numbers": [(page - 5) * 2 + 1, (page - 5) * 2 + 2]} if module == "GAME_REPORTS" else {}),
         **({"ranks": list(range((page - 17) * 4 + 1, (page - 17) * 4 + 5))} if module == "POWER_BOARD" else {})}
        for page, (module, display) in enumerate(modules, start=1)
    ]


def flagship_style_guidance() -> dict[str, Any]:
    return {
        "stats_support_thesis": True,
        "result_vs_process": True,
        "role_vs_efficiency": True,
        "expectation_vs_outcome": True,
        "state_uncertainty": True,
        "actionable_consequence": True,
        "avoid_chart_in_prose": True,
        "guidance": [
            "Use numbers as evidence for an argument, not as a paragraph-shaped table.",
            "Separate what happened from whether the underlying role or process changed.",
            "Explain why a workload, market move, injury timeline, or model component changes the fantasy read.",
            "Compare outcome with prior expectation when the evidence supports it.",
            "Preserve uncertainty; one game or one report is not automatically a trend.",
            "Assess role sustainability using opportunity and workload evidence; distinguish volume from efficiency and touchdown variance.",
            "Describe market and model expectations separately and explain opportunity cost where supported.",
            "Observed status intervals do not prove exact announcement times or manager intent; chronology alone is not causation.",
            "End analytical passages with the consequence for the manager, roster, matchup, or next decision.",
        ],
    }


def build_flagship_research_packet(
    snapshot: dict[str, Any],
    dossier: dict[str, Any],
    story: dict[str, Any] | None,
    external: ExternalEditorialInputs,
    *,
    history_root: Path,
    chronicle: ChronicleQueries | None = None,
    publication_assets: dict[str, dict[str, Any]] | None = None,
    beat_report: dict[str, Any] | None = None,
    roster_market: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build the deterministic factual contract that feeds flagship production.

    This object is intentionally pre-editorial. Code discovers facts, leaders,
    candidates, source gaps, and Tuesday handoff inputs. The AI/editor chooses
    story emphasis and writes prose later.
    """
    editorial = snapshot.get("editorial") or {}
    profile = editorial.get("publication_profile") or {}
    publication_key = str(profile.get("key") or "")
    if publication_key not in FLAGSHIP_PUBLICATIONS:
        return None

    season = str(
        (snapshot.get("nfl_state") or {}).get("season")
        or (snapshot.get("league") or {}).get("season")
        or dossier.get("season")
        or ""
    )
    week = int(snapshot.get("week") or dossier.get("week") or 0)
    league_key = str(editorial.get("league_key") or "")
    history = _season_dossiers(history_root, season, league_key, week)
    canonical_evidence = build_canonical_league_evidence(snapshot, chronicle)

    honors_research = research_honors(snapshot, dossier, external, history, chronicle)
    games = _game_research(snapshot, dossier)
    player_boards = _season_player_boards(
        list(canonical_evidence.get("player_weeks") or []),
        snapshot,
    )
    if beat_report is not None:
        games = _attach_beat_context_to_games(games, beat_report)
    weekly = dossier.get("weekly_features") or {}
    intelligence = dossier.get("nfl_game_intelligence") or {}
    manager_awards = _manager_weekly_awards(
        dossier,
        history,
        current_week=week,
        manager_of_the_week=honors_research.get("manager_of_the_week"),
        entering_records=(canonical_evidence.get("entering_records") or {}).get(str(week)),
    )
    rookie_awards = _rookie_weekly_awards(weekly, snapshot, intelligence)
    health = dossier.get("roster_health") or {}

    packet: dict[str, Any] = {
        "schema_version": 1,
        "contract_version": "ironbound-production-v0.7",
        "publication_key": publication_key,
        "league_key": league_key,
        "season": season,
        "week": week,
        "information_current_through": dossier.get("information_current_through"),
        "editorial_spine": flagship_editorial_spine(publication_key, week),
        "editorial_style_guidance": flagship_style_guidance(),
        "contract_principles": {
            "deterministic_facts_first": True,
            "ai_role": "editorial selection and prose only",
            "fantasy_points_policy": (
                "Use fantasy points for matchup totals, awards, records, and "
                "result-changing lineup decisions. Use actual NFL statistics "
                "as the default description of player performance."
            ),
        },
        "game_coverage": {
            "required_matchups": 8,
            "feature_slots": 2,
            "remaining_game_writeups": 6,
            "editorial_selection_required": True,
            "games": games,
            "cover_candidates": _cover_candidates(games, dossier),
        },
        "usage_game_intelligence": {
            "source_status": intelligence.get("source_status") or {},
            "story_signals": intelligence.get("story_signals") or [],
            "actual_nfl_stat_book": intelligence.get("stat_book") or {},
        },
        "usage_desk": _usage_desk(intelligence),
        "injury_roster_health": health,
        "beat_report": beat_report,
        "context_events": build_context_events(beat_report, games),
        "roster_market": roster_market,
        "weekly_honors": {
            **honors_research,
            "overall_player_of_the_week": _attach_stat_lines(weekly.get("overall_player_of_the_week") or _overall_player_of_week(snapshot), intelligence),
            **manager_awards,
            "high_score": max((r for g in dossier.get("scoreboard") or [] for r in g.get("teams") or []), key=lambda r: float(r.get("points") or 0), default=None),
            "low_score": min((r for g in dossier.get("scoreboard") or [] for r in g.get("teams") or []), key=lambda r: float(r.get("points") or 0), default=None),
            "started_position_leaders": _attach_stat_lines(
                _distinct_started_position_leaders(
                    snapshot,
                    weekly.get("overall_player_of_the_week")
                    or _overall_player_of_week(snapshot),
                ),
                intelligence,
            ),

            **rookie_awards,
            "weekly_efficiency_top_three": weekly.get("lineup_efficiency_top_three") or [],
            "season_efficiency_top_three": _season_efficiency_top_three(
                history,
                snapshot=snapshot,
                league_key=league_key,
                season=season,
                chronicle=chronicle,
            ),
            "season_team_score_top_three": _canonical_team_score_top_three(
                canonical_evidence,
                through_week=week,
            ),
            **player_boards,
            "benchwarmer_of_the_week": _attach_stat_lines(
                weekly.get("benchwarmer_of_the_week"), intelligence
            ),
            "rookie_watch_top_five": _attach_rookie_draft_context(
                _attach_stat_lines(
                    weekly.get("rookie_watch_top_five") or [], intelligence
                ),
                snapshot,
            ),
        },
        "power_board": {
            "writeup_inputs": _power_board_inputs(
                dossier,
                external,
                snapshot=snapshot,
                league_key=league_key,
                season=season,
                chronicle=chronicle,
            ),
            "writeups_are_editorial": True,
        },
        "power_rankings_chart": {
            "status": _external_status(external.power_rankings_supplied),
            "authority": "Ironbound_power_ranks",
            "movement_policy": "Use previous_rank and movement supplied by the Power Rankings engine. Do not recalculate movement in Editorial Desk.",
            "asset_key": "power_rankings",
            "rows": [
                {
                    "franchise_key": row.franchise_key,
                    "roster_id": row.roster_id,
                    "team": row.team,
                    "rank": row.rank,
                    "previous_rank": row.previous_rank,
                    "movement": row.movement,
                    "score": row.score,
                    "components": dict(row.components),
                }
                for row in external.official_power_rankings
            ],
        },
        "playoff_odds_chart": {
            "status": _external_status(external.playoff_odds_supplied),
            "authority": "Ironbound_power_ranks",
            "asset_key": "playoff_forecast",
            "rows": [dict(row) for row in external.playoff_odds],
        },
        "remaining_schedule_strength": {
            "status": (
                "READY"
                if external.remaining_schedule_strength
                else (
                    "AWAITING_TUESDAY_INPUT"
                    if external.schema_version >= 3
                    else "LEGACY_NOT_SUPPLIED"
                )
            ),
            "authority": "Ironbound_power_ranks",
            "method": "Average remaining opponent current Power Board index; higher is harder.",
            "rows": [dict(row) for row in external.remaining_schedule_strength],
        },
        "weekly_matchup_forecast": {
            "status": (
                "READY"
                if external.weekly_matchup_forecast
                else (
                    "AWAITING_TUESDAY_INPUT"
                    if external.schema_version >= 3
                    else "LEGACY_NOT_SUPPLIED"
                )
            ),
            "authority": "Ironbound_power_ranks",
            "lineup_policy": "Projected-optimal legal lineups are selected once from pregame projections and remain fixed through the simulations. Submitted current starters do not set the line.",
            "rows": [dict(row) for row in external.weekly_matchup_forecast],
        },
        "ranking_publication_assets": {
            "authority": "Ironbound_power_ranks",
            "required": publication_assets is not None,
            "policy": "Use the supplied PNGs unchanged in the magazine. Do not redraw these charts.",
            "assets": dict(publication_assets or {}),
        },
        "tuesday_external_inputs": {
            "schema_version": external.schema_version,
            "usage": {
                "status": _optional_external_status(external.usage_supplied),
                "rows": [dict(row) for row in external.usage],
                "note": "Optional legacy/external usage input. Weekly magazine usage is sourced from nflverse inside Editorial Desk.",
            },
            "war": {
                "status": _optional_external_status(external.war_supplied),
                "rows": [dict(row) for row in external.war],
            },
            "cwar": {
                "status": _optional_external_status(external.cwar_supplied),
                "rows": [dict(row) for row in external.cwar],
            },
            "source_metadata": dict(external.source_metadata),
            "notes": list(external.notes),
        },
        "story_desk": {
            "status": (story or {}).get("status", "unavailable"),
            "candidates": (story or {}).get("candidates") or [],
        },
    }
    packet["division_outlook"] = _division_outlook(
        dossier.get("divisions") or [], packet["remaining_schedule_strength"]
    )
    context = packet["context_events"]
    for game in games:
        game["context_event_ids"] = context["by_game"].get(str(game.get("matchup_id")), [])
    for field, module in (("injury_roster_health", "ROSTER_HEALTH"), ("roster_market", "MARKET_DESK"),
                          ("usage_desk", "USAGE_DESK"), ("weekly_matchup_forecast", "FULL_SLATE")):
        if isinstance(packet.get(field), dict):
            packet[field] = {**packet[field], "context_event_ids": context["by_module"].get(module, [])}
    for row in packet["weekly_matchup_forecast"]["rows"]:
        row["context_event_ids"] = sorted(set(context["by_roster"].get(str(row.get("roster_one")), []) +
                                             context["by_roster"].get(str(row.get("roster_two")), [])))
    packet["validation"] = validate_flagship_research_packet(packet)
    return packet


def validate_flagship_research_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate contract completeness without converting missing inputs into fiction."""
    checks: list[dict[str, Any]] = []
    manual: list[str] = []
    awaiting: list[str] = []
    editorial: list[str] = []

    expected = flagship_editorial_spine(str(packet.get("publication_key") or ""), int(packet.get("week") or 0))
    structural_fields = ("page", "module", "game_report_numbers", "ranks")
    structure = lambda rows: [{key: row.get(key) for key in structural_fields} for row in rows]
    spine_ok = structure(packet.get("editorial_spine") or []) == structure(expected)
    _check(checks, "flagship_spine", spine_ok, "25-page canonical module order and allocations")
    if not spine_ok:
        manual.append("Shared flagship page structure is missing or inconsistent.")

    report_pages = [
        row for row in packet.get("editorial_spine") or [] if row.get("module") == "GAME_REPORTS"
    ]
    report_allocations = [row.get("game_report_numbers") for row in report_pages]
    allocation_ok = (
        report_allocations == [[1, 2], [3, 4], [5, 6]]
        and len(report_pages) == 3
        and int((packet.get("game_coverage") or {}).get("feature_slots") or 0) == 2
        and int((packet.get("game_coverage") or {}).get("remaining_game_writeups") or 0) == 6
    )
    _check(
        checks,
        "game_report_allocation",
        allocation_ok,
        "three pages, two reports each, six non-feature writeups"
        if allocation_ok
        else "expected report pairs 1–2, 3–4, 5–6 and 2 feature slots",
    )
    if not allocation_ok:
        manual.append(
            "Weekly results must allocate six non-feature games as two reports on each of three pages."
        )

    games = ((packet.get("game_coverage") or {}).get("games") or [])
    required_games = int((packet.get("game_coverage") or {}).get("required_matchups") or 8)
    _check(checks, "eight_matchups", len(games) == required_games, f"{len(games)}/{required_games} matchups present")
    if len(games) != required_games:
        manual.append(
            f"Expected {required_games} completed matchups but found {len(games)}. Verify Sleeper matchup collection."
        )

    duplicate_ids = _duplicates(str(row.get("matchup_id")) for row in games)
    _check(checks, "unique_matchups", not duplicate_ids, "no duplicate matchup IDs" if not duplicate_ids else f"duplicates: {', '.join(duplicate_ids)}")
    if duplicate_ids:
        manual.append("Duplicate matchup coverage must be resolved before production.")

    allowed_division_statuses = {
        "VERIFIED_DIVISIONAL",
        "VERIFIED_NON_DIVISIONAL",
        "UNAVAILABLE",
    }
    explicit_divisions = len(games) == required_games and all(
        game.get("division_status") in allowed_division_statuses for game in games
    )
    _check(
        checks,
        "game_division_evidence",
        explicit_divisions,
        "every matchup has an explicit division classification state"
        if explicit_divisions
        else "one or more matchup division states are missing/invalid",
    )
    if explicit_divisions and any(
        game.get("division_status") == "UNAVAILABLE" for game in games
    ):
        manual.append(
            "One or more matchup division identities are unavailable; verify league division data before labeling divisional games."
        )

    for game in games:
        if not game.get("starter_stat_lines"):
            manual.append(
                f"Matchup {game.get('matchup_id')}: no submitted-starter NFL stat lines matched."
            )

    usage = packet.get("usage_desk") or {}
    usage_ok = usage.get("status") == "READY"
    _check(
        checks,
        "weekly_usage",
        usage_ok,
        str(usage.get("status") or "missing"),
    )
    if not usage_ok:
        manual.append(
            "Usage Desk evidence is incomplete. Weekly player usage from nflverse "
            "player stats must be available before flagship production."
        )

    health = packet.get("injury_roster_health") or {}
    health_ok = health.get("status") == "available"
    _check(checks, "injury_health", health_ok, str(health.get("status") or "missing"))
    if not health_ok:
        manual.append("Injury / roster-health source is unavailable.")

    beat = packet.get("beat_report")
    if beat is not None and beat.get("required"):
        beat_ok = beat.get("status") == "READY"
        _check(
            checks,
            "beat_news",
            beat_ok,
            str(beat.get("status") or "missing"),
        )
        if not beat_ok:
            manual.append(
                "Beat/news ledger is unavailable or its weekly reporting window "
                "could not be verified."
            )

    market = packet.get("roster_market")
    if market is not None:
        market_ok = market.get("status") == "READY"
        _check(checks, "roster_market", market_ok, str(market.get("status") or "missing"))
        if not market_ok:
            manual.append("Roster & Market research could not be assembled deterministically.")

    honors = packet.get("weekly_honors") or {}
    for key in (
        "started_position_leaders",
        "overall_player_of_the_week",
        "most_efficient_manager",
        "high_score",
        "low_score",
        "manager_of_the_week",
        "bad_beat",
        "escape_artist",
        "season_efficiency_top_three",
        "season_team_score_top_three",
        "benchwarmer_of_the_week",
        "rookie_watch_top_five",
        "rookie_of_the_week",
        "top_rookie_starter",
    ):
        value = honors.get(key)
        ok = value is not None and (not isinstance(value, (list, dict)) or bool(value))
        _check(checks, f"honors_{key}", ok, "present" if ok else "missing/empty")
        if not ok:
            manual.append(f"Weekly Honors: {key.replace('_', ' ')} is missing or empty.")

    overall_id = str((honors.get("overall_player_of_the_week") or {}).get("player_id") or "")
    positional_ids = [
        str(row.get("player_id") or "")
        for row in (honors.get("started_position_leaders") or {}).values()
        if isinstance(row, dict)
    ]
    player_awards_distinct = bool(overall_id) and overall_id not in positional_ids and len(
        positional_ids
    ) == len(set(positional_ids)) and all(
        isinstance((honors.get("started_position_leaders") or {}).get(position), dict)
        and (honors.get("started_position_leaders") or {}).get(position, {}).get("player_id")
        for position in CORE_POSITIONS
    )
    _check(
        checks,
        "weekly_player_award_distinctness",
        player_awards_distinct,
        "overall and positional starter awards name distinct players"
        if player_awards_distinct
        else "overall and positional starter awards are missing or overlap",
    )
    if not player_awards_distinct:
        manual.append(
            "Overall and positional player awards must identify distinct eligible starters."
        )

    award_warnings = [f"{code}: {status.get('reason')}"
        for code, status in (honors.get("award_availability") or {}).items()
        if status.get("status") != "AVAILABLE"]
    rookie_disappointment_status = honors.get("rookie_disappointment_status") or {}
    if rookie_disappointment_status.get("status") != "READY":
        award_warnings.append(
            "ROOKIE_DISAPPOINTMENT: "
            + str(rookie_disappointment_status.get("reason") or "projection evidence incomplete")
        )

    division_outlook = packet.get("division_outlook") or {}
    division_summary_ready = division_outlook.get("division_status") == "READY" and bool(
        division_outlook.get("division_summaries")
    )
    _check(
        checks,
        "division_outlook_evidence",
        division_summary_ready,
        "verified division summaries are present"
        if division_summary_ready
        else "verified division summaries are unavailable",
    )
    if not division_summary_ready:
        manual.append(
            "Division of Death needs verified division-level matchup context and standings inputs."
        )

    schedule = packet.get("remaining_schedule_strength") or {}
    schedule_rows = schedule.get("rows") or []
    schedule_ready = schedule.get("status") == "READY" and len(schedule_rows) == 16
    _check(
        checks,
        "division_outlook_schedule",
        schedule_ready,
        f"{len(schedule_rows)}/16 teams with remaining-schedule strength",
    )
    if not schedule_ready:
        awaiting.append(
            "Division of Death / Road Ahead needs the complete 16-team remaining-schedule strength handoff."
        )

    season_week = int(packet.get("week") or 0)
    efficiency_rows = honors.get("season_efficiency_top_three") or []
    efficiency_coverage = (
        bool(efficiency_rows)
        and all(int(row.get("weeks") or 0) >= season_week for row in efficiency_rows)
    )
    _check(
        checks,
        "season_efficiency_history",
        efficiency_coverage,
        (
            f"complete through Week {season_week}"
            if efficiency_coverage
            else f"fewer than {season_week} finalized efficiency weeks are recorded"
        ),
    )
    if not efficiency_coverage:
        manual.append(
            "Running efficiency board is incomplete in Chronicle/history; backfill or manually verify missing completed weeks."
        )

    team_score_rows = honors.get("season_team_score_top_three") or []
    team_score_coverage = bool(team_score_rows) and all(
        int(row.get("weeks") or 0) >= season_week for row in team_score_rows
    )
    _check(
        checks,
        "season_team_score_history",
        team_score_coverage,
        (
            f"complete through Week {season_week}"
            if team_score_coverage
            else f"fewer than {season_week} finalized scoring weeks are recorded"
        ),
    )
    if not team_score_coverage:
        manual.append(
            "Cumulative team points board is incomplete in Chronicle/history; backfill or manually verify missing completed weeks."
        )

    for key, check_name, label in (
        ("player_season_top_three", "player_season_history", "Player Season Top 3"),
        ("rookie_season_leaders", "rookie_season_history", "Rookie Season Leaders"),
    ):
        board = honors.get(key) or {}
        has_applicable_positions = key == "rookie_season_leaders" or bool(
            board.get("by_position")
        )
        board_ready = board.get("status") == "READY" and has_applicable_positions
        _check(
            checks,
            check_name,
            board_ready,
            f"complete through Week {season_week}"
            if board_ready
            else str(board.get("reason") or board.get("status") or "unavailable"),
        )
        if not board_ready:
            manual.append(
                f"{label} requires complete per-player scoring history through Week {season_week}; "
                + str(board.get("reason") or "source history unavailable")
            )

    for key, label in (
        ("power_rankings_chart", "Power Rankings"),
        ("playoff_odds_chart", "Playoff Odds"),
    ):
        section = packet.get(key) or {}
        if section.get("status") != "READY":
            awaiting.append(f"{label} from Tuesday power-rankings delivery.")

    source_metadata = (packet.get("tuesday_external_inputs") or {}).get("source_metadata") or {}
    external_schema_version = int((packet.get("tuesday_external_inputs") or {}).get("schema_version") or 1)
    if external_schema_version >= 3:
        schedule = packet.get("remaining_schedule_strength") or {}
        schedule_ok = schedule.get("status") == "READY" and len(schedule.get("rows") or []) == 16
        _check(
            checks,
            "remaining_schedule_strength",
            schedule_ok,
            f"{len(schedule.get('rows') or [])}/16 teams",
        )
        if not schedule_ok:
            awaiting.append("Complete remaining-schedule strength from the Power Rankings engine.")

        weekly_forecast = packet.get("weekly_matchup_forecast") or {}
        forecast_rows = weekly_forecast.get("rows") or []
        forecast_ok = weekly_forecast.get("status") == "READY" and len(forecast_rows) == 8
        _check(
            checks,
            "weekly_matchup_forecast",
            forecast_ok,
            f"{len(forecast_rows)}/8 matchups",
        )
        if not forecast_ok:
            awaiting.append("Complete projected-optimal weekly matchup forecast from the Power Rankings engine.")
    results_through_week = source_metadata.get("results_through_week")
    if results_through_week is not None:
        try:
            results_week_value = int(results_through_week)
        except (TypeError, ValueError):
            results_week_value = None
        if results_week_value != int(packet.get("week") or 0):
            awaiting.append(
                "Current-cycle Power Rankings handoff. "
                f"Ranking engine results are through Week {results_through_week!r}, "
                f"but this packet covers Week {packet.get('week')}."
            )

    asset_section = packet.get("ranking_publication_assets") or {}
    assets = asset_section.get("assets") or {}
    if asset_section.get("required"):
        for asset_key, label in (
            ("power_rankings", "Power Rankings graphic"),
            ("playoff_forecast", "Playoff Forecast graphic"),
        ):
            asset = assets.get(asset_key) or {}
            asset_ok = asset.get("status") == "READY" and bool(asset.get("package_path"))
            _check(
                checks,
                f"asset_{asset_key}",
                asset_ok,
                str(asset.get("status") or "missing"),
            )
            if not asset_ok:
                awaiting.append(f"{label} from the Power Rankings engine.")

    editorial.extend(
        [
            "Choose the two cover-feature game slots from deterministic cover candidates.",
            "Choose one or none from the qualified rotating manager award candidates; never auto-select.",
            "Write game stories, context-box wording, headlines, Power Board writeups, and art direction from verified evidence.",
        ]
    )

    ready = not manual and not awaiting
    return {
        "contract_valid": not any(
            not row["passed"]
            for row in checks
            if row["name"]
            in {
                "flagship_spine",
                "game_report_allocation",
                "eight_matchups",
                "unique_matchups",
                "game_division_evidence",
            }
        ),
        "research_complete": ready,
        "checks": checks,
        "manual_verify": manual,
        "award_warnings": award_warnings,
        "awaiting_tuesday_input": awaiting,
        "editorial_judgment": editorial,
    }


def render_flagship_research_packet(packet: dict[str, Any]) -> str:
    lines = [
        f"# {packet.get('publication_key', 'flagship').replace('_', ' ').title()} — Week {packet.get('week')} Flagship Research",
        "",
        f"Contract: **{packet.get('contract_version')}**",
        "",
        "## RESEARCH READINESS",
        "",
    ]
    validation = packet.get("validation") or {}
    lines.append("Research complete: **" + ("YES" if validation.get("research_complete") else "NO") + "**")
    lines.append("Structural contract valid: **" + ("YES" if validation.get("contract_valid") else "NO") + "**")

    lines.extend(["", "### Manual Verification"])
    manual = validation.get("manual_verify") or []
    lines.extend(f"- {row}" for row in manual)
    if not manual:
        lines.append("- None.")

    lines.extend(["", "### Awaiting Tuesday Inputs"])
    waiting = validation.get("awaiting_tuesday_input") or []
    lines.extend(f"- {row}" for row in waiting)
    if not waiting:
        lines.append("- None.")

    lines.extend(["", "### Editorial Judgment"])
    lines.extend(f"- {row}" for row in validation.get("editorial_judgment") or [])

    lines.extend(["", "## FLAGSHIP EDITORIAL SPINE", ""])
    for row in packet.get("editorial_spine") or []:
        lines.append(
            f"- Page {int(row.get('page') or 0):02d}: {row.get('module')} — {row.get('display_name')}"
        )
    lines.extend(["", "## EDITORIAL STYLE", ""])
    for row in (packet.get("editorial_style_guidance") or {}).get("guidance") or []:
        lines.append(f"- {row}")

    coverage = packet.get("game_coverage") or {}
    lines.extend(["", "## GAME COVERAGE LEDGER", ""])
    lines.append(
        f"Cover feature slots: {coverage.get('feature_slots', 2)}; "
        f"remaining game writeups: {coverage.get('remaining_game_writeups', 6)}; "
        f"completed matchup dossiers: {len(coverage.get('games') or [])}."
    )
    lines.extend(["", "### Cover Candidates"])
    for row in coverage.get("cover_candidates") or []:
        lines.append(
            f"- {row.get('matchup')}: signal score {row.get('signal_score')}; "
            + "; ".join(row.get("reasons") or [])
        )

    for game in coverage.get("games") or []:
        lines.extend(["", f"### Matchup {game.get('matchup_id')} — {game.get('matchup')}", ""])
        lines.append(f"- Final: {game.get('scoreline')}; margin {float(game.get('margin') or 0):.2f}.")
        if game.get("division_status") == "VERIFIED_DIVISIONAL":
            lines.append(f"- Divisional matchup: verified — {game.get('division_name')}.")
        elif game.get("division_status") == "VERIFIED_NON_DIVISIONAL":
            lines.append("- Divisional matchup: verified non-divisional.")
        else:
            lines.append("- Divisional matchup: unavailable; verify league division data.")
        for stat in game.get("starter_stat_lines") or []:
            lines.append(
                f"- {stat.get('fantasy_team')}: {stat.get('player')} — {stat.get('nfl_stat_line')}"
            )
        for note in game.get("context_signals") or []:
            lines.append(f"- Context: {note}")
        for beat in game.get("beat_context") or []:
            lines.append(
                f"- Beat context: {beat.get('headline') or beat.get('original_title')} "
                f"— {beat.get('source')}"
            )

    usage = packet.get("usage_desk") or {}
    lines.extend(["", "## USAGE DESK INPUT", ""])
    lines.append(f"Status: {usage.get('status', 'UNKNOWN')}")
    enrichment = usage.get("enrichment_status") or {}
    lines.append(
        "- Source coverage: "
        + ", ".join(
            f"{key.replace('_', ' ')}={value}"
            for key, value in enrichment.items()
        )
    )
    leaders = usage.get("leaders") or {}
    for label, rows in leaders.items():
        lines.extend(["", f"### {label.replace('_', ' ').title()}"])
        for row in rows:
            parts = [
                f"{row.get('player')} — {row.get('fantasy_team') or 'unmapped'}",
            ]
            if row.get("carries") is not None:
                parts.append(f"{int(float(row.get('carries') or 0))} carries")
            if row.get("carry_share") is not None:
                parts.append(f"{float(row.get('carry_share')):.1%} team carries")
            if row.get("targets") is not None:
                parts.append(f"{int(float(row.get('targets') or 0))} targets")
            if row.get("target_share") is not None:
                parts.append(f"{float(row.get('target_share')):.1%} team targets")
            if row.get("snap_share") is not None:
                parts.append(f"{float(row.get('snap_share')):.1%} snaps")
            if row.get("red_zone_opportunities") is not None:
                parts.append(f"{int(float(row.get('red_zone_opportunities') or 0))} red-zone opps")
            lines.append("- " + "; ".join(parts))
    if usage.get("story_signals"):
        lines.extend(["", "### Usage Story Signals"])
        for row in usage.get("story_signals") or []:
            lines.append(
                f"- {row.get('signal_type') or row.get('type') or 'signal'}: "
                f"{row.get('explanation') or row.get('statement') or _compact(row)}"
            )

    lines.extend(["", "## INJURY & ROSTER HEALTH", ""])
    health = packet.get("injury_roster_health") or {}
    lines.append(f"Status: {health.get('status', 'unknown')}")
    for row in health.get("players") or []:
        details = [
            str(value)
            for value in (
                row.get("injury_status"),
                row.get("report_primary_injury"),
                row.get("practice_participation"),
                "IR/RESERVE" if row.get("on_ir") else None,
            )
            if value
        ]
        lines.append(f"- {row.get('team')}: {row.get('player')} — {', '.join(details) or 'flagged'}")

    market = packet.get("roster_market")
    if market is not None:
        lines.extend(["", "## ROSTER & MARKET DESK", ""])
        lines.append(f"Status: {market.get('status', 'UNKNOWN')}")
        lines.extend(["", "### Lineup Churn"])
        for row in market.get("lineup_churn") or []:
            moved_in = ", ".join(player.get("player") or "" for player in row.get("moved_into_starting_lineup") or []) or "none"
            moved_out = ", ".join(player.get("player") or "" for player in row.get("moved_out_of_starting_lineup") or []) or "none"
            lines.append(f"- {row.get('team')}: IN {moved_in}; OUT {moved_out}.")
        lines.extend(["", "### Current Transactions"])
        for row in (market.get("transactions") or {}).get("current_week") or []:
            lines.append("- " + _compact(row))
        lines.extend(["", "### Repeated Asset Movement"])
        for row in market.get("repeated_asset_movement") or []:
            lines.append(
                f"- {row.get('player')}: {row.get('transaction_events')} transaction events "
                f"({row.get('adds')} adds, {row.get('drops')} drops)."
            )
        lines.extend(["", "### Beat / Health Timelines"])
        for row in market.get("news_timelines") or []:
            if len(row.get("events") or []) < 1:
                continue
            lines.append(f"- {row.get('player')}:")
            for event in row.get("events") or []:
                lines.append(
                    f"  - {event.get('published_at')} — {event.get('headline')} — "
                    f"{event.get('source')} — {event.get('source_url')}"
                )
        timeline = market.get("status_timeline") or {}
        lines.extend(["", "### Observed Status Changes", f"- Coverage: {timeline.get('status', 'UNAVAILABLE')}. {timeline.get('note', '')}"])
        for event in timeline.get("events") or []:
            pid = (event.get("entities") or {}).get("player_id")
            lines.append(f"- Player {pid}: {_compact(event.get('before') or {})} → {_compact(event.get('after') or {})}; observed between {event.get('observed_before')} and {event.get('observed_after') or event.get('observed_at')}; source {event.get('source')}.")
        platform = market.get("sleeper_platform_rates") or {}
        lines.extend(["", "### Sleeper-wide Ownership / Start Rates"])
        lines.append(
            f"- Status: {platform.get('status', 'UNAVAILABLE')}. "
            f"{platform.get('note') or 'Optional enrichment only.'}"
        )
        for pid, rates in (platform.get("players") or {}).items():
            lines.append(f"- Player {pid}: {_compact(rates)}; observed {platform.get('observed_at')}; {platform.get('source_url')}.")
        network = market.get("network_market") or {}
        lines.extend(["", f"### {network.get('scope') or 'Ironbound Network'} Signals"])
        for row in network.get("players") or []:
            if row.get("added_leagues") or row.get("dropped_leagues") or row.get("started_leagues"):
                rate = row.get("tracked_start_rate")
                rate_text = f"; tracked start rate {float(rate):.0%}" if rate is not None else ""
                lines.append(
                    f"- {row.get('player')}: rostered {row.get('rostered_leagues')} tracked leagues; "
                    f"started {row.get('started_leagues')}; added {row.get('added_leagues')}; "
                    f"dropped {row.get('dropped_leagues')}{rate_text}."
                )

    beat = packet.get("beat_report")
    if beat is not None:
        lines.extend(["", "## REUSABLE BEAT CONTEXT — SOURCE EVIDENCE", ""])
        lines.append(f"Status: {beat.get('status', 'UNKNOWN')}")
        if beat.get("source_revision"):
            lines.append(
                f"Source revision: {beat.get('source_revision')} "
                f"({beat.get('source_repository')}:{beat.get('source_branch')})"
            )
        window = beat.get("reporting_window") or {}
        if window:
            lines.append(
                f"Reporting window: {window.get('start')} through {window.get('end')}."
            )
        lines.append(
            f"League-relevant accepted stories: {int(beat.get('relevant_event_count') or 0)}."
        )
        for row in beat.get("items") or []:
            players = ", ".join(
                f"{player.get('player')} ({player.get('fantasy_team')})"
                for player in row.get("league_players") or []
            )
            tags = ", ".join(row.get("tags") or [])
            lines.append(
                f"- {row.get('published_at')} — {row.get('headline') or row.get('original_title')} "
                f"— {row.get('source')} — {players or 'league relevance mapped'}"
                + (f" — tags: {tags}" if tags else "")
            )
            if row.get("feed_summary"):
                lines.append(f"  Evidence summary: {row.get('feed_summary')}")
            if row.get("source_url"):
                lines.append(f"  Source: {row.get('source_url')}")
            lanes = [
                key.replace("_", " ")
                for key, enabled in (row.get("editorial_lanes") or {}).items()
                if enabled
            ]
            if lanes:
                lines.append("  Editorial lanes: " + ", ".join(lanes))

    honors = packet.get("weekly_honors") or {}
    lines.extend(["", "## WEEKLY HONORS & ROOKIE WATCH", "", "### Started Position Leaders"])
    for position in CORE_POSITIONS:
        row = (honors.get("started_position_leaders") or {}).get(position)
        if row:
            line = f"- {position}: {row.get('player')} — {row.get('team')} — {float(row.get('points') or 0):.2f} FP"
            if row.get("nfl_stat_line"):
                line += f" — {row.get('nfl_stat_line')}"
            lines.append(line)

    overall = honors.get("overall_player_of_the_week")
    if overall:
        lines.extend(["", "### Overall Player of the Week", f"- {overall.get('player')} — {overall.get('points')} FP — {overall.get('nfl_stat_line') or ''}"])
    for key, label in (
        ("rookie_of_the_week", "Rookie of the Week (starter, bench, or taxi)"),
        ("top_rookie_starter", "Top Rookie Starter"),
    ):
        row = honors.get(key)
        if row:
            lines.extend(["", f"### {label}", f"- {row.get('player')} — {row.get('team')} — {float(row.get('points') or 0):.2f} FP — {row.get('ironbound_draft') or 'Draft pick not recorded'} — {row.get('nfl_stat_line') or 'NFL stat line unavailable'}"])
    for key, label in (("most_efficient_manager", "Most Efficient Manager"), ("high_score", "High Score"), ("low_score", "Low Score")):
        row = honors.get(key)
        if row:
            lines.extend(["", f"### {label}", f"- {row.get('team')} — {row.get('points', row.get('actual_points'))} points"])
    lines.extend(["", "### Rotating Award Availability", honors.get("rotating_award_policy", "")])
    for code, status in (honors.get("award_availability") or {}).items():
        if status.get("status") != "AVAILABLE":
            lines.append(f"- {code}: {status.get('status')} — {status.get('reason')}")
    for row in honors.get("rotating_award_manual_review") or []:
        lines.append(f"- MANUAL_REVIEW: {row.get('label')} — {row.get('team')} — {_compact(row.get('evidence') or {})}")
    for row in honors.get("exceptional_loss_review") or []:
        lines.append(f"- Exceptional loss review: {row.get('team')} — {row.get('reason')}")
    manager = honors.get("manager_of_the_week")
    lines.extend(["", "### Manager of the Week"])
    lines.append(
        f"- {manager.get('team')} — {float(manager.get('actual_points') or 0):.2f} points; {float(manager.get('efficiency') or 0):.1%} efficiency"
        if manager else "- No eligible manager."
    )

    lines.extend(
        [
            "",
            "### Season Efficiency Top 3",
            "",
            "| Rank | Team | Cumulative Efficiency | Weeks |",
            "|---:|---|---:|---:|",
        ]
    )
    for rank, row in enumerate(honors.get("season_efficiency_top_three") or [], 1):
        lines.append(
            f"| {rank} | {row.get('team')} | {float(row.get('efficiency') or 0):.1%} | {row.get('weeks')} |"
        )

    lines.extend(
        [
            "",
            "### Season Team Score Top 3",
            "",
            "| Rank | Team | Cumulative Points | Weeks |",
            "|---:|---|---:|---:|",
        ]
    )
    for rank, row in enumerate(honors.get("season_team_score_top_three") or [], 1):
        lines.append(
            f"| {rank} | {row.get('team')} | {float(row.get('score') or 0):.2f} | {row.get('weeks')} |"
        )

    lines.extend(["", "### Player Season Top 3", ""])
    player_boards = honors.get("player_season_top_three") or {}
    lines.append(f"Status: {player_boards.get('status', 'UNAVAILABLE')} — {player_boards.get('reason') or 'complete score history required'}.")
    for position, rows in (player_boards.get("by_position") or {}).items():
        for rank, row in enumerate(rows, 1):
            lines.append(
                f"- {position} #{rank}: {row.get('player')} — {row.get('fantasy_team')} — {float(row.get('points') or 0):.2f} cumulative FP."
            )

    rookie_boards = honors.get("rookie_season_leaders") or {}
    lines.extend(["", "### Rookie Season Leaders", f"Status: {rookie_boards.get('status', 'UNAVAILABLE')} — {rookie_boards.get('reason') or 'complete score history required'}."])
    for position, row in (rookie_boards.get("by_position") or {}).items():
        lines.append(
            f"- {position}: {row.get('player')} — {row.get('fantasy_team')} — {float(row.get('points') or 0):.2f} cumulative FP."
        )

    lines.extend(["", "### Bad Beat"])
    bad_beat = honors.get("bad_beat")
    if bad_beat:
        lines.append(
            f"- {bad_beat.get('team')}: {float(bad_beat.get('points') or 0):.2f} points in a loss; entering record {_compact(bad_beat.get('entering_record') or {})}."
        )
    else:
        status = honors.get("bad_beat_status") or {}
        lines.append(f"- {status.get('status', 'UNAVAILABLE')}: {status.get('reason') or 'No verified qualifying loss.'}")
    for row in (honors.get("bad_beat_candidates") or [])[:5]:
        lines.append(
            f"  - Candidate: {row.get('team')} — {float(row.get('points') or 0):.2f} lost by "
            f"{float(row.get('margin') or 0):.2f}; entering record "
            f"{_compact(row.get('entering_record') or row.get('record_status'))}."
        )

    lines.extend(["", "### Escape Artist"])
    escape = honors.get("escape_artist")
    if escape:
        lines.append(
            f"- {escape.get('team')}: {float(escape.get('points') or 0):.2f} points in a win; entering record {_compact(escape.get('entering_record') or {})}."
        )
    else:
        status = honors.get("escape_artist_status") or {}
        lines.append(f"- {status.get('status', 'UNAVAILABLE')}: {status.get('reason') or 'No verified distinct qualifying win.'}")
    for row in (honors.get("escape_artist_candidates") or [])[:5]:
        lines.append(
            f"  - Candidate: {row.get('team')} — {float(row.get('points') or 0):.2f} won by "
            f"{float(row.get('margin') or 0):.2f}; entering record "
            f"{_compact(row.get('entering_record') or row.get('record_status'))}."
        )

    lines.extend(["", "### Rookie Disappointment — Editorial Candidates"])
    rookie_status = honors.get("rookie_disappointment_status") or {}
    lines.append(f"Status: {rookie_status.get('status', 'UNAVAILABLE')} — {rookie_status.get('reason') or 'candidate evidence available'}.")
    for row in honors.get("rookie_disappointment_candidates") or []:
        projection = (
            f"{float(row['projected_points']):.2f} projected; delta {float(row['projection_delta']):+.2f}"
            if row.get("projection_status") == "VERIFIED"
            else "projection unavailable"
        )
        lines.append(
            f"- {row.get('player')} — {row.get('team')} — {row.get('status')} — "
            f"{float(row.get('points') or 0):.2f} FP — {row.get('ironbound_draft') or 'Draft pick not recorded'} — {projection}."
        )

    free_agent = honors.get("free_agent_of_the_week")
    lines.extend(["", "### Free Agent of the Week"])
    if free_agent:
        lines.append(
            f"- {free_agent.get('player')} — {free_agent.get('fantasy_team', 'UNROSTERED')} — "
            f"{float(free_agent.get('points') or 0):.2f} FP."
        )
    else:
        lines.append("- UNAVAILABLE: no verified free-agent scoring candidate was supplied.")

    lines.extend(["", "### Benchwarmer of the Week"])
    bench = honors.get("benchwarmer_of_the_week")
    if bench:
        line = f"- {bench.get('player')} — {bench.get('team')} — {float(bench.get('points') or 0):.2f} FP"
        if bench.get("nfl_stat_line"):
            line += f" — {bench.get('nfl_stat_line')}"
        lines.append(line)
    else:
        lines.append("- No eligible benchwarmer.")

    lines.extend(
        [
            "",
            "### Rookie Watch — Top 5",
            "",
            "| Rank | Rookie | Week Line / FP | Current Team | Ironbound Draft |",
            "|---:|---|---|---|---|",
        ]
    )
    for rank, row in enumerate(honors.get("rookie_watch_top_five") or [], 1):
        draft = str(row.get("ironbound_draft") or "Not recorded")
        line = row.get("nfl_stat_line") or "NFL stat line unavailable"
        lines.append(
            f"| {rank} | {row.get('player')} | {line}; {float(row.get('points') or 0):.2f} FP | {row.get('team')} | {draft} |"
        )

    lines.extend(["", "### Rotating Award Candidates"])
    for row in honors.get("rotating_award_candidates") or []:
        lines.append(f"- {row.get('candidate_type')}: {row.get('team') or row.get('player') or row.get('started_player')} — {row.get('reason')}")

    lines.extend(["", "## POWER BOARD — INDIVIDUAL WRITEUP INPUTS", ""])
    for row in (packet.get("power_board") or {}).get("writeup_inputs") or []:
        previous = row.get("previous_rank")
        movement = row.get("rank_movement")
        movement_text = ""
        if previous is not None and movement is not None:
            if int(movement) > 0:
                movement_text = f"; up {int(movement)} from #{int(previous)}"
            elif int(movement) < 0:
                movement_text = f"; down {abs(int(movement))} from #{int(previous)}"
            else:
                movement_text = f"; unchanged from #{int(previous)}"
        lines.append(
            f"- {row.get('team')}: {row.get('wins', 0)}-{row.get('losses', 0)}; "
            f"{float(row.get('points_for') or 0):.2f} PF; official rank {row.get('official_rank', 'awaiting')}"
            f"{movement_text}; efficiency {float(row.get('efficiency') or 0):.1%}."
        )
        components = row.get("ranking_components") or {}
        if components:
            lines.append(
                "  - Ranking components: "
                f"market {float(components.get('market_points') or 0):.1f}; "
                f"ROS starters {float(components.get('ros_starters_points') or 0):.1f}; "
                f"season results {float(components.get('season_results_points') or 0):.1f}."
            )

    lines.extend(["", "## POWER RANKINGS CHART INPUT", ""])
    power = packet.get("power_rankings_chart") or {}
    lines.append(f"Status: {power.get('status')}")
    lines.append(
        "Authority: Ironbound_power_ranks. Movement below is imported from the "
        "ranking engine's shared Saturday/Tuesday publication history and must not be recalculated."
    )
    for row in sorted(power.get("rows") or [], key=lambda item: int(item.get("rank") or 999)):
        label = row.get("team") or row.get("franchise_key") or f"Roster {row.get('roster_id')}"
        previous = row.get("previous_rank")
        movement = row.get("movement")
        if previous is None or movement is None:
            movement_text = "movement unavailable"
        elif int(movement) > 0:
            movement_text = f"up {int(movement)} from #{int(previous)}"
        elif int(movement) < 0:
            movement_text = f"down {abs(int(movement))} from #{int(previous)}"
        else:
            movement_text = f"unchanged from #{int(previous)}"
        lines.append(
            f"- #{row.get('rank')} {label} — {movement_text}; "
            f"ranking score {float(row.get('score') or 0):.1f}"
        )

    lines.extend(["", "## RANKING PUBLICATION ASSETS", ""])
    assets = packet.get("ranking_publication_assets") or {}
    lines.append(str(assets.get("policy") or ""))
    for asset_key, label in (
        ("power_rankings", "Power Rankings"),
        ("playoff_forecast", "Playoff Forecast"),
    ):
        asset = (assets.get("assets") or {}).get(asset_key) or {}
        if asset.get("status") == "READY":
            lines.append(
                f"- {label}: {asset.get('package_path')} — "
                f"SHA-256 {asset.get('sha256') or asset.get('actual_sha256') or 'not supplied'} — "
                "PLACE THIS SUPPLIED GRAPHIC UNCHANGED."
            )
        else:
            lines.append(f"- {label}: {asset.get('status') or 'MISSING'}")

    lines.extend(["", "## PLAYOFF ODDS CHART INPUT", ""])
    odds = packet.get("playoff_odds_chart") or {}
    lines.append(f"Status: {odds.get('status')}")
    for row in odds.get("rows") or []:
        lines.append("- " + _compact(row))

    outlook = packet.get("division_outlook") or {}
    lines.extend(["", "## DIVISION OF DEATH / ROAD AHEAD", ""])
    lines.append(
        f"Status: {outlook.get('status', 'UNAVAILABLE')}; "
        f"division data: {outlook.get('division_status', 'UNAVAILABLE')}; "
        f"schedule data: {outlook.get('schedule_status', 'UNAVAILABLE')}."
    )
    for row in outlook.get("division_summaries") or []:
        lines.append(
            f"- {row.get('division_name') or row.get('division_id')}: "
            f"{row.get('average_points', 'average unavailable')} average points; "
            f"record {_compact(row.get('head_to_head_record') or {})}."
        )
    hardest = outlook.get("hardest_remaining_schedule") or {}
    easiest = outlook.get("easiest_remaining_schedule") or {}
    if hardest:
        lines.append(f"- Hardest remaining schedule: {_compact(hardest)}")
    if easiest:
        lines.append(f"- Easiest remaining schedule: {_compact(easiest)}")

    lines.extend(["", "## REMAINING SCHEDULE STRENGTH", ""])
    schedule = packet.get("remaining_schedule_strength") or {}
    lines.append(f"Status: {schedule.get('status')}; Authority: {schedule.get('authority')}.")
    for row in schedule.get("rows") or []:
        lines.append(
            f"- #{row.get('difficulty_rank')} {row.get('team')}: "
            f"average opponent index {row.get('average_opponent_index')} ({row.get('grade')})."
        )

    lines.extend(["", "## FULL SLATE — SIMULATED WEEKLY LINES", ""])
    weekly_forecast = packet.get("weekly_matchup_forecast") or {}
    lines.append(f"Status: {weekly_forecast.get('status')}; Authority: {weekly_forecast.get('authority')}.")
    lines.append(str(weekly_forecast.get("lineup_policy") or ""))
    for row in weekly_forecast.get("rows") or []:
        favorite = row.get("favorite_team") or (
            row.get("team_one") if int(row.get("favorite_roster_id") or 0) == int(row.get("roster_one") or -1) else row.get("team_two")
        )
        lines.append(
            f"- {row.get('team_one')} vs. {row.get('team_two')}: "
            f"{favorite} -{float(row.get('spread') or 0):.1f}; "
            f"O/U {float(row.get('over_under') or 0):.1f}; "
            f"{row.get('simulations')} simulations."
        )

    lines.extend(["", "## OPTIONAL SUPPLEMENTAL ANALYTICS", ""])
    ext = packet.get("tuesday_external_inputs") or {}
    lines.append(
        "Weekly usage is already supplied by the internal nflverse Usage Desk above. "
        "WAR and cWAR are optional feature-story enrichment and do not affect research completeness."
    )
    for key, label in (("war", "WAR"), ("cwar", "cWAR")):
        section = ext.get(key) or {}
        lines.extend(["", f"### {label} — {section.get('status')}"])
        for row in section.get("rows") or []:
            lines.append("- " + _compact(row))

    lines.extend(["", "## STORY DESK / COVER ANGLES", ""])
    for row in (packet.get("story_desk") or {}).get("candidates") or []:
        subjects = " / ".join(row.get("display_subjects") or [])
        lines.append(
            f"- {str(row.get('candidate_type') or 'story').replace('_', ' ').title()}"
            + (f" — {subjects}" if subjects else "")
        )
        for fact in (row.get("display_facts") or row.get("facts") or [])[:3]:
            if fact.get("statement"):
                lines.append(f"  - {fact['statement']}")

    lines.extend(
        [
            "",
            "## HANDOFF RULE",
            "",
            "This packet is factual research. The production manuscript may select angles and write prose, but it must not invent missing facts. A missing deterministic source must remain MANUAL_VERIFY; a missing Tuesday handoff must remain AWAITING_TUESDAY_INPUT.",
            "",
        ]
    )
    return "\n".join(lines)


def write_flagship_research_packet(directory: Path, packet: dict[str, Any]) -> tuple[Path, Path]:
    directory = Path(directory)
    json_path = directory / "flagship_research_packet.json"
    markdown_path = directory / "flagship_research_packet.md"
    json_path.write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_flagship_research_packet(packet), encoding="utf-8")
    return json_path, markdown_path


def _game_research(snapshot: dict[str, Any], dossier: dict[str, Any]) -> list[dict[str, Any]]:
    scoreboard = dossier.get("scoreboard") or []
    stat_rows = (((dossier.get("nfl_game_intelligence") or {}).get("stat_book") or {}).get("records") or [])
    signals = (dossier.get("nfl_game_intelligence") or {}).get("story_signals") or []
    team_stat_rows: dict[str, list[dict[str, Any]]] = {}
    roster_by_id = {
        int(row.get("roster_id") or 0): row
        for row in snapshot.get("rosters") or []
        if int(row.get("roster_id") or 0)
    }
    metadata = (snapshot.get("league") or {}).get("metadata") or {}
    for row in stat_rows:
        team_stat_rows.setdefault(str(row.get("fantasy_team") or ""), []).append(row)

    games: list[dict[str, Any]] = []
    for game in scoreboard:
        teams = game.get("teams") or []
        team_names = [str(row.get("team") or "") for row in teams]
        starter_stats = [
            dict(row)
            for team in team_names
            for row in team_stat_rows.get(team, [])
        ]
        signal_lines = [
            str(signal.get("explanation"))
            for signal in signals
            if signal.get("explanation") and _signal_belongs_to_game(signal, starter_stats)
        ]
        ordered = sorted(teams, key=lambda row: float(row.get("points") or 0), reverse=True)
        matchup = " vs. ".join(row.get("team") or "Unknown" for row in teams)
        scoreline = " — ".join(
            f"{row.get('team')} {float(row.get('points') or 0):.2f}"
            for row in ordered
        )
        top_starter = _top_started_player_for_game(snapshot, team_names)
        divisions = [
            str(((roster_by_id.get(int(team.get("roster_id") or 0)) or {}).get("settings") or {}).get("division"))
            if ((roster_by_id.get(int(team.get("roster_id") or 0)) or {}).get("settings") or {}).get("division") is not None
            else None
            for team in teams
        ]
        division_status = "UNAVAILABLE"
        division_name = None
        if len(divisions) == 2 and all(divisions):
            if divisions[0] != divisions[1]:
                division_status = "VERIFIED_NON_DIVISIONAL"
            else:
                division_name = metadata.get(f"division_{divisions[0]}")
                if division_name:
                    division_status = "VERIFIED_DIVISIONAL"
        games.append(
            {
                "matchup_id": game.get("matchup_id"),
                "matchup": matchup,
                "scoreline": scoreline,
                "teams": teams,
                "winner": game.get("winner"),
                "loser": game.get("loser"),
                "margin": game.get("margin"),
                "starter_stat_lines": starter_stats,
                "context_signals": signal_lines,
                "top_started_player": top_starter,
                "division_status": division_status,
                **({"division_name": str(division_name)} if division_name else {}),
            }
        )
    return games


def _division_outlook(
    division_summaries: list[dict[str, Any]],
    remaining_schedule_strength: dict[str, Any],
) -> dict[str, Any]:
    summaries = [dict(row) for row in division_summaries if isinstance(row, dict)]
    schedule = dict(remaining_schedule_strength or {})
    rows = [dict(row) for row in schedule.get("rows") or [] if isinstance(row, dict)]
    rows.sort(key=lambda row: int(row.get("difficulty_rank") or 999))
    division_status = "READY" if summaries else "UNAVAILABLE"
    schedule_status = str(schedule.get("status") or "UNAVAILABLE")
    return {
        "status": "READY" if division_status == "READY" and schedule_status == "READY" and rows else "PARTIAL",
        "division_status": division_status,
        "division_summaries": summaries,
        "schedule_status": schedule_status,
        "remaining_schedule_strength": rows,
        "hardest_remaining_schedule": rows[0] if rows else None,
        "easiest_remaining_schedule": rows[-1] if rows else None,
    }


def _attach_beat_context_to_games(
    games: list[dict[str, Any]],
    beat_report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Cross-link accepted beat items to fantasy matchups without editorial inference."""
    items = beat_report.get("items") or []
    enriched: list[dict[str, Any]] = []
    for game in games:
        row = dict(game)
        team_names = {
            str(team.get("team") or "")
            for team in row.get("teams") or []
            if team.get("team")
        }
        row["beat_context"] = [
            {
                "event_id": item.get("event_id"),
                "published_at": item.get("published_at"),
                "headline": item.get("headline"),
                "original_title": item.get("original_title"),
                "source": item.get("source"),
                "source_url": item.get("source_url"),
                "tags": item.get("tags") or [],
                "league_players": item.get("league_players") or [],
                "editorial_lanes": item.get("editorial_lanes") or {},
            }
            for item in items
            if team_names.intersection(
                str(player.get("fantasy_team") or "")
                for player in item.get("league_players") or []
            )
        ]
        enriched.append(row)
    return enriched


def _cover_candidates(games: list[dict[str, Any]], dossier: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    monday = (dossier.get("game_timing") or {}).get("monday") or {}
    changed = {
        (str(row.get("final_winner") or ""), str(row.get("final_loser") or ""))
        for row in monday.get("lead_changes") or []
    }
    for game in games:
        margin = float(game.get("margin") or 0)
        winner = game.get("winner") or {}
        loser = game.get("loser") or {}
        winner_points = float(winner.get("points") or 0)
        top = game.get("top_started_player") or {}
        reasons: list[str] = []
        score = 0.0
        if margin <= 10:
            score += 8
            reasons.append(f"close finish ({margin:.2f}-point margin)")
        elif margin <= 20:
            score += 4
            reasons.append(f"competitive finish ({margin:.2f}-point margin)")
        if winner_points >= 140:
            score += 7
            reasons.append(f"high team score ({winner_points:.2f})")
        elif winner_points >= 125:
            score += 3
            reasons.append(f"strong team score ({winner_points:.2f})")
        top_points = float(top.get("points") or 0)
        if top_points >= 35:
            score += min(top_points / 5, 10)
            reasons.append(f"singular started-player performance ({top.get('player')} {top_points:.2f})")
        if (str(winner.get("team") or ""), str(loser.get("team") or "")) in changed:
            score += 10
            reasons.append("Monday result-changing comeback")
        if game.get("context_signals"):
            score += min(len(game["context_signals"]) * 2, 6)
            reasons.append("usage/game-intelligence signal")
        candidates.append(
            {
                "matchup_id": game.get("matchup_id"),
                "matchup": game.get("matchup"),
                "signal_score": round(score, 2),
                "reasons": reasons or ["completed matchup available for editorial review"],
            }
        )
    return sorted(candidates, key=lambda row: (-float(row["signal_score"]), str(row["matchup_id"])))[:5]


def _top_started_player_for_game(snapshot: dict[str, Any], team_names: list[str]) -> dict[str, Any] | None:
    users = {str(row.get("user_id")): row for row in snapshot.get("users") or []}
    roster_team: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        owner = users.get(str(roster.get("owner_id"))) or {}
        meta = owner.get("metadata") or {}
        roster_team[int(roster.get("roster_id") or 0)] = str(
            meta.get("team_name") or owner.get("display_name") or f"Roster {roster.get('roster_id')}"
        )
    players = snapshot.get("players") or {}
    candidates: list[dict[str, Any]] = []
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup.get("roster_id") or 0)
        if roster_team.get(roster_id) not in team_names:
            continue
        points = matchup.get("players_points") or matchup.get("players_points_custom") or {}
        for player_id in matchup.get("starters") or []:
            player = players.get(str(player_id)) or {}
            candidates.append(
                {
                    "player_id": str(player_id),
                    "player": player.get("full_name") or str(player_id),
                    "team": roster_team.get(roster_id),
                    "points": float(points.get(str(player_id), points.get(player_id, 0)) or 0),
                }
            )
    return max(candidates, key=lambda row: (row["points"], row["player"]), default=None)


def _signal_belongs_to_game(signal: dict[str, Any], starter_stats: list[dict[str, Any]]) -> bool:
    player_ids = {str(row.get("nfl_player_id") or row.get("player_id") or "") for row in starter_stats}
    return str(signal.get("player_id") or "") in player_ids


def _season_dossiers(root: Path, season: str, league_key: str, through_week: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(root).glob(f"{season}/week-*/{league_key}/dossier.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        week = int(value.get("week") or 0)
        if 0 < week <= through_week:
            rows.append(value)
    return rows


def _season_team_score_top_three(
    history: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any],
    league_key: str,
    season: str,
    chronicle: ChronicleQueries | None,
) -> list[dict[str, Any]]:
    names = _roster_team_names(snapshot)
    current_week = int(snapshot.get("week") or 0)
    by_week_roster: dict[tuple[int, int], dict[str, Any]] = {}

    if chronicle is not None:
        for row in chronicle.season_matchup_finals(league_key, season):
            roster_id = int(row.get("roster_id") or 0)
            week = int(row.get("week") or 0)
            points = _safe_float(row.get("points"))
            if roster_id and points is not None and 0 < week <= current_week:
                by_week_roster[(week, roster_id)] = {
                    "team": names.get(roster_id, f"Roster {roster_id}"),
                    "roster_id": roster_id,
                    "score": points,
                    "week": week,
                }

    # Historical dossier artifacts are a compatibility fallback for weeks that
    # predate durable MATCHUP_FINAL events.
    for dossier in history:
        week = int(dossier.get("week") or 0)
        if not 0 < week <= current_week:
            continue
        for game in dossier.get("scoreboard") or []:
            for team in game.get("teams") or []:
                roster_id = int(team.get("roster_id") or 0)
                points = _safe_float(team.get("points"))
                if roster_id and points is not None:
                    by_week_roster.setdefault(
                        (week, roster_id),
                        {
                            "team": team.get("team") or names.get(roster_id),
                            "roster_id": roster_id,
                            "score": points,
                            "week": week,
                        },
                    )

    # Always merge the reviewed week from the live dossier so a correctly
    # completed packet does not depend on materialized Chronicle freshness.
    for matchup in snapshot.get("matchups") or []:
        roster_id = int(matchup.get("roster_id") or 0)
        points = _safe_float(matchup.get("points"))
        if roster_id and current_week and points is not None:
            by_week_roster[(current_week, roster_id)] = {
                "team": names.get(roster_id, f"Roster {roster_id}"),
                "roster_id": roster_id,
                "score": points,
                "week": current_week,
            }

    totals: dict[int, dict[str, Any]] = {}
    for row in by_week_roster.values():
        roster_id = int(row["roster_id"])
        aggregate = totals.setdefault(
            roster_id,
            {
                "team": row.get("team") or names.get(roster_id) or f"Roster {roster_id}",
                "roster_id": roster_id,
                "score": 0.0,
                "weeks": 0,
                "through_week": int(snapshot.get("week") or 0),
            },
        )
        aggregate["score"] += float(row["score"])
        aggregate["weeks"] += 1
    rows = list(totals.values())
    rows.sort(
        key=lambda row: (
            -row["score"],
            -row["weeks"],
            str(row.get("team") or "").casefold(),
        )
    )
    return rows[:3]


def _canonical_team_score_top_three(
    canonical_evidence: dict[str, Any],
    *,
    through_week: int,
) -> list[dict[str, Any]]:
    rows = [
        {
            "team": row.get("team"),
            "roster_id": row.get("roster_id"),
            "score": float(row.get("points") or 0),
            "weeks": int(row.get("through_week") or through_week),
            "through_week": through_week,
        }
        for row in (canonical_evidence.get("team_season_totals") or {}).values()
    ]
    rows.sort(
        key=lambda row: (
            -float(row.get("score") or 0),
            str(row.get("team") or "").casefold(),
        )
    )
    return rows[:3]


def _season_player_boards(
    historical_rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate finalized weekly player scores without presenting gaps as full totals."""
    from .weekly_features import _rostered_player_weeks

    through_week = int(snapshot.get("week") or 0)
    rosters = {
        int(row.get("roster_id") or 0): row
        for row in snapshot.get("rosters") or []
        if int(row.get("roster_id") or 0)
    }
    team_names = _roster_team_names(snapshot)
    players = snapshot.get("players") or {}

    def display_player_name(player_id: str) -> str:
        player = players.get(player_id) or {}
        return str(player.get("full_name") or player.get("name") or player_id)

    current_roster_by_player: dict[str, int] = {}
    duplicate_current_players: set[str] = set()
    for roster_id, roster in rosters.items():
        for player_id in {
            str(value)
            for field in ("players", "taxi", "reserve")
            for value in roster.get(field) or []
        }:
            if player_id in current_roster_by_player and current_roster_by_player[player_id] != roster_id:
                duplicate_current_players.add(player_id)
            current_roster_by_player[player_id] = roster_id

    by_week_player: dict[tuple[int, str], dict[str, Any]] = {}
    roster_coverage: dict[int, set[int]] = {}
    conflicts: set[tuple[int, str]] = set()

    def add_score(row: dict[str, Any], *, current: bool = False) -> None:
        week = int(row.get("week") or 0)
        roster_id = int(row.get("roster_id") or 0)
        player_id = str(row.get("player_id") or "")
        if not (0 < week <= through_week and roster_id in rosters and player_id):
            return
        roster_coverage.setdefault(week, set()).add(roster_id)
        key = (week, player_id)
        value = {
            "week": week,
            "roster_id": roster_id,
            "player_id": player_id,
            "position": row.get("position"),
            "points": round(float(row.get("points") or 0), 2),
        }
        previous = by_week_player.get(key)
        if previous and previous["roster_id"] != roster_id and previous["points"] != value["points"]:
            conflicts.add(key)
        if previous is None or current:
            by_week_player[key] = value

    for row in historical_rows:
        if int(row.get("week") or 0) < through_week:
            add_score(row)
    for row in _rostered_player_weeks(snapshot):
        add_score({**row, "week": through_week}, current=True)

    expected_rosters = set(rosters)
    missing_weeks = [
        week
        for week in range(1, through_week + 1)
        if not expected_rosters.issubset(roster_coverage.get(week, set()))
    ]
    reasons = []
    if missing_weeks:
        reasons.append(
            "missing finalized player scores for week(s) "
            + ", ".join(str(value) for value in missing_weeks)
        )
    if conflicts:
        reasons.append("conflicting player-week scores were recorded for multiple fantasy rosters")
    if duplicate_current_players:
        reasons.append("one or more players are assigned to multiple current fantasy rosters")
    status = "READY" if not reasons and through_week > 0 else "UNAVAILABLE"

    totals: dict[str, float] = {}
    for (_, player_id), row in by_week_player.items():
        if player_id in current_roster_by_player:
            totals[player_id] = totals.get(player_id, 0.0) + float(row["points"])

    by_position: dict[str, list[dict[str, Any]]] = {}
    rookie_by_position: dict[str, dict[str, Any]] = {}
    if status == "READY":
        for position in CORE_POSITIONS:
            candidates = []
            rookie_candidates = []
            for player_id, points in totals.items():
                player = players.get(player_id) or {}
                player_position = str(player.get("position") or "").upper()
                if not player_position:
                    fantasy_positions = player.get("fantasy_positions") or []
                    player_position = str(fantasy_positions[0] if fantasy_positions else "").upper()
                if player_position != position:
                    continue
                roster_id = current_roster_by_player[player_id]
                row = {
                    "player_id": player_id,
                    "player": display_player_name(player_id),
                    "position": position,
                    "points": round(points, 2),
                    "fantasy_team": team_names.get(roster_id, f"Roster {roster_id}"),
                }
                candidates.append(row)
                if player.get("years_exp") is not None and _safe_int(player.get("years_exp")) == 0:
                    rookie_candidates.append(row)
            candidates.sort(key=lambda row: (-row["points"], row["player"].casefold()))
            rookie_candidates.sort(key=lambda row: (-row["points"], row["player"].casefold()))
            by_position[position] = candidates[:3]
            if rookie_candidates:
                rookie_by_position[position] = rookie_candidates[0]

    reason = "; ".join(reasons) if reasons else None
    return {
        "player_season_top_three": {
            "status": status,
            "through_week": through_week,
            "reason": reason,
            "by_position": by_position if status == "READY" else {},
        },
        "rookie_season_leaders": {
            "status": status,
            "through_week": through_week,
            "reason": reason,
            "by_position": rookie_by_position if status == "READY" else {},
        },
    }


def _manager_weekly_awards(
    dossier: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    current_week: int,
    manager_of_the_week: dict[str, Any] | None,
    entering_records: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    lineup = list(dossier.get("lineup_efficiency") or [])
    winner_id = _safe_int((manager_of_the_week or {}).get("roster_id"))
    most_efficient = max(
        (
            row
            for row in lineup
            if _safe_int(row.get("roster_id")) is not None
            and _safe_int(row.get("roster_id")) != winner_id
        ),
        key=lambda row: (
            _safe_float(row.get("efficiency")) or 0,
            _safe_float(row.get("actual_points")) or 0,
        ),
        default=None,
    )

    records: dict[int, dict[int, float]] = {}
    for prior in history:
        week = _safe_int(prior.get("week"))
        if week is None or not 0 < week < current_week:
            continue
        for game in prior.get("scoreboard") or []:
            teams = game.get("teams") or []
            if len(teams) != 2:
                continue
            scores = [(_safe_int(team.get("roster_id")), _safe_float(team.get("points"))) for team in teams]
            if any(rid is None or points is None for rid, points in scores):
                continue
            (left_id, left_score), (right_id, right_score) = scores
            result = 0.5 if left_score == right_score else (1.0 if left_score > right_score else 0.0)
            records.setdefault(left_id, {})[week] = result
            records.setdefault(right_id, {})[week] = 1.0 - result if result != 0.5 else 0.5

    expected_weeks = set(range(1, current_week))
    entering: dict[int, dict[str, int]] = {}
    if entering_records:
        entering = {
            int(roster_id): {
                "wins": int((row or {}).get("wins") or 0),
                "losses": int((row or {}).get("losses") or 0),
                "ties": int((row or {}).get("ties") or 0),
            }
            for roster_id, row in entering_records.items()
        }
    elif expected_weeks:
        for roster_id, results in records.items():
            if set(results) != expected_weeks:
                continue
            entering[roster_id] = {
                "wins": sum(value == 1.0 for value in results.values()),
                "losses": sum(value == 0.0 for value in results.values()),
                "ties": sum(value == 0.5 for value in results.values()),
            }

    losses: list[dict[str, Any]] = []
    wins: list[dict[str, Any]] = []
    for game in dossier.get("scoreboard") or []:
        teams = game.get("teams") or []
        if len(teams) != 2:
            continue
        left, right = teams
        left_id, right_id = _safe_int(left.get("roster_id")), _safe_int(right.get("roster_id"))
        left_score, right_score = _safe_float(left.get("points")), _safe_float(right.get("points"))
        if None in (left_id, right_id, left_score, right_score) or left_score == right_score:
            continue
        matchup_id = game.get("matchup_id")
        for team, opponent, roster_id, score, opponent_score, won in (
            (left, right, left_id, left_score, right_score, left_score > right_score),
            (right, left, right_id, right_score, left_score, right_score > left_score),
        ):
            record = entering.get(roster_id)
            row = {
                "roster_id": roster_id,
                "team": team.get("team") or f"Roster {roster_id}",
                "points": round(score, 2),
                "opponent": opponent.get("team") or f"Roster {_safe_int(opponent.get('roster_id'))}",
                "opponent_points": round(opponent_score, 2),
                "margin": round(abs(score - opponent_score), 2),
                "matchup_id": matchup_id,
                "entering_record": record,
                "record_status": "VERIFIED" if record is not None else "UNAVAILABLE",
            }
            (wins if won else losses).append(row)

    losses.sort(
        key=lambda row: (
            -(row["entering_record"]["wins"] > row["entering_record"]["losses"])
            if row["entering_record"]
            else 0,
            -row["points"],
            row["margin"],
            str(row["team"]).casefold(),
        )
    )
    wins.sort(
        key=lambda row: (
            -(row["entering_record"]["wins"] > row["entering_record"]["losses"])
            if row["entering_record"]
            else 0,
            row["margin"],
            row["points"] + row["opponent_points"],
            str(row["team"]).casefold(),
        )
    )
    bad_beat = next((row for row in losses if row["record_status"] == "VERIFIED"), None)
    escape = next(
        (
            row
            for row in wins
            if row["record_status"] == "VERIFIED"
            and bad_beat
            and row["roster_id"] != bad_beat["roster_id"]
            and row["matchup_id"] != bad_beat["matchup_id"]
        ),
        None,
    )
    if bad_beat and not escape:
        escape_status = {
            "status": "MANUAL_REVIEW",
            "reason": "No verified Escape Artist candidate remains after excluding Bad Beat's manager and matchup.",
        }
    elif not bad_beat or not escape:
        escape_status = {
            "status": "UNAVAILABLE",
            "reason": "Verified entering records and a distinct completed matchup are required for non-overlapping awards.",
        }
    else:
        escape_status = {"status": "READY", "reason": None}
    bad_status = (
        {"status": "READY", "reason": None}
        if bad_beat
        else {
            "status": "UNAVAILABLE",
            "reason": "Verified entering records are required to prioritize Bad Beat candidates.",
        }
    )
    return {
        "most_efficient_manager": most_efficient,
        "bad_beat": bad_beat,
        "bad_beat_candidates": losses,
        "bad_beat_status": bad_status,
        "escape_artist": escape,
        "escape_artist_candidates": wins,
        "escape_artist_status": escape_status,
    }


def _rookie_weekly_awards(
    weekly: dict[str, Any],
    snapshot: dict[str, Any],
    intelligence: dict[str, Any],
) -> dict[str, Any]:
    from .honors import frozen_projections
    from .weekly_features import _free_agent_of_week, _rookie_of_week, _rostered_player_weeks

    players = snapshot.get("players") or {}
    rookie_rows = []
    for row in _rostered_player_weeks(snapshot):
        player = players.get(str(row.get("player_id") or "")) or {}
        if player.get("years_exp") is None or _safe_int(player.get("years_exp")) != 0:
            continue
        rookie_rows.append(dict(row))

    projections, _, projection_error = frozen_projections(snapshot)
    disappointment = []
    for row in rookie_rows:
        item = dict(row)
        player_id = str(row.get("player_id") or "")
        projection = projections.get(player_id)
        item["projection_status"] = "VERIFIED" if projection is not None else "UNAVAILABLE"
        item["projected_points"] = projection
        item["projection_delta"] = (
            round(float(row.get("points") or 0) - float(projection), 2)
            if projection is not None
            else None
        )
        disappointment.append(item)
    disappointment = _attach_rookie_draft_context(disappointment, snapshot)
    # Draft cost is a secondary tie-breaker: early picks rank ahead of later picks.
    disappointment.sort(
        key=lambda row: (
            row.get("status") != "STARTED",
            row.get("projection_delta") is None,
            row.get("projection_delta") if row.get("projection_delta") is not None else 0,
            float(row.get("points") or 0),
            _safe_int(row.get("ironbound_draft_round")) or 99,
            _safe_int(row.get("ironbound_draft_slot")) or 99,
        )
    )
    raw_rookie = weekly.get("rookie_of_the_week") or _rookie_of_week(snapshot)
    raw_starter = max(
        (row for row in rookie_rows if row.get("status") == "STARTED"),
        key=lambda row: (float(row.get("points") or 0), str(row.get("player") or "").casefold()),
        default=None,
    )
    projections_complete = bool(rookie_rows) and all(
        row.get("projection_status") == "VERIFIED" for row in disappointment
    )
    if raw_rookie:
        raw_rookie = _attach_rookie_draft_context([raw_rookie], snapshot)[0]
    if raw_starter:
        raw_starter = _attach_rookie_draft_context([raw_starter], snapshot)[0]
    free_agent = weekly.get("free_agent_of_the_week") or _free_agent_of_week(snapshot)
    free_agent = _unrostered_free_agent(free_agent, intelligence)
    if not rookie_rows:
        disappointment_status = {
            "status": "UNAVAILABLE",
            "reason": "No eligible rostered rookies were captured for the reviewed week.",
        }
    elif projections_complete and not projection_error:
        disappointment_status = {"status": "READY", "reason": None}
    else:
        disappointment_status = {
            "status": "PARTIAL",
            "reason": projection_error
            or "Verified player projections are incomplete; projection deltas are omitted where unavailable.",
        }
    return {
        "rookie_of_the_week": _attach_stat_lines(raw_rookie, intelligence),
        "top_rookie_starter": _attach_stat_lines(raw_starter, intelligence),
        "rookie_disappointment_candidates": _attach_stat_lines(disappointment, intelligence),
        "rookie_disappointment_status": disappointment_status,
        "free_agent_of_the_week": free_agent,
        "weekly_player_awards": {
            "overall": "overall_player_of_the_week",
            "positional": [f"started_position_leaders.{position}" for position in CORE_POSITIONS],
            "distinct_player_rule": "Each positional leader excludes the overall player winner.",
        },
    }


def _distinct_started_position_leaders(
    snapshot: dict[str, Any], overall: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    from .weekly_features import _rostered_player_weeks

    overall_player_id = str((overall or {}).get("player_id") or "")
    leaders: dict[str, dict[str, Any]] = {}
    for row in _rostered_player_weeks(snapshot):
        position = str(row.get("position") or "").upper()
        if (
            row.get("status") != "STARTED"
            or position not in CORE_POSITIONS
            or str(row.get("player_id") or "") == overall_player_id
        ):
            continue
        current = leaders.get(position)
        if current is None or (
            float(row.get("points") or 0), str(row.get("player") or "").casefold()
        ) > (
            float(current.get("points") or 0), str(current.get("player") or "").casefold()
        ):
            leaders[position] = dict(row)
    return leaders


def _unrostered_free_agent(value: Any, intelligence: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        **_attach_stat_lines(dict(value), intelligence),
        "fantasy_team": "UNROSTERED",
    }


def _season_efficiency_top_three(
    history: list[dict[str, Any]],
    *,
    snapshot: dict[str, Any],
    league_key: str,
    season: str,
    chronicle: ChronicleQueries | None,
) -> list[dict[str, Any]]:
    from .weekly_features import _lineup_efficiency
    names = _roster_team_names(snapshot)
    through = int(snapshot.get("week") or 0)
    by_week_team = {}
    for dossier in history:
        week = int(dossier.get("week") or 0)
        if not 0 < week <= through:
            continue
        for row in dossier.get("lineup_efficiency") or []:
            team = names.get(int(row.get("roster_id") or 0)) or row.get("team")
            if team:
                by_week_team[(week, team)] = row
    if chronicle is not None:
        for row in chronicle.season_efficiency(league_key, season):
            week = int(row.get("week") or 0)
            team = names.get(int(row.get("roster_id") or 0))
            if team and 0 < week <= through:
                by_week_team[(week, team)] = row
    # Fresh current-week evidence wins, without depending on ledger write timing.
    if (snapshot.get("league") or {}).get("roster_positions"):
        for row in _lineup_efficiency(snapshot):
            by_week_team[(through, row["team"])] = row
    by_team = {}
    max_week = max((w for w, _ in by_week_team), default=0)
    for (week, team), row in by_week_team.items():
        aggregate = by_team.setdefault(team, {"actual": 0.0, "optimal": 0.0, "weeks": 0.0})
        aggregate["actual"] += float(row.get("actual_points") or 0)
        aggregate["optimal"] += float(row.get("optimal_points") or 0)
        aggregate["weeks"] += 1
    rows = [
        {
            "team": team,
            "efficiency": round(
                values["actual"] / values["optimal"], 4
            ) if values["optimal"] else 0.0,
            "actual_points": round(values["actual"], 2),
            "optimal_points": round(values["optimal"], 2),
            "weeks": int(values["weeks"]),
            "through_week": max_week,
        }
        for team, values in by_team.items()
        if values["weeks"]
    ]
    rows.sort(key=lambda row: (-row["efficiency"], -row["weeks"], row["team"].casefold()))
    return rows[:3]


def _power_board_inputs(
    dossier: dict[str, Any],
    external: ExternalEditorialInputs,
    *,
    snapshot: dict[str, Any],
    league_key: str,
    season: str,
    chronicle: ChronicleQueries | None,
) -> list[dict[str, Any]]:
    standings = (
        (dossier.get("rankings") or {}).get("official_standings")
        or dossier.get("standings")
        or []
    )
    efficiency = {
        int(row.get("roster_id") or 0): row
        for row in dossier.get("lineup_efficiency") or []
    }
    rows = []
    for row in standings:
        rid = int(row.get("roster_id") or 0)
        team = str(row.get("team") or "")
        eff = efficiency.get(rid) or {}
        franchise_key = (
            chronicle.identity_for_roster(league_key, season, rid)
            if chronicle is not None
            else None
        )
        ranking = external.ranking_for_roster(
            rid,
            franchise_key=franchise_key,
            team=team,
        )
        rows.append(
            {
                **row,
                "franchise_key": franchise_key,
                "efficiency": eff.get("efficiency"),
                "points_left_on_bench": eff.get("points_left_on_bench"),
                "official_rank": ranking.rank if ranking else None,
                "previous_rank": ranking.previous_rank if ranking else None,
                "rank_movement": ranking.movement if ranking else None,
                "ranking_score": ranking.score if ranking else None,
                "ranking_components": dict(ranking.components) if ranking else {},
                "playoff_odds": _row_for_team(
                    external.playoff_odds, rid, franchise_key, team
                ),
                "usage": _row_for_team(external.usage, rid, franchise_key, team),
                "war": _row_for_team(external.war, rid, franchise_key, team),
                "cwar": _row_for_team(external.cwar, rid, franchise_key, team),
            }
        )
    rows.sort(
        key=lambda row: (
            int(row.get("official_rank") or 999),
            str(row.get("team") or "").casefold(),
        )
    )
    return rows


def _row_for_team(
    rows: Any,
    roster_id: int,
    franchise_key: str | None,
    team: str,
) -> dict[str, Any] | None:
    wanted_team = str(team or "").strip().casefold()
    for row in rows or []:
        if row.get("roster_id") is not None:
            try:
                if int(row.get("roster_id")) == int(roster_id):
                    return dict(row)
            except (TypeError, ValueError):
                pass
    if franchise_key:
        for row in rows or []:
            if str(row.get("franchise_key") or "") == str(franchise_key):
                return dict(row)
    if wanted_team:
        for row in rows or []:
            if str(row.get("team") or "").strip().casefold() == wanted_team:
                return dict(row)
    return None


def _attach_stat_lines(value: Any, intelligence: dict[str, Any]) -> Any:
    stat_book = intelligence.get("stat_book") or {}
    source_rows = (
        stat_book.get("rostered_records")
        or stat_book.get("records")
        or []
    )
    by_sleeper = {
        str(row.get("sleeper_player_id")): row
        for row in source_rows
        if row.get("sleeper_player_id")
    }

    def enrich(row: dict[str, Any]) -> dict[str, Any]:
        stat = by_sleeper.get(str(row.get("player_id") or "")) or {}
        return {
            **row,
            "nfl_stat_line": stat.get("nfl_stat_line"),
            "snap_share": stat.get("snap_share"),
            "target_share": stat.get("target_share"),
            "carry_share": stat.get("carry_share"),
        }

    if value is None:
        return None
    if isinstance(value, list):
        return [enrich(dict(row)) for row in value]
    if isinstance(value, dict):
        if "player_id" in value:
            return enrich(dict(value))
        return {
            key: enrich(dict(row)) if isinstance(row, dict) else row
            for key, row in value.items()
        }
    return value


def _attach_rookie_draft_context(
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    draft_source = (
        ((snapshot.get("flagship_sleeper") or {}).get("drafts") or {})
        or (snapshot.get("draft_context") or {})
    )
    current_names = _roster_team_names(snapshot)
    team_count = max(1, len(current_names))
    by_player: dict[str, dict[str, Any]] = {}

    for record in draft_source.get("records") or []:
        draft = record.get("draft") or {}
        draft_season = str(draft.get("season") or "")
        league_season = str((snapshot.get("league") or {}).get("season") or "")
        if league_season and draft_season and draft_season != league_season:
            continue
        for pick in record.get("picks") or []:
            player_id = str(pick.get("player_id") or "")
            if not player_id:
                continue
            round_no = _safe_int(pick.get("round"))
            slot = _safe_int(pick.get("draft_slot"))
            pick_no = _safe_int(pick.get("pick_no"))
            if slot is None and round_no and pick_no:
                slot = pick_no - (round_no - 1) * team_count
            if round_no is None or slot is None or slot <= 0:
                continue
            by_player[player_id] = {
                "round": round_no,
                "slot": slot,
                "roster_id": _safe_int(pick.get("roster_id")),
            }

    enriched = []
    for row in rows:
        item = dict(row)
        pick = by_player.get(str(item.get("player_id") or ""))
        if pick:
            label = f"{pick['round']}.{pick['slot']:02d}"
            drafting_roster = pick.get("roster_id")
            drafting_team = current_names.get(int(drafting_roster or 0))
            current_team = str(item.get("team") or "")
            if drafting_team and drafting_team != current_team:
                label += f" — drafted by {drafting_team}"
            item["ironbound_draft"] = label
            item["ironbound_draft_round"] = pick["round"]
            item["ironbound_draft_slot"] = pick["slot"]
            item["ironbound_drafted_by"] = drafting_team
        else:
            item["ironbound_draft"] = None
        enriched.append(item)
    return enriched


def _safe_int(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and abs(parsed) != float("inf") else None


def _usage_desk(intelligence: dict[str, Any]) -> dict[str, Any]:
    """Create a weekly magazine usage desk from internally collected NFL data."""
    source_status = intelligence.get("source_status") or {}
    stat_book = intelligence.get("stat_book") or {}
    rows = list(stat_book.get("rostered_records") or stat_book.get("records") or [])
    player_stats_ready = (
        str(source_status.get("player_stats") or "").casefold() == "available"
        and str(stat_book.get("status") or "").casefold() == "available"
        and bool(rows)
    )

    active = [
        dict(row)
        for row in rows
        if any(
            float(row.get(key) or 0) > 0
            for key in (
                "carries",
                "targets",
                "offense_snaps",
                "red_zone_opportunities",
                "inside_10_opportunities",
                "inside_5_opportunities",
            )
        )
    ]

    def top(field: str, limit: int = 8) -> list[dict[str, Any]]:
        candidates = [row for row in active if row.get(field) is not None]
        candidates.sort(
            key=lambda row: (
                -float(row.get(field) or 0),
                str(row.get("player") or "").casefold(),
            )
        )
        return candidates[:limit]

    return {
        "status": "READY" if player_stats_ready else "MANUAL_VERIFY",
        "required_source": "nflverse weekly player stats",
        "enrichment_status": {
            "player_stats": source_status.get("player_stats") or "unavailable",
            "snap_counts": source_status.get("snap_counts") or "unavailable",
            "play_by_play": source_status.get("play_by_play") or "unavailable",
        },
        "rostered_player_rows": rows,
        "leaders": {
            "targets": top("targets"),
            "carries": top("carries"),
            "snap_share": top("snap_share"),
            "red_zone_opportunities": top("red_zone_opportunities"),
        },
        "story_signals": list(intelligence.get("story_signals") or []),
    }


def _roster_team_names(snapshot: dict[str, Any]) -> dict[int, str]:
    users = {
        str(row.get("user_id")): row for row in snapshot.get("users") or []
    }
    names: dict[int, str] = {}
    for roster in snapshot.get("rosters") or []:
        roster_id = int(roster.get("roster_id") or 0)
        owner = users.get(str(roster.get("owner_id"))) or {}
        metadata = owner.get("metadata") or {}
        names[roster_id] = str(
            metadata.get("team_name")
            or owner.get("display_name")
            or f"Roster {roster_id}"
        )
    return names


def _optional_external_status(supplied: bool) -> str:
    return "READY" if supplied else "OPTIONAL_NOT_SUPPLIED"


def _external_status(supplied: bool) -> str:
    return "READY" if supplied else "AWAITING_TUESDAY_INPUT"


def _duplicates(values: Any) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _compact(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(", ", ": "))
