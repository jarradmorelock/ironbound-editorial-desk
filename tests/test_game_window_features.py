from editorial_desk.feature_producers import game_window_context


def _snapshot():
    return {
        "league": {"roster_positions": ["QB", "WR", "BN"]},
        "users": [
            {"user_id": "u1", "display_name": "Alpha", "metadata": {"team_name": "Alpha"}},
            {"user_id": "u2", "display_name": "Beta", "metadata": {"team_name": "Beta"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["early", "monday"]},
            {"roster_id": 2, "owner_id": "u2", "players": ["opp", "bench"]},
        ],
        "players": {
            "early": {"full_name": "Early QB", "position": "QB", "fantasy_positions": ["QB"], "team": "BUF"},
            "monday": {"full_name": "Monday Hero", "position": "WR", "fantasy_positions": ["WR"], "team": "NYJ"},
            "opp": {"full_name": "Opponent QB", "position": "QB", "fantasy_positions": ["QB"], "team": "DAL"},
            "bench": {"full_name": "Bench WR", "position": "WR", "fantasy_positions": ["WR"], "team": "DAL"},
        },
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 105, "starters": ["early", "monday"], "players": ["early", "monday"], "players_points": {"early": 70, "monday": 35}},
            {"matchup_id": 1, "roster_id": 2, "points": 100, "starters": ["opp", "bench"], "players": ["opp", "bench"], "players_points": {"opp": 70, "bench": 30}},
        ],
        "nfl_context": {
            "game_windows": [
                {"name": "monday", "player_ids": ["monday"]}
            ]
        },
    }


def _dossier():
    return {
        "scoreboard": [
            {"winner": {"roster_id": 1, "team": "Alpha", "points": 105}, "loser": {"roster_id": 2, "team": "Beta", "points": 100}, "margin": 5}
        ]
    }


def test_final_minus_window_scoring_is_labeled_reconstructed():
    result = game_window_context(_snapshot(), _dossier())
    assert result.status == "ready"
    row = result.data[0]
    assert row["provenance"] == "reconstructed"
    assert row["pre_window_score"] == 70
    assert row["opponent_pre_window_score"] == 100
    assert row["window_points"] == 35
    assert row["final_score"] == 105
    assert row["final_margin"] == 5
    assert row["trailing_before_window"] is True
    assert row["remaining_players"][0]["player"] == "Monday Hero"


def test_observed_live_chronicle_snapshot_overrides_reconstructed_pre_window_score():
    events = [
        {
            "event_type": "MATCHUP_SCORE_SNAPSHOT",
            "provenance": "observed_live",
            "observed_at": "2026-09-14T23:55:00Z",
            "evidence": {
                "window": "monday",
                "scores": {"1": 72, "2": 100},
                "remaining_starters": {"1": ["monday"], "2": []},
            },
        }
    ]
    result = game_window_context(_snapshot(), _dossier(), events)
    assert result.status == "ready"
    row = result.data[0]
    assert row["provenance"] == "observed_live"
    assert row["observed_at"] == "2026-09-14T23:55:00Z"
    assert row["pre_window_score"] == 72
    assert row["opponent_pre_window_score"] == 100
    assert row["remaining_players"][0]["player"] == "Monday Hero"


def test_no_identifiable_final_window_is_legitimately_empty():
    snapshot = _snapshot()
    snapshot["nfl_context"] = {}
    result = game_window_context(snapshot, _dossier())
    assert result.status == "ready_no_items"
