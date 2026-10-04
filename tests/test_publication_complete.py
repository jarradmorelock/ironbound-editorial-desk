from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.publication_complete import (
    build_publication_complete_packet,
    validate_publication_complete_packet,
)


def _snapshot(publication_key="ironbound_weekly"):
    users = [
        {
            "user_id": f"u{roster_id}",
            "display_name": f"Owner {roster_id}",
            "metadata": {"team_name": f"Team {roster_id}"},
        }
        for roster_id in range(1, 17)
    ]
    rosters = [
        {
            "roster_id": roster_id,
            "owner_id": f"u{roster_id}",
            "players": [f"p{roster_id}"],
            "settings": {"division": 1 if roster_id <= 8 else 2},
        }
        for roster_id in range(1, 17)
    ]
    players = {
        f"p{roster_id}": {
            "full_name": f"Player {roster_id}",
            "position": "QB",
            "team": "NFL",
        }
        for roster_id in range(1, 17)
    }
    matchups = [
        {
            "matchup_id": (roster_id + 1) // 2,
            "roster_id": roster_id,
            "points": 100.0 if roster_id % 2 else 90.0,
            "players": [f"p{roster_id}"],
            "starters": [f"p{roster_id}"],
            "players_points": {f"p{roster_id}": 20.0 + roster_id},
        }
        for roster_id in range(1, 17)
    ]
    return {
        "week": 3,
        "league": {
            "season": "2026",
            "roster_positions": ["QB"],
            "metadata": {"division_1": "One", "division_2": "Two"},
        },
        "editorial": {
            "league_key": "ironbound_sixteen",
            "publication_profile": {"key": publication_key},
        },
        "users": users,
        "rosters": rosters,
        "players": players,
        "matchups": matchups,
    }


def _canonical():
    games = []
    player_weeks = []
    evidence_index = {}
    for matchup_id in range(1, 9):
        for roster_id, points in (
            (matchup_id * 2 - 1, 100.0),
            (matchup_id * 2, 90.0),
        ):
            team_eid = f"team-week:2026:3:{roster_id}"
            player_eid = f"player-week:2026:3:{roster_id}:p{roster_id}"
            game = {
                "evidence_id": team_eid,
                "week": 3,
                "matchup_id": matchup_id,
                "roster_id": roster_id,
                "team": f"Team {roster_id}",
                "points": points,
            }
            player = {
                "evidence_id": player_eid,
                "week": 3,
                "roster_id": roster_id,
                "player_id": f"p{roster_id}",
                "points": 20.0 + roster_id,
                "started": True,
            }
            games.append(game)
            player_weeks.append(player)
            evidence_index[team_eid] = game
            evidence_index[player_eid] = player
    team_records = {
        str(i): {
            "roster_id": i,
            "team": f"Team {i}",
            "division": "1" if i <= 8 else "2",
            "overall_record": {"wins": 1, "losses": 1, "ties": 0},
            "division_record": {"wins": 1, "losses": 0, "ties": 0},
            "cross_division_record": {"wins": 0, "losses": 1, "ties": 0},
        }
        for i in range(1, 17)
    }
    return {
        "coverage": {"status": "READY", "weeks": [1, 2, 3]},
        "historical_matchups": games,
        "player_weeks": player_weeks,
        "entering_records": {"3": {str(i): {"wins": 1, "losses": 1, "ties": 0} for i in range(1, 17)}},
        "team_season_totals": {str(i): {"roster_id": i, "points": 300.0, "through_week": 3} for i in range(1, 17)},
        "player_season_totals": {"p1": {"player_id": "p1", "points": 60.0, "through_week": 3}},
        "player_season_totals_status": "READY",
        "division_summary": {
            "status": "READY",
            "divisions": {
                "1": {"division": "1", "scoring_average": 100.0},
                "2": {"division": "2", "scoring_average": 95.0},
            },
            "team_records": team_records,
        },
        "evidence_index": evidence_index,
        "conflicts": [],
    }


