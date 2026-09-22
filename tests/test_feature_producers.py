from editorial_desk.feature_producers import (
    bench_blast,
    bench_leader,
    divisional_started_mvps,
    game_window_context,
    league_wide_started_mvp,
    position_leaders,
    record_watch,
    result_flipping_decisions,
    waiver_impact,
    winning_decision_swings,
    workload_stat_lines,
)


def _snapshot():
    return {
        "league": {
            "roster_positions": ["QB", "IDP_FLEX", "BN"],
            "metadata": {"division_1": "East", "division_2": "West"},
            "scoring_settings": {"pass_yd": 0.04},
        },
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
            {"user_id": "u3", "display_name": "Three", "metadata": {"team_name": "Three"}},
            {"user_id": "u4", "display_name": "Four", "metadata": {"team_name": "Four"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["q1", "l1", "qb1"], "settings": {"division": 1}},
            {"roster_id": 2, "owner_id": "u2", "players": ["q2", "l2", "qb2"], "settings": {"division": 1}},
            {"roster_id": 3, "owner_id": "u3", "players": ["q3", "l3", "qb3"], "settings": {"division": 2}},
            {"roster_id": 4, "owner_id": "u4", "players": ["q4", "l4", "qb4"], "settings": {"division": 2}},
        ],
        "players": {
            "q1": {"full_name": "Q One", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "qb1": {"full_name": "Q One Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "l1": {"full_name": "LB One", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 3},
            "q2": {"full_name": "Q Two", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "qb2": {"full_name": "Q Two Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "l2": {"full_name": "LB Two", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 3},
            "q3": {"full_name": "Q Three", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "qb3": {"full_name": "Q Three Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "l3": {"full_name": "LB Three", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 0},
            "q4": {"full_name": "Q Four", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "qb4": {"full_name": "Q Four Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3},
            "l4": {"full_name": "LB Four", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 3},
        },
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 30, "starters": ["q1", "l1"], "players": ["q1", "l1", "qb1"], "players_points": {"q1": 20, "l1": 10, "qb1": 5}},
            {"matchup_id": 1, "roster_id": 2, "points": 28, "starters": ["q2", "l2"], "players": ["q2", "l2", "qb2"], "players_points": {"q2": 18, "l2": 10, "qb2": 25}},
            {"matchup_id": 2, "roster_id": 3, "points": 29, "starters": ["q3", "l3"], "players": ["q3", "l3", "qb3"], "players_points": {"q3": 15, "l3": 14, "qb3": 5}},
            {"matchup_id": 2, "roster_id": 4, "points": 28, "starters": ["q4", "l4"], "players": ["q4", "l4", "qb4"], "players_points": {"q4": 14, "l4": 14, "qb4": 1}},
        ],
        "transactions": [
            {"transaction_id": "w1", "status": "complete", "type": "waiver", "adds": {"q3": 3}, "drops": {}, "settings": {"waiver_bid": 9}}
        ],
        "ranking_inputs": {"sleeper_projections": {"status": "available", "players": {}}},
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {"player_id": "q1", "player_name": "Q One", "position": "QB", "attempts": 35, "passing_yards": 310, "passing_tds": 3},
                    {"player_id": "q2", "player_name": "Q Two", "position": "QB", "attempts": 42, "passing_yards": 280, "passing_tds": 2},
                    {"player_id": "r1", "player_name": "Runner", "position": "RB", "carries": 25, "rushing_yards": 130, "rushing_tds": 1},
                    {"player_id": "w1", "player_name": "Receiver", "position": "WR", "receptions": 11, "receiving_yards": 145, "receiving_tds": 2}
                ]
            }
        },
    }


def _dossier():
    return {
        "scoreboard": [
            {"winner": {"roster_id": 1, "team": "One", "points": 30}, "loser": {"roster_id": 2, "team": "Two", "points": 28}, "margin": 2},
            {"winner": {"roster_id": 3, "team": "Three", "points": 29}, "loser": {"roster_id": 4, "team": "Four", "points": 28}, "margin": 1},
        ],
        "record_watch": [{"record_type": "weekly_high_score", "value": 30}],
    }


def test_legal_bench_swap_that_changes_winner_is_reported():
    flips = result_flipping_decisions(_snapshot(), _dossier())
    flip = next(row for row in flips if row["roster_id"] == 2)
    assert flip["started_player"] == "Q Two"
    assert flip["bench_player"] == "Q Two Bench"
    assert flip["point_swing"] == 7
    assert flip["hypothetical_team_points"] == 35
    assert flip["would_flip_result"] is True


def test_winning_decision_swing_is_distinct_from_efficiency():
    calls = winning_decision_swings(_snapshot(), _dossier())
    call = next(row for row in calls if row["roster_id"] == 3)
    assert call["started_player"] == "Q Three"
    assert call["bench_player"] == "Q Three Bench"
    assert call["point_swing"] == 10
    assert call["victory_margin"] == 1
    assert call["protected_win"] is True


def test_volunteer_style_mvp_is_single_highest_started_player_league_wide():
    mvp = league_wide_started_mvp(_snapshot())
    assert mvp["player"] == "Q One"
    assert mvp["points"] == 20
    assert mvp["status"] == "STARTED"


def test_saturday_divisional_mvps_and_gold_foil_use_started_players():
    mvps = divisional_started_mvps(_snapshot())
    assert {row["division_name"] for row in mvps} == {"East", "West"}
    assert sum(1 for row in mvps if row["gold_foil"]) == 1
    assert next(row for row in mvps if row["gold_foil"])["player"] == "Q One"


def test_position_leaders_include_idp_and_preserve_lineup_status():
    leaders = position_leaders(_snapshot())
    assert leaders["QB"]["player"] == "Q Two Bench"
    assert leaders["QB"]["status"] == "BENCH"
    assert leaders["LB"]["player"] in {"LB Three", "LB Four"}
    assert leaders["LB"]["status"] == "STARTED"


def test_bench_leader_and_bench_blast_are_not_started_players():
    leader = bench_leader(_snapshot())
    blast = bench_blast(_snapshot())
    assert leader["player"] == "Q Two Bench"
    assert leader["status"] == "BENCH"
    assert blast["player"] == "Q Two Bench"


def test_waiver_impact_preserves_faab_lineup_and_result_relevance():
    rows = waiver_impact(_snapshot(), _dossier())
    waiver = next(row for row in rows if row["transaction_id"] == "w1")
    assert waiver["transaction_type"] == "waiver"
    assert waiver["faab"] == 9
    assert waiver["started"] is True
    assert waiver["points"] == 15
    assert waiver["result_relevant"] is True


def test_record_watch_carries_incomplete_chronicle_warning():
    result = record_watch(
        _dossier(),
        {"coverage": {"complete": False, "warnings": ["2024 transactions unavailable"]}},
    )
    assert result["records"] == _dossier()["record_watch"]
    assert result["coverage_complete"] is False
    assert result["coverage_warnings"] == ["2024 transactions unavailable"]


def test_workload_stat_lines_uses_real_nfl_volume_not_fantasy_points():
    snapshot = _snapshot()
    snapshot["rosters"][0]["players"].extend(["r1", "w1"])
    snapshot["players"]["r1"] = {
        "full_name": "Runner",
        "position": "RB",
        "fantasy_positions": ["RB"],
    }
    snapshot["players"]["w1"] = {
        "full_name": "Receiver",
        "position": "WR",
        "fantasy_positions": ["WR"],
    }
    result = workload_stat_lines(snapshot)
    assert result.status == "ready"
    assert result.data["passing_attempts"]["player_name"] == "Q Two"
    assert result.data["passing_yards"]["player_name"] == "Q One"
    assert result.data["rushing_attempts"]["player_name"] == "Runner"
    assert result.data["receptions"]["player_name"] == "Receiver"
    assert result.data["rushing_attempts"]["fantasy_team"] == "One"


def test_game_window_context_reuses_monday_timing_dossier_when_no_window_source():
    snapshot = _snapshot()
    dossier = _dossier()
    dossier["game_timing"] = {
        "monday": {
            "matchups": [
                {
                    "matchup_id": 1,
                    "completed": True,
                    "day_was_active": True,
                    "final_margin": 2,
                    "final_winner": "One",
                    "final_loser": "Two",
                    "winner_score_before_day": 10,
                    "loser_score_before_day": 25,
                    "lead_changed_on_day": True,
                    "tie_broken_on_day": False,
                    "margin_supplied_by_day": True,
                    "teams": [
                        {
                            "roster_id": 1,
                            "team": "One",
                            "points": 30,
                            "day_points": 20,
                            "players": [
                                {
                                    "player_id": "q1",
                                    "player": "Q One",
                                    "fantasy_points": 20,
                                    "nfl_stat_line": "24/31 passing for 287 yards, 3 TD",
                                }
                            ],
                        },
                        {
                            "roster_id": 2,
                            "team": "Two",
                            "points": 28,
                            "day_points": 3,
                            "players": [],
                        },
                    ],
                }
            ]
        }
    }

    result = game_window_context(snapshot, dossier)

    assert result.status == "ready"
    assert result.data[0]["window"] == "Monday"
    assert result.data[0]["swung_result"] is True
    assert result.data[0]["remaining_players"][0]["player"] == "Q One"
    assert "287 yards" in result.data[0]["remaining_players"][0]["nfl_stat_line"]
