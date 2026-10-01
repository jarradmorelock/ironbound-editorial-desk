import json

from editorial_desk.external_inputs import ExternalEditorialInputs, OfficialPowerRanking
from editorial_desk.flagship_research import (
    build_flagship_research_packet,
    render_flagship_research_packet,
)


def _fixture():
    users = []
    rosters = []
    matchups = []
    players = {}
    scoreboard = []
    stat_rows = []
    standings = []
    efficiency = []
    rookie_watch = []

    for roster_id in range(1, 17):
        team = f"Team {roster_id}"
        player_id = f"p{roster_id}"
        users.append(
            {
                "user_id": f"u{roster_id}",
                "display_name": f"Manager {roster_id}",
                "metadata": {"team_name": team},
            }
        )
        rosters.append(
            {
                "roster_id": roster_id,
                "owner_id": f"u{roster_id}",
                "players": [player_id],
                "reserve": [],
                "taxi": [],
                "settings": {
                    "wins": 1 if roster_id % 2 else 0,
                    "losses": 0 if roster_id % 2 else 1,
                    "ties": 0,
                    "fpts": 100 + roster_id,
                },
            }
        )
        players[player_id] = {
            "full_name": f"Player {roster_id}",
            "position": ("QB", "RB", "WR", "TE")[(roster_id - 1) % 4],
            "years_exp": 0 if roster_id <= 5 else 2,
        }
        points = 100 + roster_id
        matchups.append(
            {
                "matchup_id": (roster_id + 1) // 2,
                "roster_id": roster_id,
                "points": points,
                "starters": [player_id],
                "players": [player_id],
                "players_points": {player_id: points},
            }
        )
        stat_rows.append(
            {
                "sleeper_player_id": player_id,
                "fantasy_team": team,
                "player": f"Player {roster_id}",
                "nfl_player_id": f"g{roster_id}",
                "position": players[player_id]["position"],
                "nfl_team": "TEN",
                "nfl_stat_line": f"{roster_id} touches for {80 + roster_id} yards",
            }
        )
        standings.append(
            {
                "roster_id": roster_id,
                "team": team,
                "wins": 1 if roster_id % 2 else 0,
                "losses": 0 if roster_id % 2 else 1,
                "ties": 0,
                "points_for": points,
            }
        )
        efficiency.append(
            {
                "roster_id": roster_id,
                "team": team,
                "actual_points": points,
                "optimal_points": points + 5,
                "efficiency": round(points / (points + 5), 4),
                "points_left_on_bench": 5,
            }
        )

    for matchup_id in range(1, 9):
        left = 2 * matchup_id - 1
        right = 2 * matchup_id
        left_row = {
            "roster_id": left,
            "team": f"Team {left}",
            "points": 100 + left,
        }
        right_row = {
            "roster_id": right,
            "team": f"Team {right}",
            "points": 100 + right,
        }
        scoreboard.append(
            {
                "matchup_id": matchup_id,
                "teams": [left_row, right_row],
                "winner": right_row,
                "loser": left_row,
                "tie": False,
                "margin": 1,
            }
        )

    for rank in range(1, 6):
        rookie_watch.append(
            {
                "player_id": f"p{rank}",
                "player": f"Player {rank}",
                "team": f"Team {rank}",
                "points": 30 - rank,
                "status": "STARTED",
            }
        )

    snapshot = {
        "week": 4,
        "nfl_state": {"season": "2026"},
        "editorial": {
            "league_key": "ironbound_sixteen",
            "publication": "The Ironbound Weekly",
            "tier": "flagship",
            "publication_profile": {"key": "ironbound_weekly"},
        },
        "league": {"season": "2026"},
        "users": users,
        "rosters": rosters,
        "players": players,
        "matchups": matchups,
        "draft_context": {
            "status": "available",
            "records": [
                {
                    "draft": {"season": "2026", "draft_id": "rookies"},
                    "picks": [
                        {
                            "player_id": "p1",
                            "round": 1,
                            "draft_slot": 3,
                            "pick_no": 3,
                            "roster_id": 2,
                        },
                        {
                            "player_id": "p2",
                            "round": 1,
                            "draft_slot": 4,
                            "pick_no": 4,
                            "roster_id": 2,
                        },
                    ],
                }
            ],
        },
    }

    dossier = {
        "season": "2026",
        "week": 4,
        "information_current_through": "2026-09-21T18:00:00+00:00",
        "league": {
            "league_key": "ironbound_sixteen",
            "publication": "The Ironbound Weekly",
            "tier": "flagship",
        },
        "scoreboard": scoreboard,
        "rankings": {"official_standings": standings},
        "lineup_efficiency": efficiency,
        "weekly_features": {
            "started_position_leaders": {
                position: {
                    "player": f"{position} Leader",
                    "team": "Team 1",
                    "points": 30,
                    "status": "STARTED",
                }
                for position in ("QB", "RB", "WR", "TE")
            },
            "lineup_efficiency_top_three": efficiency[:3],
            "benchwarmer_of_the_week": {
                "player": "Bench Star",
                "team": "Team 8",
                "points": 31.5,
                "status": "BENCH",
            },
            "rookie_watch_top_five": rookie_watch,
            "divisional_mvp_nominees": [],
        },
        "awards": {
            "manager_of_the_week": {
                "team": "Team 2",
                "actual_points": 102,
                "efficiency": 0.99,
            },
            "bad_beat": {
                "team": "Team 15",
                "roster_id": 15,
                "points": 115,
            },
            "escape_artist": {
                "team": "Team 2",
                "roster_id": 2,
                "points": 102,
            },
            "waiver_star_candidates": [
                {
                    "team": "Team 2",
                    "player": "Pickup Player",
                    "points": 22,
                    "victory_margin": 1,
                }
            ],
            "result_flipping_decisions": [],
        },
        "weekly_records": {
            "status": "scoring_available",
            "highest_score": {"team": "Team 16", "points": 116},
        },
        "roster_health": {"status": "available", "players": []},
        "nfl_game_intelligence": {
            "source_status": {
                "player_stats": "available",
                "snap_counts": "available",
                "play_by_play": "available",
            },
            "stat_book": {
                "status": "available",
                "records": stat_rows,
                "missing_starters": [],
            },
            "story_signals": [],
        },
        "game_timing": {"monday": {"lead_changes": []}},
    }
    return snapshot, dossier