def _transactions(unresolved=False):
    pick = {
        "season": "2027",
        "round": 1,
        "original_roster_id": 1,
        "previous_owner_roster_id": None if unresolved else 1,
        "new_owner_roster_id": 2,
    }
    return {
        "coverage": {"status": "READY", "transaction_count": 1},
        "pick_provenance_status": "PARTIAL" if unresolved else "READY",
        "unresolved_pick_provenance": [{"transaction_id": "tx1", "pick": pick}] if unresolved else [],
        "transactions": [
            {
                "transaction_id": "tx1",
                "week": 3,
                "type": "trade",
                "players": {"received_by": {}, "sent_by": {}},
                "draft_picks": [pick],
                "evidence_ids": ["sleeper-transaction:tx1"],
            }
        ],
    }


def _research():
    games = [
        {"matchup_id": i, "matchup": f"Team {2*i-1} vs Team {2*i}", "scoreline": "100-90"}
        for i in range(1, 9)
    ]
    forecast = [
        {
            "matchup_id": i,
            "week": 4,
            "roster_one": 2 * i - 1,
            "roster_two": 2 * i,
            "team_one": f"Team {2 * i - 1}",
            "team_two": f"Team {2 * i}",
            "projected_margin": 5,
            "projected_score_one": 110.0,
            "projected_score_two": 105.0,
            "projected_total": 215.0,
            "optimal_lineup_one": [f"p{2 * i - 1}"],
            "optimal_lineup_two": [f"p{2 * i}"],
            "projection_source": "fixture projections",
        }
        for i in range(1, 9)
    ]
    rankings = [
        {"roster_id": i, "team": f"Team {i}", "rank": i, "previous_rank": i}
        for i in range(1, 17)
    ]
    return {
        "publication_key": "ironbound_weekly",
        "season": "2026",
        "week": 3,
        "game_coverage": {"games": games, "cover_candidates": [{"matchup_id": 1}]},
        "usage_desk": {"status": "READY", "leaders": {}},
        "weekly_honors": {
            "manager_of_the_week": {"roster_id": 1},
            "most_efficient_manager": {"roster_id": 1},
            "bad_beat": {"roster_id": 2},
            "escape_artist": {"roster_id": 3},
            "high_score": {"roster_id": 1, "team": "Team 1", "points": 100.0},
            "low_score": {"roster_id": 16, "team": "Team 16", "points": 90.0},
            "overall_player_of_the_week": {"player_id": "p1"},
            "started_position_leaders": {
                "QB": {"player_id": "q"},
                "RB": {"player_id": "r"},
                "WR": {"player_id": "w"},
                "TE": {"player_id": "t"},
            },
            "benchwarmer_of_the_week": {"player_id": "b"},
            "rookie_watch_top_five": [
                {
                    "player_id": f"rookie{i}",
                    "player": f"Rookie {i}",
                    "team": f"Team {i + 1}",
                    "status": "STARTED",
                    "points": 10.0 + i,
                    "nfl_stat_line": None,
                    "ironbound_draft_status": "NOT_DRAFTED_IN_CAPTURED_LEAGUE_DRAFT",
                    "ironbound_draft_provenance": {"source": "fixture"},
                }
                for i in range(5)
            ],
            "rookie_of_the_week": {"player_id": "rookie0"},
            "season_efficiency_top_three": [{"roster_id": 1, "weeks": 3}],
            "season_team_score_top_three": [{"roster_id": 1, "weeks": 3}],
            "player_season_top_three": {"status": "READY", "by_position": {"QB": [{"player_id": "q"}]}},
            "rookie_season_leaders": {"status": "READY", "by_position": {"WR": [{"player_id": "rookie0"}]}},
            "rotating_award_candidates": [],
            "rotating_award_manual_review": [],
            "award_audit": {"BY_A_RIVET": {"availability": "AVAILABLE"}},
        },
        "story_desk": {"status": "available", "candidates": [{"candidate_id": "story1"}]},
        "power_board": {"writeup_inputs": rankings},
        "power_rankings_chart": {"status": "READY", "rows": rankings, "asset_key": "power_rankings"},
        "playoff_odds_chart": {"status": "READY", "rows": [{"roster_id": i, "playoff": 50} for i in range(1, 17)], "asset_key": "playoff_forecast"},
        "remaining_schedule_strength": {"status": "READY", "rows": [{"roster_id": i, "average": 50} for i in range(1, 17)]},
        "weekly_matchup_forecast": {"status": "READY", "rows": forecast},
        "division_outlook": {"division_status": "READY", "division_summaries": [{"division": "1"}]},
        "ranking_publication_assets": {
            "required": True,
            "assets": {
                "power_rankings": {"status": "READY", "package_path": "publication-assets/ranks.png"},
                "playoff_forecast": {"status": "READY", "package_path": "publication-assets/playoffs.png"},
            },
        },
        "roster_market": {
            "status": "READY",
            "sleeper_platform_rates": {"status": "UNAVAILABLE", "required": False},
        },
    }


