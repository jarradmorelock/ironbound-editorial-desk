import json

from editorial_desk.feature_producers import workload_stat_lines
from editorial_desk.newspaper_research import (
    build_newspaper_research_packet,
    render_newspaper_research_packet,
)


def _department(feature, name=None, status="ready", data=None):
    return {
        "feature": feature,
        "display_name": name or feature,
        "required_in_phase": True,
        "status": status,
        "data": {} if data is None else data,
        "reason": None,
        "degraded": False,
    }


def _packet(key, features):
    return {
        "publication_key": key,
        "publication": key.replace("_", " ").title(),
        "week": 2,
        "departments": [_department(feature) for feature in features],
    }


def test_volunteer_contract_rejects_division_leak_and_names_family_rules():
    features = [
        "weekly_results",
        "record_watch",
        "manager_decision_evidence",
        "official_table",
        "league_median",
        "ranking_movement",
        "league_wide_started_mvp",
        "manager_of_week",
        "bench_leaders",
        "rookie_of_week",
        "free_agent_of_week",
        "lineup_efficiency",
        "bad_beat",
        "escape_artist",
        "waiver_impact",
        "bench_blast",
        "health_status",
        "next_matchups",
    ]
    packet = _packet("volunteer_voice", features)
    research = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"information_current_through": "2026-09-22", "roster_health": {"status": "available"}},
        packet,
    )
    assert research["validation"]["contract_valid"] is True
    text = render_newspaper_research_packet(research)
    assert "Rocky Top Rumble divisions are disabled" in text
    assert "Mountain MVP" not in json.dumps(research["validation"])

    leaked = json.loads(json.dumps(packet))
    leaked["departments"].append(
        _department("division_metrics", data=[{"division_name": "Holler"}])
    )
    bad = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"roster_health": {"status": "available"}},
        leaked,
    )
    assert bad["validation"]["contract_valid"] is False
    assert any("division" in row.lower() for row in bad["validation"]["manual_verify"])


def test_ballad_contract_requires_median_and_late_window_evidence():
    features = [
        "weekly_results",
        "league_median",
        "game_window_context",
        "final_scorecard",
        "lineup_flip_candidates",
        "standings",
        "ranking_movement",
        "weekly_honors",
        "player_position_leaders",
        "waiver_impact",
        "health_status",
        "record_watch",
        "next_matchups",
    ]
    research = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"roster_health": {"status": "available"}},
        _packet("ballad_crier", features),
    )
    assert research["validation"]["contract_valid"] is True
    names = [row["feature"] for row in research["sections"]]
    assert names.index("league_median") < names.index("game_window_context")
    assert names.index("game_window_context") < names.index("lineup_flip_candidates")


def test_saturday_conditional_dynasty_modules_do_not_block_core_contract():
    required = [
        "weekly_results",
        "opening_statement_inputs",
        "game_window_context",
        "weekly_ledger",
        "division_metrics",
        "ranking_movement",
        "lineup_efficiency",
        "lineup_flip_candidates",
        "waiver_impact",
        "divisional_started_mvps",
        "manager_of_week",
        "idp_position_metrics",
        "weekly_desk_honors",
        "dynasty_market_values",
        "health_status",
    ]
    research = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"roster_health": {"status": "available"}},
        _packet("saturday_standard", required),
    )
    assert research["validation"]["contract_valid"] is True
    assert set(research["validation"]["conditional_departments"]) == {
        "transactions",
        "rookie_draft",
        "future_picks",
        "next_matchups",
    }


def test_stampede_workload_stats_are_limited_to_rostered_players():
    snapshot = {
        "users": [{"user_id": "u1", "display_name": "Cheese", "metadata": {"team_name": "Cheese"}}],
        "rosters": [{"roster_id": 1, "owner_id": "u1", "players": ["s1"]}],
        "players": {
            "s1": {"full_name": "Rostered Runner", "position": "RB", "gsis_id": "g1"},
            "s2": {"full_name": "Unrostered Star", "position": "RB", "gsis_id": "g2"},
        },
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {"player_id": "g1", "player_display_name": "Rostered Runner", "carries": 20, "rushing_yards": 100, "targets": 3},
                    {"player_id": "g2", "player_display_name": "Unrostered Star", "carries": 30, "rushing_yards": 200, "targets": 9},
                ],
            }
        },
    }
    result = workload_stat_lines(snapshot)
    assert result.status == "ready"
    assert result.data["rushing_attempts"]["player_display_name"] == "Rostered Runner"
    assert result.data["rushing_attempts"]["fantasy_team"] == "Cheese"
    assert "Unrostered Star" not in json.dumps(result.data)


def test_newspaper_renderer_surfaces_median_line_cleanly():
    features = [
        "weekly_results",
        "league_median",
        "game_window_context",
        "final_scorecard",
        "lineup_flip_candidates",
        "standings",
        "ranking_movement",
        "weekly_honors",
        "player_position_leaders",
        "waiver_impact",
        "health_status",
        "record_watch",
        "next_matchups",
    ]
    packet = _packet("ballad_crier", features)
    packet["departments"][1]["data"] = {
        "enabled": True,
        "points": 136.36,
        "results": [{"team": "Alpha", "result": "win"}],
    }
    research = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"roster_health": {"status": "available"}},
        packet,
    )
    text = render_newspaper_research_packet(research)
    assert "Median line: 136.36" in text
    assert "Above median: Alpha" in text


def test_newspaper_renderer_never_uses_json_only_placeholder():
    packet = _packet("saturday_standard", ["dynasty_market_values"])
    packet["departments"][0]["data"] = {
        "p1": {
            "full_name": "Example Receiver",
            "position": "WR",
            "team": "TEN",
            "trade_value": 5123,
            "overall_rank": 18,
        }
    }
    research = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"roster_health": {"status": "available"}},
        packet,
    )
    text = render_newspaper_research_packet(research)

    assert "Example Receiver (WR, TEN)" in text
    assert "value 5123" in text
    assert "Structured evidence is present" not in text


def test_newspaper_health_renderer_drops_bare_active_noise():
    packet = _packet("the_stampede", ["health_status"])
    packet["departments"][0]["data"] = [
        {
            "team": "Alpha",
            "player": "Healthy Star",
            "position": "RB",
            "nfl_team": "TEN",
            "status": "Active",
        },
        {
            "team": "Beta",
            "player": "Questionable Star",
            "position": "WR",
            "nfl_team": "KC",
            "status": "Active",
            "game_designation": "Questionable",
            "injury": "Hamstring",
            "practice_participation": "Limited Participation",
        },
    ]
    research = build_newspaper_research_packet(
        {"matchups": [], "next_matchups": {"status": "available"}, "nfl_context": {}},
        {"roster_health": {"status": "available"}},
        packet,
    )
    text = render_newspaper_research_packet(research)

    assert "Questionable Star" in text
    assert "Hamstring" in text
    assert "Healthy Star" not in text