def _external():
    return ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=tuple(
            OfficialPowerRanking(f"franchise:{rank}", rank)
            for rank in range(1, 17)
        ),
        playoff_odds=tuple(
            {"franchise_key": f"franchise:{rank}", "playoff": 80 - rank}
            for rank in range(1, 17)
        ),
        usage=({"metric": "usage", "value": 1},),
        war=({"metric": "war", "value": 2},),
        cwar=({"metric": "cwar", "value": 3},),
        source_metadata={"week": 4},
    )


def _write_history(root, dossier):
    for week in range(1, 5):
        value = dict(dossier)
        value["week"] = week
        directory = root / "2026" / f"week-{week:02d}" / "ironbound_sixteen"
        directory.mkdir(parents=True)
        (directory / "dossier.json").write_text(json.dumps(value), encoding="utf-8")


def test_flagship_contract_covers_all_eight_games_and_required_honors(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)

    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
    )

    assert packet["validation"]["contract_valid"] is True
    assert packet["validation"]["research_complete"] is True
    assert len(packet["game_coverage"]["games"]) == 8
    assert packet["game_coverage"]["feature_slots"] == 2
    assert packet["game_coverage"]["remaining_game_writeups"] == 6
    assert len(packet["weekly_honors"]["rookie_watch_top_five"]) == 5
    assert len(packet["weekly_honors"]["season_team_score_top_three"]) == 3
    assert len(packet["weekly_honors"]["season_efficiency_top_three"]) == 3
    assert packet["weekly_honors"]["benchwarmer_of_the_week"]["player"] == "Bench Star"
    assert packet["weekly_honors"]["bad_beat"]["team"] == "Team 15"
    assert packet["weekly_honors"]["escape_artist"]["team"] == "Team 2"