def _source_manifest():
    return {
        "information_cutoff": "2026-09-30T18:00:00+00:00",
        "sleeper": {
            "matchups": {"status": "AVAILABLE", "weeks": [1, 2, 3]},
            "transactions": {"status": "AVAILABLE", "weeks": [1, 2, 3]},
            "projections": {"status": "AVAILABLE", "season": "2026", "week": 3},
        },
        "rankings": {"status": "READY", "results_through_week": 3, "ranking_week": 4},
        "publication_assets": {"status": "READY"},
        "beat_news": {"status": "PARTIAL", "blocking": False},
    }


def _health():
    return {
        "status": "READY",
        "information_cutoff": "2026-09-30T18:00:00+00:00",
        "players": [],
        "news_events": [],
    }


def _packet(transactions=None):
    research = _research()
    external = ExternalEditorialInputs("ironbound_weekly", schema_version=3)
    return build_publication_complete_packet(
        _snapshot(),
        {},
        research,
        external,
        canonical_evidence=_canonical(),
        transaction_evidence=transactions or _transactions(),
        source_manifest=_source_manifest(),
        health=_health(),
        publication_assets=(research["ranking_publication_assets"]["assets"]),
    )


def test_complete_flagship_packet_contains_writer_ready_departments():
    packet = _packet()

    assert packet["contract_version"] == "publication-complete-v1"
    assert set(packet) >= {
        "issue_identity",
        "source_manifest",
        "readiness",
        "evidence_index",
        "game_dossiers",
        "feature_evidence",
        "usage_desk",
        "roster_health",
        "transaction_desk",
        "manager_honors",
        "player_honors",
        "rookie_watch",
        "division_report",
        "power_board",
        "playoff_forecast",
        "power_rankings",
        "week_ahead",
        "sources_and_model_notes",
        "publication_assets",
    }
    assert packet["readiness"]["publication_ready"] is True
    assert len(packet["game_dossiers"]) == 8
    assert len(packet["week_ahead"]["rows"]) == 8


def test_missing_required_transaction_pick_provenance_blocks_publication():
    packet = _packet(_transactions(unresolved=True))

    assert packet["readiness"]["publication_ready"] is False
    assert packet["readiness"]["status"] == "BLOCKED"
    assert any(
        gap["section"] == "transaction_desk"
        and gap["code"] == "UNRESOLVED_PICK_PROVENANCE"
        for gap in packet["readiness"]["blocking_gaps"]
    )


def test_optional_market_enrichment_does_not_block_publication():
    packet = _packet()

    assert packet["readiness"]["publication_ready"] is True
    assert any(
        gap["section"] == "optional_market"
        for gap in packet["readiness"]["optional_gaps"]
    )


def test_packet_does_not_require_fixed_page_count():
    packet = _packet()

    assert "required_page_count" not in packet["readiness"]
    assert "page_count" not in packet["issue_identity"]


def test_unbound_uses_same_flagship_readiness_contract():
    packet = _packet()
    packet["issue_identity"]["publication_key"] = "unbound_weekly"

    validation = validate_publication_complete_packet(packet)

    assert validation["profile_tier"] == "flagship"
    assert validation["publication_ready"] is True


