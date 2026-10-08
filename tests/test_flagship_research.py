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
    assert packet["validation"]["research_complete"] is False
    assert any("division" in row.casefold() for row in packet["validation"]["manual_verify"])
    assert len(packet["game_coverage"]["games"]) == 8
    assert all(game["division_status"] == "UNAVAILABLE" for game in packet["game_coverage"]["games"])
    assert packet["division_outlook"]["status"] == "PARTIAL"
    assert packet["game_coverage"]["feature_slots"] == 2
    assert packet["game_coverage"]["remaining_game_writeups"] == 6
    assert len(packet["weekly_honors"]["rookie_watch_top_five"]) == 5
    assert len(packet["weekly_honors"]["season_team_score_top_three"]) == 3
    assert len(packet["weekly_honors"]["season_efficiency_top_three"]) == 3
    assert packet["weekly_honors"]["player_season_top_three"]["status"] == "UNAVAILABLE"
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

    assert "## DIVISION OF DEATH / ROAD AHEAD" in text
    assert "## Player Season Top 3" in text
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
    assert any("division" in row.casefold() for row in packet["validation"]["manual_verify"])
    assert any("Player Season Top 3" in row for row in packet["validation"]["manual_verify"])
    waiting = " ".join(packet["validation"]["awaiting_tuesday_input"])
    assert "Power Rankings" in waiting
    assert "Playoff Odds" in waiting
    assert "WAR" not in waiting
    assert "cWAR" not in waiting
    assert "usage" not in waiting.lower()
    assert "Division of Death" in waiting


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

    assert packet["validation"]["research_complete"] is False
    assert any("Division of Death" in row for row in packet["validation"]["awaiting_tuesday_input"])
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

    assert packet["validation"]["research_complete"] is False
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


def test_full_packet_validation_names_division_history_and_tuesday_gaps(tmp_path):
    from editorial_desk.flagship_research import validate_flagship_research_packet

    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
    )

    validation = packet["validation"]
    check_map = {row["name"]: row["passed"] for row in validation["checks"]}
    assert check_map["game_division_evidence"] is True
    assert check_map["player_season_history"] is False
    assert check_map["rookie_season_history"] is False
    assert any("division" in message.casefold() for message in validation["manual_verify"])
    assert any("Player Season Top 3" in message for message in validation["manual_verify"])
    assert any("Division of Death" in message for message in validation["awaiting_tuesday_input"])

    rendered = render_flagship_research_packet(packet)
    assert "Divisional matchup: unavailable" in rendered
    assert "Rookie Disappointment — Editorial Candidates" in rendered
    assert "Free Agent of the Week" in rendered
    assert "Division of Death" in rendered
    assert "Awaiting Tuesday Inputs" in rendered

    packet["game_coverage"]["games"][0].pop("division_status")
    invalid = validate_flagship_research_packet(packet)
    assert invalid["contract_valid"] is False


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
    snapshot["league"]["metadata"] = {"division_1": "Forge", "division_2": "Anvil"}
    for roster in snapshot["rosters"]:
        roster["settings"]["division"] = 1 if int(roster["roster_id"]) % 2 else 2
    dossier["divisions"] = [
        {"division_id": "1", "division_name": "Forge"},
        {"division_id": "2", "division_name": "Anvil"},
    ]

    class Chronicle:
        def season_player_fantasy_finals(self, league_key, season):
            return [
                {
                    "week": week,
                    "roster_id": roster["roster_id"],
                    "player_id": roster["players"][0],
                    "position": snapshot["players"][roster["players"][0]]["position"],
                    "points": 10 + roster["roster_id"],
                }
                for week in range(1, 4)
                for roster in snapshot["rosters"]
            ]

        def season_efficiency(self, *args):
            return []

        def season_matchup_finals(self, *args):
            return []

        def identity_for_roster(self, *args):
            return None

        def league_events(self, *args):
            return []
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
        chronicle=Chronicle(),
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
    assert packet["weekly_honors"]["player_season_top_three"]["status"] == "READY"


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
    assert validate_flagship_research_packet(packet)['contract_valid'] is False


def test_incorrect_game_report_allocation_fails_structural_contract_validation(tmp_path):
    from editorial_desk.flagship_research import validate_flagship_research_packet

    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(
        snapshot,
        dossier,
        {"status": "available", "candidates": []},
        _external(),
        history_root=tmp_path,
    )
    packet["editorial_spine"][4]["game_report_numbers"] = [1]

    validation = validate_flagship_research_packet(packet)

    assert validation["contract_valid"] is False
    allocation = next(row for row in validation["checks"] if row["name"] == "game_report_allocation")
    assert allocation["passed"] is False


