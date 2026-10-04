from editorial_desk.weekly_features import _lineup_efficiency


def test_editorial_max_points_excludes_taxi_players():
    snapshot = {
        "league": {"roster_positions": ["QB", "RB", "WR", "FLEX", "BN"]},
        "users": [
            {
                "user_id": "u1",
                "display_name": "Owner One",
                "metadata": {"team_name": "One"},
            }
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["qb", "rb", "wr", "taxi"],
                "taxi": ["taxi"],
            }
        ],
        "players": {
            "qb": {"full_name": "Quarterback", "position": "QB", "fantasy_positions": ["QB"]},
            "rb": {"full_name": "Runner", "position": "RB", "fantasy_positions": ["RB"]},
            "wr": {"full_name": "Receiver", "position": "WR", "fantasy_positions": ["WR"]},
            "taxi": {"full_name": "Taxi Rookie", "position": "RB", "fantasy_positions": ["RB"]},
        },
        "matchups": [
            {
                "roster_id": 1,
                "starters": ["qb", "rb", "wr"],
                "players": ["qb", "rb", "wr", "taxi"],
                "players_points": {"qb": 20.0, "rb": 10.0, "wr": 10.0, "taxi": 40.0},
            }
        ],
    }

    row = _lineup_efficiency(snapshot)[0]

    assert row["actual_points"] == 40.0
    assert row["optimal_points"] == 40.0
    assert row["points_left_on_bench"] == 0.0
    assert row["efficiency"] == 1.0