def test_flagship_game_dossiers_and_week_ahead_are_writer_ready_offline():
    snapshot = _snapshot()
    snapshot["league"]["roster_positions"] = ["QB"]
    snapshot["users"] = [
        {
            "user_id": f"u{roster_id}",
            "display_name": f"Owner {roster_id}",
            "metadata": {"team_name": f"Team {roster_id}"},
        }
        for roster_id in range(1, 17)
    ]
    snapshot["rosters"] = [
        {
            "roster_id": roster_id,
            "owner_id": f"u{roster_id}",
            "players": [f"p{roster_id}"],
            "settings": {"division": 1 if roster_id <= 8 else 2},
        }
        for roster_id in range(1, 17)
    ]
    snapshot["players"] = {
        f"p{roster_id}": {
            "full_name": f"Player {roster_id}",
            "position": "QB",
            "team": "NFL",
        }
        for roster_id in range(1, 17)
    }
    snapshot["matchups"] = [
        {
            "matchup_id": (roster_id + 1) // 2,
            "roster_id": roster_id,
            "points": 100.0 if roster_id % 2 else 90.0,
            "players": [f"p{roster_id}"],
            "starters": [f"p{roster_id}"],
            "players_points": {f"p{roster_id}": 20.0 + roster_id},
        }
        for roster_id in range(1, 17)
    ]

    canonical = _canonical()
    canonical["historical_matchups"] = [
        {
            **row,
            "evidence_id": f"team-week:2026:3:{row['roster_id']}",
        }
        for row in canonical["historical_matchups"]
    ]
    canonical["player_weeks"] = [
        {
            "evidence_id": f"player-week:2026:3:{roster_id}:p{roster_id}",
            "week": 3,
            "roster_id": roster_id,
            "player_id": f"p{roster_id}",
            "points": 20.0 + roster_id,
            "started": True,
        }
        for roster_id in range(1, 17)
    ]
    canonical["evidence_index"] = {
        row["evidence_id"]: row
        for row in canonical["historical_matchups"] + canonical["player_weeks"]
    }
    canonical["division_summary"]["team_records"] = {
        str(roster_id): {
            "roster_id": roster_id,
            "team": f"Team {roster_id}",
            "division": "1" if roster_id <= 8 else "2",
            "overall_record": {"wins": 1, "losses": 1, "ties": 0},
            "division_record": {"wins": 1, "losses": 0, "ties": 0},
            "cross_division_record": {"wins": 0, "losses": 1, "ties": 0},
        }
        for roster_id in range(1, 17)
    }

    research = _research()
    research["weekly_honors"]["free_agent_of_the_week"] = {
        "player_id": "fa",
        "player": "Free Agent",
    }
    for row in research["weekly_matchup_forecast"]["rows"]:
        left = row["roster_one"]
        right = row["roster_two"]
        row.update(
            {
                "week": 4,
                "team_one": f"Team {left}",
                "team_two": f"Team {right}",
                "projected_score_one": 110.0,
                "projected_score_two": 105.0,
                "projected_total": 215.0,
                "optimal_lineup_one": [f"p{left}"],
                "optimal_lineup_two": [f"p{right}"],
                "projection_source": "fixture projections",
            }
        )

    packet = build_publication_complete_packet(
        snapshot,
        {},
        research,
        ExternalEditorialInputs("ironbound_weekly", schema_version=3),
        canonical_evidence=canonical,
        transaction_evidence=_transactions(),
        source_manifest=_source_manifest(),
        health={
            "status": "READY",
            "information_cutoff": "2026-09-30T18:00:00+00:00",
            "players": [
                {
                    "player_id": "p1",
                    "player": "Player 1",
                    "roster_id": 1,
                    "fantasy_team": "Team 1",
                    "injury_status": "Questionable",
                    "observed_at": "2026-09-30T17:00:00+00:00",
                }
            ],
            "news_events": [],
        },
        publication_assets=research["ranking_publication_assets"]["assets"],
    )

    game = packet["game_dossiers"][0]
    assert game["submitted_lineup_evidence_status"] == "READY"
    assert game["teams"][0]["submitted_starters"][0]["player"] == "Player 1"
    assert game["teams"][0]["submitted_starters"][0]["fantasy_points"] == 21.0
    assert game["teams"][0]["entering_record"] == {"wins": 1, "losses": 1, "ties": 0}
    assert game["teams"][0]["entering_power_rank"] == 1
    assert game["teams"][0]["health_context"][0]["injury_status"] == "Questionable"
    assert game["evidence_ids"]

    ahead = packet["week_ahead"]["rows"][0]
    assert ahead["model_source"] == "fixture projections"
    assert ahead["teams"][0]["optimal_lineup"][0]["player"] == "Player 1"
    assert ahead["teams"][0]["health_caveats"][0]["injury_status"] == "Questionable"
    assert ahead["teams"][0]["division_context"]["division"] == "1"
    assert ahead["evidence_ids"][0] in packet["evidence_index"]
    assert packet["player_honors"]["free_agent_of_the_week"]["player"] == "Free Agent"