def test_game_research_marks_division_only_from_verified_roster_membership():
    from editorial_desk.flagship_research import _game_research

    snapshot, dossier = _fixture()
    snapshot["league"]["metadata"] = {
        "division_1": "Forge",
        "division_2": "Anvil",
    }
    for roster in snapshot["rosters"]:
        roster["settings"]["division"] = 1
    snapshot["rosters"][1]["settings"]["division"] = 2

    games = _game_research(snapshot, dossier)

    assert games[0]["division_status"] == "VERIFIED_NON_DIVISIONAL"
    assert "division_name" not in games[0]
    assert games[1]["division_status"] == "VERIFIED_DIVISIONAL"
    assert games[1]["division_name"] == "Forge"

    del snapshot["rosters"][1]["settings"]["division"]
    missing = _game_research(snapshot, dossier)[0]
    assert missing["division_status"] == "UNAVAILABLE"
    assert "division_name" not in missing


def test_division_outlook_keeps_summary_and_schedule_status_separate():
    from editorial_desk.flagship_research import _division_outlook

    summary = [{"division_id": "1", "division_name": "Forge"}]
    schedule = {
        "status": "AWAITING_TUESDAY_INPUT",
        "authority": "Ironbound_power_ranks",
        "rows": [],
    }

    outlook = _division_outlook(summary, schedule)

    assert outlook["division_status"] == "READY"
    assert outlook["division_summaries"] == summary
    assert outlook["schedule_status"] == "AWAITING_TUESDAY_INPUT"
    assert outlook["remaining_schedule_strength"] == []

    ready = _division_outlook(
        summary,
        {
            "status": "READY",
            "rows": [
                {"team": "Forge", "difficulty_rank": 2},
                {"team": "Anvil", "difficulty_rank": 1},
                {"team": "Crown", "difficulty_rank": 3},
            ],
        },
    )
    assert ready["status"] == "READY"
    assert ready["hardest_remaining_schedule"]["team"] == "Anvil"
    assert ready["easiest_remaining_schedule"]["team"] == "Crown"


