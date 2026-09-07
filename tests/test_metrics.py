from editorial_desk.metrics import build_weekly_dossier, optimal_lineup


PLAYERS = {
    "qb1": {"full_name": "Quarterback One", "fantasy_positions": ["QB"]},
    "qb2": {"full_name": "Quarterback Two", "fantasy_positions": ["QB"]},
    "rb1": {"full_name": "Runner One", "fantasy_positions": ["RB"]},
    "rb2": {"full_name": "Runner Two", "fantasy_positions": ["RB"]},
    "rb3": {"full_name": "Runner Three", "fantasy_positions": ["RB"]},
    "wr1": {"full_name": "Receiver One", "fantasy_positions": ["WR"]},
    "wr2": {"full_name": "Receiver Two", "fantasy_positions": ["WR"]},
    "wr3": {"full_name": "Receiver Three", "fantasy_positions": ["WR"]},
    "wr4": {"full_name": "Receiver Four", "fantasy_positions": ["WR"]},
}


def test_optimal_lineup_obeys_slot_eligibility():
    score, assignment = optimal_lineup(
        ["qb1", "qb2", "rb1", "rb2", "wr1"],
        {"qb1": 10, "qb2": 25, "rb1": 20, "rb2": 15, "wr1": 30},
        ["QB", "RB", "FLEX"],
        PLAYERS,
    )
    assert score == 75
    assert assignment[0] == "qb2"
    assert {assignment[1], assignment[2]} == {"rb1", "wr1"}


def snapshot():
    return {
        "collected_at": "2026-09-15T22:00:00+00:00",
        "week": 1,
        "editorial": {
            "league_key": "test",
            "configured_name": "Test League",
            "publication": "Test Paper",
            "tier": "newspaper",
        },
        "league": {
            "name": "Test League",
            "season": "2026",
            "roster_positions": ["QB", "RB", "WR", "FLEX", "BN"],
            "settings": {"league_average_match": 1, "divisions": 2},
            "metadata": {"division_1": "Forge", "division_2": "Anvil"},
        },
        "users": [
            {"user_id": "u1", "display_name": "Owner One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Owner Two", "metadata": {"team_name": "Two"}},
            {"user_id": "u3", "display_name": "Owner Three", "metadata": {"team_name": "Three"}},
            {"user_id": "u4", "display_name": "Owner Four", "metadata": {"team_name": "Four"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "settings": {"division": 1}},
            {"roster_id": 2, "owner_id": "u2", "settings": {"division": 1}},
            {"roster_id": 3, "owner_id": "u3", "settings": {"division": 2}},
            {"roster_id": 4, "owner_id": "u4", "settings": {"division": 2}},
        ],
        "players": PLAYERS,
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 101, "starters": ["qb1", "rb1", "wr1", "wr2"], "players": ["qb1", "rb1", "rb2", "wr1", "wr2"], "players_points": {"qb1": 20, "rb1": 20, "rb2": 35, "wr1": 31, "wr2": 30}},
            {"matchup_id": 1, "roster_id": 2, "points": 110, "starters": ["qb2", "rb2", "wr3", "wr4"], "players": ["qb2", "rb2", "rb3", "wr3", "wr4"], "players_points": {"qb2": 25, "rb2": 25, "rb3": 10, "wr3": 30, "wr4": 30}},
            {"matchup_id": 2, "roster_id": 3, "points": 70, "starters": ["qb1", "rb1", "wr1", "wr2"], "players": ["qb1", "rb1", "wr1", "wr2"], "players_points": {"qb1": 10, "rb1": 20, "wr1": 20, "wr2": 20}},
            {"matchup_id": 2, "roster_id": 4, "points": 65, "starters": ["qb2", "rb2", "wr3", "wr4"], "players": ["qb2", "rb2", "wr3", "wr4"], "players_points": {"qb2": 15, "rb2": 15, "wr3": 20, "wr4": 15}},
        ],
        "transactions": [
            {"transaction_id": "tx1", "status": "complete", "type": "waiver", "adds": {"wr3": 2}, "settings": {"waiver_bid": 7}}
        ],
        "traded_picks": [],
    }


def test_awards_and_lineup_metrics_are_derived_from_verified_scores():
    dossier = build_weekly_dossier(snapshot())
    assert dossier["awards"]["bad_beat"]["team"] == "One"
    assert dossier["awards"]["escape_artist"]["team"] == "Three"
    assert dossier["awards"]["bench_mvp"]["player"] == "Runner Two"
    assert dossier["awards"]["manager_of_the_week"]["team"] == "Two"
    assert dossier["awards"]["waiver_star_candidates"][0]["player"] == "Receiver Three"


def test_single_swap_that_changes_result_is_identified():
    dossier = build_weekly_dossier(snapshot())
    flip = dossier["awards"]["result_flipping_decisions"][0]
    assert flip["team"] == "One"
    assert flip["started_player"] == "Runner One"
    assert flip["bench_player"] == "Runner Two"
    assert flip["revised_team_score"] == 116


def test_median_and_named_division_context_are_preserved():
    dossier = build_weekly_dossier(snapshot())
    assert dossier["league_median"]["enabled"] is True
    assert dossier["league_median"]["points"] == 85.5
    assert dossier["awards"]["bad_beat"]["league_median"]["result"] == "win"
    assert [row["division_name"] for row in dossier["divisions"]] == [
        "Forge",
        "Anvil",
    ]
    assert dossier["divisions"][0]["weekly_scoring_rank"] == 1


def test_zero_point_preseason_matchups_do_not_create_false_awards_or_records():
    empty = snapshot()
    for matchup in empty["matchups"]:
        matchup["points"] = 0
        matchup["players_points"] = {
            player_id: 0 for player_id in matchup["players_points"]
        }
    dossier = build_weekly_dossier(empty)
    assert dossier["awards"]["mvp_card_result"] is None
    assert dossier["weekly_records"]["status"] == "awaiting_scores"
    assert dossier["weekly_records"]["highest_score"] is None