def test_power_board_writeups_precede_rankings_and_playoff_charts(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
    )

    text = render_flagship_research_packet(packet)

    assert text.index("## POWER BOARD — INDIVIDUAL WRITEUP INPUTS") < text.index(
        "## POWER RANKINGS CHART INPUT"
    ) < text.index("## PLAYOFF ODDS CHART INPUT")


def test_missing_tuesday_handoff_is_awaiting_input_not_data_failure(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        ExternalEditorialInputs(publication_key="ironbound_weekly"),
        history_root=tmp_path,
    )

    assert packet["validation"]["contract_valid"] is True
    assert packet["validation"]["research_complete"] is False
    assert packet["validation"]["manual_verify"] == []
    waiting = " ".join(packet["validation"]["awaiting_tuesday_input"])
    assert "Power Rankings" in waiting
    assert "Playoff Odds" in waiting
    assert "WAR" not in waiting
    assert "cWAR" not in waiting
    assert "usage" not in waiting.lower()


def test_internal_usage_makes_packet_complete_without_external_usage_war_or_cwar(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    external = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=tuple(
            OfficialPowerRanking(
                franchise_key=None,
                rank=rank,
                roster_id=rank,
                team=f"Team {rank}",
            )
            for rank in range(1, 17)
        ),
        playoff_odds=tuple(
            {"roster_id": rank, "team": f"Team {rank}", "playoff": 80 - rank}
            for rank in range(1, 17)
        ),
    )

    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        external,
        history_root=tmp_path,
    )

    assert packet["validation"]["research_complete"] is True
    assert packet["validation"]["awaiting_tuesday_input"] == []
    assert packet["usage_desk"]["status"] == "READY"
    assert packet["tuesday_external_inputs"]["war"]["status"] == "OPTIONAL_NOT_SUPPLIED"
    assert packet["tuesday_external_inputs"]["cwar"]["status"] == "OPTIONAL_NOT_SUPPLIED"


def test_usage_desk_ranks_rostered_player_workload_from_internal_nfl_data(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    dossier["nfl_game_intelligence"]["stat_book"]["records"][0].update(
        {
            "carries": 18,
            "carry_share": 0.72,
            "targets": 9,
            "target_share": 0.30,
            "snap_share": 0.88,
            "offense_snaps": 61,
            "red_zone_opportunities": 5,
        }
    )

    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
    )

    usage = packet["usage_desk"]
    assert usage["status"] == "READY"
    assert usage["leaders"]["targets"][0]["player"] == "Player 1"
    assert usage["leaders"]["carries"][0]["carries"] == 18
    text = render_flagship_research_packet(packet)
    assert "## USAGE DESK INPUT" in text
    assert "18 carries" in text
    assert "30.0% team targets" in text
    assert "88.0% snaps" in text
    assert "5 red-zone opps" in text


def test_power_rankings_chart_uses_team_name_when_franchise_key_is_absent(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    external = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=tuple(
            OfficialPowerRanking(
                franchise_key=None,
                rank=rank,
                roster_id=rank,
                team=f"Team {rank}",
            )
            for rank in range(1, 17)
        ),
        playoff_odds=tuple(
            {"roster_id": rank, "team": f"Team {rank}", "playoff": 80 - rank}
            for rank in range(1, 17)
        ),
    )
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        external,
        history_root=tmp_path,
    )
    text = render_flagship_research_packet(packet)
    assert "#1 Team 1" in text
    assert "#1 None" not in text


def test_required_beat_news_source_blocks_completeness_when_unavailable(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)

    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
        beat_report={
            "required": True,
            "status": "MANUAL_VERIFY",
            "error": "ledger unavailable",
            "items": [],
        },
    )

    assert packet["validation"]["research_complete"] is False
    assert any(
        "Beat/news ledger" in row
        for row in packet["validation"]["manual_verify"]
    )


