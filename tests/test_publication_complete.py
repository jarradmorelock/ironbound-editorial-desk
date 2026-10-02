from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.publication_complete import (
    build_publication_complete_packet,
    validate_publication_complete_packet,
)


def _snapshot(publication_key="ironbound_weekly"):
    return {
        "week": 3,
        "league": {"season": "2026"},
        "editorial": {
            "league_key": "ironbound_sixteen",
            "publication_profile": {"key": publication_key},
        },
    }


def _canonical():
    games = []
    for matchup_id in range(1, 9):
        games.extend(
            [
                {"week": 3, "matchup_id": matchup_id, "roster_id": matchup_id * 2 - 1, "team": f"Team {matchup_id * 2 - 1}", "points": 100.0},
                {"week": 3, "matchup_id": matchup_id, "roster_id": matchup_id * 2, "team": f"Team {matchup_id * 2}", "points": 90.0},
            ]
        )
    return {
        "coverage": {"status": "READY", "weeks": [1, 2, 3]},
        "historical_matchups": games,
        "entering_records": {"3": {str(i): {"wins": 1, "losses": 1, "ties": 0} for i in range(1, 17)}},
        "team_season_totals": {str(i): {"roster_id": i, "points": 300.0, "through_week": 3} for i in range(1, 17)},
        "player_season_totals": {"p1": {"player_id": "p1", "points": 60.0, "through_week": 3}},
        "player_season_totals_status": "READY",
        "division_summary": {"status": "READY", "divisions": {"1": {"scoring_average": 100.0}}},
        "evidence_index": {"fact:1": {"evidence_id": "fact:1"}},
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
        {"matchup_id": i, "roster_one": 2*i-1, "roster_two": 2*i, "projected_margin": 5}
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
            "overall_player_of_the_week": {"player_id": "p1"},
            "started_position_leaders": {
                "QB": {"player_id": "q"},
                "RB": {"player_id": "r"},
                "WR": {"player_id": "w"},
                "TE": {"player_id": "t"},
            },
            "benchwarmer_of_the_week": {"player_id": "b"},
            "rookie_watch_top_five": [{"player_id": f"rookie{i}"} for i in range(5)],
            "rookie_of_the_week": {"player_id": "rookie0"},
            "season_efficiency_top_three": [{"roster_id": 1, "weeks": 3}],
            "season_team_score_top_three": [{"roster_id": 1, "weeks": 3}],
            "player_season_top_three": {"status": "READY", "by_position": {"QB": [{"player_id": "q"}]}},
            "rookie_season_leaders": {"status": "READY", "by_position": {"WR": [{"player_id": "rookie0"}]}},
            "rotating_award_candidates": [],
            "rotating_award_manual_review": [],
            "award_audit": {},
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
