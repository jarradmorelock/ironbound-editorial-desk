import pytest

from editorial_desk.ranking_story_context import build_ranking_story_context


def test_rankings_generate_verified_editorial_leads_with_odds():
    rankings = [
        {"roster_id": 1, "team": "Top", "rank": 1, "previous_rank": 3, "movement": 2,
         "score": 80, "components": {"market_points": 9}},
        {"roster_id": 2, "team": "Next", "rank": 2, "previous_rank": 1, "movement": -1,
         "score": 75, "components": {"market_points": 8}},
    ]
    standings = [
        {"roster_id": 1, "team": "Top", "rank": 5, "wins": 3, "losses": 1, "ties": 0, "points_for": 500},
        {"roster_id": 2, "team": "Next", "rank": 1, "wins": 4, "losses": 0, "ties": 0, "points_for": 600},
    ]
    odds = [{"roster_id": 1, "playoff": 65}]
    value = build_ranking_story_context(rankings, standings, odds)
    assert value["status"] == "ready"
    assert value["rows"][0]["rank_vs_standings"] == 4
    assert any(row["type"] == "power_risers" and row["team"] == "Top" for row in value["angles"])
    assert any(row["type"] == "standings_vs_power_disagreement" for row in value["angles"])
    assert value["rows"][0]["playoff_odds"] == odds[0]


def test_missing_previous_rank_does_not_manufacture_movement():
    value = build_ranking_story_context([{"roster_id": 1, "team": "A", "rank": 1,
                                          "previous_rank": None, "movement": 0}], [], [])
    assert value["rows"][0]["power_rank_movement"] is None
    assert not value["angles"]


def test_inconsistent_movement_is_rejected():
    with pytest.raises(ValueError, match="movement mismatch"):
        build_ranking_story_context([{"roster_id": 1, "team": "A", "rank": 1,
                                      "previous_rank": 3, "movement": -1}], [], [])


def test_empty_handoff_has_unavailable_status():
    assert build_ranking_story_context([], [], [])["status"] == "unavailable"