def test_ready_beat_news_is_rendered_with_source_attribution(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)

    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
        beat_report={
            "required": True,
            "status": "READY",
            "source_revision": "abc123",
            "source_repository": "jarradmorelock/Ironbound-Forum-Feed-Poster",
            "source_branch": "news-data",
            "reporting_window": {
                "start": "2026-09-15T00:00:00-04:00",
                "end": "2026-09-22T23:59:59-04:00",
            },
            "relevant_event_count": 1,
            "items": [
                {
                    "published_at": "2026-09-18T12:00:00+00:00",
                    "headline": "Player 1 earns lead role",
                    "source": "RotoWire",
                    "source_url": "https://example.com/story",
                    "feed_summary": "The coaching staff expects an expanded role.",
                    "tags": ["Depth Chart"],
                    "league_players": [
                        {
                            "player": "Player 1",
                            "fantasy_team": "Team 1",
                        }
                    ],
                    "editorial_lanes": {
                        "since_we_last_printed": True,
                        "usage_context": True,
                    },
                }
            ],
        },
    )

    assert packet["validation"]["research_complete"] is True
    assert any(
        game.get("beat_context")
        for game in packet["game_coverage"]["games"]
        if any(
            str(team.get("team") or "") == "Team 1"
            for team in game.get("teams") or []
        )
    )
    text = render_flagship_research_packet(packet)
    assert "## REUSABLE BEAT CONTEXT" in text
    assert "Player 1 earns lead role" in text
    assert "RotoWire" in text
    assert "https://example.com/story" in text
    assert "usage context" in text


def test_rookie_watch_keeps_current_team_and_adds_ironbound_draft_context(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
    )

    rookies = packet["weekly_honors"]["rookie_watch_top_five"]
    first = next(row for row in rookies if row["player_id"] == "p1")
    second = next(row for row in rookies if row["player_id"] == "p2")

    assert first["team"] == "Team 1"
    assert first["ironbound_draft"] == "1.03 — drafted by Team 2"
    assert second["team"] == "Team 2"
    assert second["ironbound_draft"] == "1.04"

    text = render_flagship_research_packet(packet)
    assert "| Current Team | Ironbound Draft |" in text
    assert "1.03 — drafted by Team 2" in text


def test_roster_keyed_tuesday_handoff_populates_power_board(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    external = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        official_power_rankings=tuple(
            OfficialPowerRanking(
                franchise_key=None,
                rank=rank,
                roster_id=rank,
                team=f"Team {rank}",
                previous_rank=rank + 1,
                movement=1,
            )
            for rank in range(1, 17)
        ),
        playoff_odds=tuple(
            {"roster_id": rank, "team": f"Team {rank}", "playoff": 80 - rank}
            for rank in range(1, 17)
        ),
        usage=({"roster_id": 1, "value": 0.61},),
        war=({"roster_id": 1, "value": 2.4},),
        cwar=({"roster_id": 1, "value": 1.8},),
    )
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        external,
        history_root=tmp_path,
    )

    first = next(row for row in packet["power_board"]["writeup_inputs"] if row["roster_id"] == 1)
    assert first["official_rank"] == 1
    assert first["previous_rank"] == 2
    assert first["rank_movement"] == 1
    assert first["playoff_odds"]["playoff"] == 79
    assert first["war"]["value"] == 2.4


