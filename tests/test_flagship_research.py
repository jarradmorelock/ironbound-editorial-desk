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
    assert "WAR" in waiting
    assert "cWAR" in waiting
    assert "usage" in waiting.lower()
