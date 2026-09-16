from editorial_desk.metrics import build_weekly_dossier
from editorial_desk.review import render_editorial_review
from editorial_desk.weekly_features import apply_weekly_features


def _snapshot(*, projection_tiebreak: bool = False, transaction_tiebreak: bool = False):
    ranking_players = {}
    if projection_tiebreak:
        ranking_players = {
            "q3": {"pass_yd": 250},
            "q3b": {"pass_yd": 500},
        }

    transactions = []
    if transaction_tiebreak:
        transactions = [
            {
                "transaction_id": "tx1",
                "status": "complete",
                "type": "waiver",
                "adds": {"q3": 3},
                "drops": {},
                "settings": {"waiver_bid": 7},
            }
        ]

    return {
        "collected_at": "2026-09-15T22:00:00+00:00",
        "week": 1,
        "editorial": {
            "league_key": "test",
            "configured_name": "Test League",
            "publication": "Test Paper",
            "tier": "newspaper",
            "league_format": "redraft",
            "ranking_model": "redraft_projection_starters_record",
        },
        "league": {
            "name": "Test League",
            "season": "2026",
            "roster_positions": ["QB", "BN"],
            "settings": {},
            "metadata": {},
            "scoring_settings": {"pass_yd": 0.04},
        },
        "users": [
            {"user_id": "u1", "display_name": "Perfect Loser", "metadata": {"team_name": "Perfect Loser"}},
            {"user_id": "u2", "display_name": "High Score Winner", "metadata": {"team_name": "High Score Winner"}},
            {"user_id": "u3", "display_name": "Perfect Winner", "metadata": {"team_name": "Perfect Winner"}},
            {"user_id": "u4", "display_name": "Other Loser", "metadata": {"team_name": "Other Loser"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["q1"], "settings": {}},
            {"roster_id": 2, "owner_id": "u2", "players": ["q2", "q2b"], "settings": {}},
            {"roster_id": 3, "owner_id": "u3", "players": ["q3", "q3b"], "settings": {}},
            {"roster_id": 4, "owner_id": "u4", "players": ["q4", "q4b"], "settings": {}},
        ],
        "players": {
            "q1": {"full_name": "Q One", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q2": {"full_name": "Q Two", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q2b": {"full_name": "Q Two Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q3": {"full_name": "Q Three", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q3b": {"full_name": "Q Three Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q4": {"full_name": "Q Four", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
            "q4b": {"full_name": "Q Four Bench", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5},
        },
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 30, "starters": ["q1"], "players": ["q1"], "players_points": {"q1": 30}},
            {"matchup_id": 1, "roster_id": 2, "points": 35, "starters": ["q2"], "players": ["q2", "q2b"], "players_points": {"q2": 35, "q2b": 40}},
            {"matchup_id": 2, "roster_id": 3, "points": 28, "starters": ["q3"], "players": ["q3", "q3b"], "players_points": {"q3": 28, "q3b": 5}},
            {"matchup_id": 2, "roster_id": 4, "points": 20, "starters": ["q4"], "players": ["q4", "q4b"], "players_points": {"q4": 20, "q4b": 25}},
        ],
        "transactions": transactions,
        "traded_picks": [],
        "ranking_inputs": {
            "sleeper_projections": {"status": "available", "players": ranking_players},
            "dynasty_daddy": {"status": "unavailable", "players": {}},
            "redraft_daddy": {"status": "unavailable", "players": {}},
        },
        "nfl_context": {"player_stats": {"status": "unavailable", "records": []}},
    }


def test_weekly_lineup_efficiency_is_separate_top_three_and_can_include_loser():
    snapshot = _snapshot()
    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))

    top_three = dossier["weekly_features"]["lineup_efficiency_top_three"]

    assert [row["roster_id"] for row in top_three] == [1, 3, 2]
    assert top_three[0]["team"] == "Perfect Loser"
    assert len(top_three) == 3


def test_manager_of_week_balances_score_and_efficiency_among_winners():
    snapshot = _snapshot()
    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))

    manager = dossier["awards"]["manager_of_the_week"]

    assert manager["roster_id"] == 2
    assert manager["head_to_head_result"] == "win"
    assert manager["efficiency_rank_among_winners"] == 2
    assert manager["score_rank_among_winners"] == 1
    assert manager["manager_rank_sum"] == 3


def test_lower_projected_start_that_preserved_win_breaks_manager_tie():
    snapshot = _snapshot(projection_tiebreak=True)
    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))

    manager = dossier["awards"]["manager_of_the_week"]

    assert manager["roster_id"] == 3
    evidence = manager["management_tiebreak"]["evidence"]
    assert any(row["type"] == "projection_start_sit" for row in evidence)
    projection_call = next(row for row in evidence if row["type"] == "projection_start_sit")
    assert projection_call["started_player"] == "Q Three"
    assert projection_call["bench_player"] == "Q Three Bench"
    assert projection_call["started_projection"] < projection_call["bench_projection"]
    assert projection_call["point_swing"] > projection_call["victory_margin"]


def test_started_waiver_add_that_outscored_margin_breaks_manager_tie():
    snapshot = _snapshot(transaction_tiebreak=True)
    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))

    manager = dossier["awards"]["manager_of_the_week"]

    assert manager["roster_id"] == 3
    evidence = manager["management_tiebreak"]["evidence"]
    transaction_call = next(row for row in evidence if row["type"] == "transaction_start")
    assert transaction_call["player"] == "Q Three"
    assert transaction_call["transaction_type"] == "waiver"
    assert transaction_call["points"] > transaction_call["victory_margin"]


def test_review_renders_weekly_lineup_efficiency_top_three_as_separate_section():
    snapshot = _snapshot()
    dossier = apply_weekly_features(snapshot, build_weekly_dossier(snapshot))
    dossier["market_context"] = {}
    dossier["source_manifest"] = []

    text = render_editorial_review(dossier)

    assert "### Weekly Lineup Efficiency Top 3" in text
    assert "Perfect Loser" in text
    assert "Manager of the Week" in text