def test_v07_contract_exposes_shared_flagship_spine_and_authoritative_forward_models(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    rankings = tuple(
        OfficialPowerRanking(
            franchise_key=None,
            rank=rank,
            roster_id=rank,
            team=f"Team {rank}",
            previous_rank=rank,
            movement=0,
            score=80 - rank,
            components={
                "market_points": 20.0,
                "ros_starters_points": 30.0,
                "season_results_points": 10.0,
            },
        )
        for rank in range(1, 17)
    )
    external = ExternalEditorialInputs(
        publication_key="ironbound_weekly",
        schema_version=3,
        official_power_rankings=rankings,
        playoff_odds=tuple(
            {"roster_id": rank, "team": f"Team {rank}", "playoff": 80 - rank}
            for rank in range(1, 17)
        ),
        remaining_schedule_strength=tuple(
            {
                "roster_id": rank,
                "team": f"Team {rank}",
                "average_opponent_index": 50 + rank / 10,
                "difficulty_rank": rank,
                "grade": "C",
            }
            for rank in range(1, 17)
        ),
        weekly_matchup_forecast=tuple(
            {
                "week": 5,
                "matchup_id": matchup_id,
                "roster_one": matchup_id * 2 - 1,
                "team_one": f"Team {matchup_id * 2 - 1}",
                "roster_two": matchup_id * 2,
                "team_two": f"Team {matchup_id * 2}",
                "spread": 3.5,
                "over_under": 245.5,
                "simulations": 10000,
            }
            for matchup_id in range(1, 9)
        ),
        source_metadata={"ranking_week": 5, "results_through_week": 4},
    )

    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        external,
        history_root=tmp_path,
        roster_market={"status": "READY", "lineup_churn": [], "transactions": {}},
    )

    assert packet["contract_version"] == "ironbound-production-v0.7"
    assert len(packet["editorial_spine"]) == 25
    assert [row["module"] for row in packet["editorial_spine"]] == [
        "COVER", "CONTENTS", "LEAD_ART_OPENER", "LEAD_FEATURE",
        "GAME_REPORTS", "GAME_REPORTS", "GAME_REPORTS", "SECONDARY_FEATURE",
        "USAGE_DESK", "ROSTER_HEALTH", "MARKET_DESK", "MANAGER_HONORS",
        "PLAYER_HONORS", "ROOKIE_WATCH", "PLAYOFF_FORECAST", "POWER_RANKINGS",
        "POWER_BOARD", "POWER_BOARD", "POWER_BOARD", "POWER_BOARD",
        "PRESSURE_POINTS", "FULL_SLATE", "DIVISION_ROAD_AHEAD", "WEEK_AHEAD", "SOURCES",
    ]
    assert packet["power_board"]["writeup_inputs"][0]["ranking_components"]["market_points"] == 20.0
    assert packet["remaining_schedule_strength"]["rows"][0]["difficulty_rank"] == 1
    assert packet["weekly_matchup_forecast"]["rows"][0]["over_under"] == 245.5
    assert packet["editorial_style_guidance"]["stats_support_thesis"] is True
    assert packet["validation"]["research_complete"] is True


def test_flagship_brands_share_exact_page_functions_and_content_allocations():
    from editorial_desk.flagship_research import flagship_editorial_spine
    iron = flagship_editorial_spine('ironbound_weekly', 3)
    unbound = flagship_editorial_spine('unbound_weekly', 3)
    assert [r['module'] for r in iron] == [r['module'] for r in unbound]
    assert [r['page'] for r in iron] == list(range(1, 26))
    assert [r['game_report_numbers'] for r in iron[4:7]] == [[1, 2], [3, 4], [5, 6]]
    assert [r['ranks'] for r in iron[16:20]] == [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]
    assert iron[9]['display_name'] != unbound[9]['display_name']
    assert [row["display_name"] for row in iron[11:14]] == [
        "MANAGER HONORS & CUMULATIVE TEAM STATS",
        "PLAYER HONORS & SEASON LEADERS",
        "ROOKIE WATCH",
    ]
    assert iron[23]["display_name"] == "WEEK 4 PREVIEW"


def test_missing_page_fails_structural_contract_validation(tmp_path):
    from editorial_desk.flagship_research import validate_flagship_research_packet
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(snapshot, dossier, {}, _external(), history_root=tmp_path)
    packet['editorial_spine'].pop()
    assert validate_flagship_research_packet(packet)['research_complete'] is False


def test_honors_research_reports_projection_gaps_and_enriches_overall(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(snapshot,dossier,{},_external(),history_root=tmp_path)
    honors=packet['weekly_honors']
    assert honors['overall_player_of_the_week']['nfl_stat_line']
    assert honors['high_score']['points']==116
    assert honors['low_score']['points']==101
    assert honors['most_efficient_manager']
    assert honors['selected_rotating_award'] is None
    assert honors['award_availability']['IRON_BALLS']['status']=='UNAVAILABLE'
    assert packet['validation']['award_warnings']
    rendered=render_flagship_research_packet(packet)
    assert 'Missing verified same-season/week frozen pregame capture' in rendered
    assert 'Overall Player of the Week' in rendered
    assert 'Manager of the Week' in rendered