def test_season_player_boards_merge_current_week_and_report_missing_history():
    from editorial_desk.flagship_research import _season_player_boards

    snapshot = {
        "week": 2,
        "players": {
            "p1": {"full_name": "Alpha QB", "position": "QB", "years_exp": 0},
            "p2": {"full_name": "Beta RB", "position": "RB", "years_exp": 2},
            "p3": {"full_name": "Gamma QB", "position": "QB", "years_exp": 0},
            "p4": {"full_name": "Delta QB", "position": "QB", "years_exp": 2},
        },
        "users": [
            {"user_id": "u1", "metadata": {"team_name": "Forge"}},
            {"user_id": "u2", "metadata": {"team_name": "Anvil"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["p1", "p2"]},
            {"roster_id": 2, "owner_id": "u2", "players": ["p3", "p4"]},
        ],
        "matchups": [
            {"roster_id": 1, "players": ["p1", "p2"], "players_points": {"p1": 5, "p2": 8}},
            {"roster_id": 2, "players": ["p3", "p4"], "players_points": {"p3": 30, "p4": 6}},
        ],
    }
    prior = [
        {"week": 1, "roster_id": 1, "player_id": "p1", "position": "QB", "points": 10},
        {"week": 1, "roster_id": 1, "player_id": "p2", "position": "RB", "points": 20},
        {"week": 1, "roster_id": 2, "player_id": "p3", "position": "QB", "points": 15},
        {"week": 1, "roster_id": 2, "player_id": "p4", "position": "QB", "points": 20},
    ]

    boards = _season_player_boards(prior, snapshot)

    assert boards["player_season_top_three"]["status"] == "READY"
    assert boards["player_season_top_three"]["by_position"]["QB"] == [
        {"player_id": "p3", "player": "Gamma QB", "position": "QB", "points": 45.0, "fantasy_team": "Anvil"},
        {"player_id": "p4", "player": "Delta QB", "position": "QB", "points": 26.0, "fantasy_team": "Anvil"},
        {"player_id": "p1", "player": "Alpha QB", "position": "QB", "points": 15.0, "fantasy_team": "Forge"},
    ]
    assert boards["rookie_season_leaders"]["by_position"]["QB"] == {
        "player_id": "p3", "player": "Gamma QB", "position": "QB", "points": 45.0, "fantasy_team": "Anvil"
    }
    assert "RB" not in boards["rookie_season_leaders"]["by_position"]

    incomplete = _season_player_boards(
        [
            {"week": 1, "roster_id": 1, "player_id": "p1", "position": "QB", "points": 10},
            {"week": 1, "roster_id": 2, "player_id": "p3", "position": "QB", "points": 15},
            {"week": 1, "roster_id": 2, "player_id": "p4", "position": "QB", "points": 20},
        ],
        snapshot,
    )
    assert incomplete["player_season_top_three"]["status"] == "UNAVAILABLE"
    assert incomplete["player_season_top_three"]["by_position"] == {}
    assert "Beta RB" in incomplete["player_season_top_three"]["reason"]
    assert "Week 1" in incomplete["player_season_top_three"]["reason"]


def test_flagship_packet_uses_supplied_player_week_history(tmp_path, monkeypatch):
    import editorial_desk.flagship_research as research

    snapshot, dossier = _fixture()
    supplied = [{
        "week": 1, "roster_id": 1, "player_id": "historical-player",
        "position": "RB", "points": 12.5,
    }]
    observed = {}
    original = research._season_player_boards

    def capture(rows, current_snapshot):
        observed["rows"] = rows
        return original(rows, current_snapshot)

    monkeypatch.setattr(research, "_season_player_boards", capture)
    research.build_flagship_research_packet(
        snapshot, dossier, {}, _external(), history_root=tmp_path,
        player_week_history=supplied,
    )

    assert observed["rows"] == supplied


def test_honors_research_reports_projection_gaps_and_enriches_overall(tmp_path):
    snapshot, dossier = _fixture()
    _write_history(tmp_path, dossier)
    packet = build_flagship_research_packet(snapshot,dossier,{},_external(),history_root=tmp_path)
    honors=packet['weekly_honors']
    assert honors['overall_player_of_the_week']['nfl_stat_line']
    assert honors['high_score']['points']==116
    assert honors['low_score']['points']==101
    assert honors['most_efficient_manager']
    assert honors['most_efficient_manager']['roster_id'] != honors['manager_of_the_week']['roster_id']
    assert 'rookie_of_the_week' in honors
    assert 'top_rookie_starter' in honors
    assert 'rookie_disappointment_candidates' in honors
    assert 'free_agent_of_the_week' in honors
    assert 'bad_beat_candidates' in honors and 'escape_artist_candidates' in honors
    assert honors['selected_rotating_award'] is None
    assert honors['award_availability']['IRON_BALLS']['status']=='UNAVAILABLE'
    assert packet['validation']['award_warnings']
    rendered=render_flagship_research_packet(packet)
    assert 'Missing verified same-season/week frozen pregame capture' in rendered
    assert 'Overall Player of the Week' in rendered
    assert 'Manager of the Week' in rendered


def test_manager_bad_beat_and_escape_artist_are_record_aware_and_disjoint():
    from editorial_desk.flagship_research import _manager_weekly_awards

    history = [
        {
            "week": 1,
            "scoreboard": [
                {"matchup_id": 1, "teams": [{"roster_id": 1, "team": "A", "points": 110}, {"roster_id": 2, "team": "B", "points": 90}]},
                {"matchup_id": 2, "teams": [{"roster_id": 3, "team": "C", "points": 100}, {"roster_id": 4, "team": "D", "points": 95}]},
            ],
        }
    ]
    dossier = {
        "lineup_efficiency": [
            {"roster_id": 4, "efficiency": 0.80},
            {"roster_id": 3, "efficiency": 0.98},
            {"roster_id": 1, "efficiency": 1.0},
            {"roster_id": 2, "efficiency": 0.95},
        ],
        "scoreboard": [
            {"matchup_id": 11, "teams": [{"roster_id": 1, "team": "A", "points": 121.05}, {"roster_id": 2, "team": "B", "points": 121.06}]},
            {"matchup_id": 12, "teams": [{"roster_id": 3, "team": "C", "points": 105}, {"roster_id": 4, "team": "D", "points": 104.9}]},
        ],
    }

    awards = _manager_weekly_awards(
        dossier, history, current_week=2, manager_of_the_week={"roster_id": 1}
    )

    assert awards["most_efficient_manager"]["roster_id"] == 3
    assert awards["bad_beat"]["roster_id"] == 1
    assert awards["escape_artist"]["roster_id"] == 3
    assert awards["bad_beat"]["matchup_id"] != awards["escape_artist"]["matchup_id"]
    assert awards["bad_beat"]["entering_record"]["wins"] == 1


def test_rookie_of_week_can_be_bench_while_top_rookie_starter_is_separate():
    from editorial_desk.flagship_research import _rookie_weekly_awards

    snapshot = {
        "week": 2,
        "league": {"season": "2026", "roster_positions": ["QB", "RB", "BN"]},
        "users": [{"user_id": "u1", "metadata": {"team_name": "Forge"}}],
        "rosters": [{"roster_id": 1, "owner_id": "u1", "players": ["rookie-qb", "rookie-rb", "taxi-wr"], "taxi": ["taxi-wr"]}],
        "players": {
            "rookie-qb": {"full_name": "Rookie QB", "position": "QB", "years_exp": 0},
            "rookie-rb": {"full_name": "Rookie RB", "position": "RB", "years_exp": 0},
            "taxi-wr": {"full_name": "Taxi WR", "position": "WR", "years_exp": 0},
        },
        "draft_context": {
            "records": [
                {
                    "draft": {"season": "2026"},
                    "picks": [
                        {"player_id": "taxi-wr", "round": 1, "draft_slot": 1, "roster_id": 1},
                        {"player_id": "rookie-qb", "round": 2, "draft_slot": 1, "roster_id": 1},
                    ],
                }
            ]
        },
        "matchups": [{"roster_id": 1, "players": ["rookie-qb", "rookie-rb", "taxi-wr"], "starters": ["rookie-qb"], "players_points": {"rookie-qb": 20, "rookie-rb": 32, "taxi-wr": 40}}],
    }

    awards = _rookie_weekly_awards({}, snapshot, {})

    assert awards["rookie_of_the_week"]["player"] == "Taxi WR"
    assert awards["rookie_of_the_week"]["status"] == "TAXI"
    assert awards["top_rookie_starter"]["player"] == "Rookie QB"
    assert awards["top_rookie_starter"]["status"] == "STARTED"
    assert awards["rookie_of_the_week"]["ironbound_draft"] == "1.01"
    assert awards["top_rookie_starter"]["ironbound_draft"] == "2.01"
    assert awards["rookie_disappointment_status"]["status"] == "PARTIAL"


def test_started_positional_awards_remain_distinct_from_overall_winner():
    from editorial_desk.flagship_research import _distinct_started_position_leaders

    snapshot = {
        "users": [{"user_id": "u1", "metadata": {"team_name": "Forge"}}],
        "rosters": [{"roster_id": 1, "owner_id": "u1"}],
        "players": {
            "overall": {"full_name": "Overall QB", "position": "QB"},
            "next": {"full_name": "Next QB", "position": "QB"},
        },
        "matchups": [{"roster_id": 1, "players": ["overall", "next"], "starters": ["overall", "next"], "players_points": {"overall": 40, "next": 30}}],
    }

    leaders = _distinct_started_position_leaders(snapshot, {"player_id": "overall"})

    assert leaders["QB"]["player_id"] == "next"


def test_free_agent_display_is_explicitly_unrostered():
    from editorial_desk.flagship_research import _unrostered_free_agent

    result = _unrostered_free_agent(
        {"player_id": "p1", "player": "Free Agent", "points": 25}, {}
    )

    assert result["fantasy_team"] == "UNROSTERED"


def test_manager_history_uses_complete_collected_schedule_without_old_report_files():
    from editorial_desk.flagship_research import _manager_record_history, _manager_weekly_awards

    snapshot = {'week': 2, 'rosters': [{'roster_id': i} for i in range(1, 5)],
                'flagship_sleeper': {'schedule': {'weeks': {'1': [
                    {'roster_id': 1, 'matchup_id': 1, 'points': 90, 'custom_points': 110},
                    {'roster_id': 2, 'matchup_id': 1, 'points': 100},
                    {'roster_id': 3, 'matchup_id': 2, 'points': 120},
                    {'roster_id': 4, 'matchup_id': 2, 'points': 115},
                ]}}}}
    dossier = {'scoreboard': [
        {'matchup_id': 1, 'teams': [{'roster_id': 1, 'points': 130}, {'roster_id': 2, 'points': 131}]},
        {'matchup_id': 2, 'teams': [{'roster_id': 3, 'points': 100}, {'roster_id': 4, 'points': 99}]},
    ]}
    history = _manager_record_history(snapshot, [])
    awards = _manager_weekly_awards(dossier, history, current_week=2, manager_of_the_week=None)
    assert awards['bad_beat']['roster_id'] == 1
    assert awards['bad_beat']['entering_record'] == {'wins': 1, 'losses': 0, 'ties': 0}
    assert awards['escape_artist']['roster_id'] == 3
    # Saved report history remains authoritative where already supplied.
    assert _manager_record_history(snapshot, history) == history
    rows = snapshot['flagship_sleeper']['schedule']['weeks']['1']
    rows.append(dict(rows[0]))
    assert _manager_record_history(snapshot, []) == []
    rows.pop()
    rows.pop()
    assert _manager_record_history(snapshot, []) == []
