import json
from pathlib import Path

from editorial_desk.external_inputs import load_external_inputs
from editorial_desk.feature_producers import game_window_context
from editorial_desk.flagship_research import (
    _attach_rookie_draft_context,
    _season_team_score_top_three,
)
from editorial_desk.newspaper_research import render_newspaper_research_packet
from editorial_desk.nfl_enrichment import _build_flagship_stat_book


def test_external_rankings_accept_roster_key_and_team(tmp_path):
    path = tmp_path / "handoff.json"
    path.write_text(
        json.dumps(
            {
                "publication_key": "ironbound_weekly",
                "official_power_rankings": [
                    {
                        "roster_id": 7,
                        "team": "San Carlos FC",
                        "rank": 1,
                        "previous_rank": 3,
                        "movement": 2,
                        "score": 91.2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = load_external_inputs(path, "ironbound_weekly")
    row = result.ranking_for_roster(7, team="San Carlos FC")
    assert row is not None
    assert row.rank == 1
    assert row.previous_rank == 3
    assert row.movement == 2
    assert row.score == 91.2


def test_season_score_board_merges_chronicle_history_and_current_week():
    class Chronicle:
        def season_matchup_finals(self, league_key, season):
            return [
                {
                    "season": season,
                    "week": 1,
                    "matchup_id": 1,
                    "roster_id": 1,
                    "points": 167.15,
                },
                {
                    "season": season,
                    "week": 1,
                    "matchup_id": 1,
                    "roster_id": 2,
                    "points": 90.0,
                },
            ]

    snapshot = {
        "week": 2,
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "Week One King"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Week Two Team"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1"},
            {"roster_id": 2, "owner_id": "u2"},
        ],
        "matchups": [
            {"roster_id": 1, "points": 100.0},
            {"roster_id": 2, "points": 147.08},
        ],
    }
    rows = _season_team_score_top_three(
        [],
        snapshot=snapshot,
        league_key="ironbound_sixteen",
        season="2026",
        chronicle=Chronicle(),
    )
    assert rows[0]["score"] == 167.15
    assert rows[0]["week"] == 1
    assert any(row["score"] == 147.08 and row["week"] == 2 for row in rows)


def test_flagship_stat_book_enriches_bench_player_without_polluting_starter_records():
    snapshot = {
        "users": [{"user_id": "u1", "display_name": "Owner", "metadata": {"team_name": "Team One"}}],
        "rosters": [{"roster_id": 1, "owner_id": "u1", "players": ["starter", "bench"]}],
        "players": {
            "starter": {"full_name": "Starter QB", "position": "QB", "team": "DET", "gsis_id": "g1"},
            "bench": {"full_name": "Bench QB", "position": "QB", "team": "DET", "gsis_id": "g2"},
        },
        "matchups": [{"roster_id": 1, "starters": ["starter"]}],
    }
    stats = {
        "status": "available",
        "records": [
            {"player_id": "g1", "player_display_name": "Starter QB", "team": "DET", "position": "QB", "attempts": 30, "completions": 20, "passing_yards": 250, "passing_tds": 2},
            {"player_id": "g2", "player_display_name": "Bench QB", "team": "DET", "position": "QB", "attempts": 35, "completions": 28, "passing_yards": 325, "passing_tds": 4},
        ],
    }
    book = _build_flagship_stat_book(snapshot, stats, {})
    assert [row["sleeper_player_id"] for row in book["records"]] == ["starter"]
    assert {row["sleeper_player_id"] for row in book["rostered_records"]} == {"starter", "bench"}
    bench = next(row for row in book["rostered_records"] if row["sleeper_player_id"] == "bench")
    assert "325" in bench["nfl_stat_line"]
    assert "4 TD" in bench["nfl_stat_line"]


def test_rookie_context_keeps_current_team_and_adds_round_pick_and_original_team():
    snapshot = {
        "league": {"season": "2026"},
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "Drafting Team"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Current Team"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1"},
            {"roster_id": 2, "owner_id": "u2"},
        ],
        "flagship_sleeper": {
            "drafts": {
                "status": "available",
                "records": [
                    {
                        "draft": {"season": "2026"},
                        "picks": [
                            {
                                "player_id": "rookie",
                                "round": 2,
                                "draft_slot": 5,
                                "pick_no": 21,
                                "roster_id": 1,
                            }
                        ],
                    }
                ],
            }
        },
    }
    rows = _attach_rookie_draft_context(
        [{"player_id": "rookie", "player": "Rookie", "team": "Current Team"}],
        snapshot,
    )
    assert rows[0]["team"] == "Current Team"
    assert rows[0]["ironbound_draft"] == "2.05 — drafted by Drafting Team"


def test_newspaper_game_window_falls_back_to_monday_timing():
    dossier = {
        "game_timing": {
            "monday": {
                "matchups": [
                    {
                        "matchup_id": 1,
                        "completed": True,
                        "day_was_active": True,
                        "final_winner": "Winner",
                        "final_loser": "Loser",
                        "winner_score_before_day": 95.0,
                        "loser_score_before_day": 105.0,
                        "lead_changed_on_day": True,
                        "tie_broken_on_day": False,
                        "margin_supplied_by_day": True,
                        "final_margin": 5.0,
                        "teams": [
                            {
                                "team": "Winner",
                                "points": 120.0,
                                "day_points": 25.0,
                                "players": [
                                    {
                                        "player_id": "p1",
                                        "player": "Monday Hero",
                                        "fantasy_points": 25.0,
                                        "nfl_stat_line": "8 catches, 120 rec yds, 2 rec TD",
                                    }
                                ],
                            },
                            {
                                "team": "Loser",
                                "points": 115.0,
                                "day_points": 10.0,
                                "players": [],
                            },
                        ],
                    }
                ]
            }
        }
    }
    result = game_window_context({"nfl_context": {}}, dossier)
    assert result.status == "ready"
    assert result.data[0]["window"] == "Monday"
    assert result.data[0]["swung_result"] is True
    assert result.data[0]["remaining_players"][0]["player"] == "Monday Hero"


def test_newspaper_renderer_never_emits_json_only_placeholder():
    packet = {
        "publication_key": "ballad_crier",
        "publication": "The Ballad Crier",
        "week": 2,
        "contract_label": "test",
        "editorial_notes": [],
        "source_status": {},
        "validation": {
            "contract_valid": True,
            "research_complete": True,
            "manual_verify": [],
        },
        "sections": [
            {
                "feature": "mystery_structured_section",
                "display_name": "Mystery",
                "status": "ready",
                "data": [{"team": "Alpha", "value": 42}],
                "reason": None,
            }
        ],
    }
    text = render_newspaper_research_packet(packet)
    assert "Structured evidence is present" not in text
    assert "team=Alpha" in text
    assert "value=42" in text
