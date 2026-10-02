from editorial_desk.canonical_evidence import build_canonical_league_evidence


def _snapshot():
    return {
        "week": 3,
        "league": {"season": "2026", "settings": {"divisions": 2}},
        "editorial": {"league_key": "test_league"},
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "settings": {"division": 1}},
            {"roster_id": 2, "owner_id": "u2", "settings": {"division": 2}},
        ],
        "players": {
            "p1": {"full_name": "Player One"},
            "p2": {"full_name": "Player Two"},
        },
        "matchups": [
            {
                "matchup_id": 1,
                "roster_id": 1,
                "points": 110.0,
                "starters": ["p1"],
                "players": ["p1"],
                "players_points": {"p1": 23.5},
            },
            {
                "matchup_id": 1,
                "roster_id": 2,
                "points": 90.0,
                "starters": ["p2"],
                "players": ["p2"],
                "players_points": {"p2": 10.0},
            },
        ],
        "publication_sleeper": {
            "schedule": {
                "status": "available",
                "weeks": {
                    "1": [
                        {"matchup_id": 1, "roster_id": 1, "points": 100.0, "players": ["p1"], "players_points": {"p1": 20.0}},
                        {"matchup_id": 1, "roster_id": 2, "points": 80.0, "players": ["p2"], "players_points": {"p2": 10.0}},
                    ],
                    "2": [
                        {"matchup_id": 1, "roster_id": 1, "points": 101.0, "players": ["p1"], "players_points": {"p1": 20.0}},
                        {"matchup_id": 1, "roster_id": 2, "points": 81.0, "players": ["p2"], "players_points": {"p2": 11.0}},
                    ],
                    "3": [],
                },
            }
        },
    }


def test_sleeper_schedule_history_builds_entering_records_and_player_totals():
    result = build_canonical_league_evidence(_snapshot(), None)

    assert result["coverage"]["weeks"] == [1, 2, 3]
    assert result["coverage"]["status"] == "READY"
    assert result["entering_records"]["3"]["1"] == {"wins": 2, "losses": 0, "ties": 0}
    assert result["player_season_totals"]["p1"]["points"] == 63.5
    assert result["player_season_totals"]["p1"]["through_week"] == 3


def test_missing_historical_roster_blocks_full_season_totals():
    snapshot = _snapshot()
    snapshot["publication_sleeper"]["schedule"]["weeks"]["2"] = [
        {"matchup_id": 1, "roster_id": 1, "points": 101.0, "players": ["p1"], "players_points": {"p1": 20.0}}
    ]

    result = build_canonical_league_evidence(snapshot, None)

    assert result["coverage"]["status"] == "PARTIAL"
    assert "week 2" in result["coverage"]["reason"].lower()
    assert result["player_season_totals_status"] == "UNAVAILABLE"


class _ChronicleConflict:
    def season_matchup_finals(self, league_key, season):
        return [
            {
                "season": season,
                "week": 1,
                "matchup_id": 1,
                "roster_id": 1,
                "points": 99.0,
            }
        ]

    def season_player_fantasy_finals(self, league_key, season):
        return []


def test_sleeper_chronicle_conflict_is_manual_verify():
    result = build_canonical_league_evidence(_snapshot(), _ChronicleConflict())

    assert result["conflicts"][0]["status"] == "MANUAL_VERIFY"
    assert result["coverage"]["status"] == "MANUAL_VERIFY"


def test_real_ironbound_week3_history_reconstructs_entering_records_and_season_totals():
    """Regression values extracted from the actual Week 3 Editorial Desk artifact."""
    names = {
        1: "The Buckaneers",
        2: "Pikeville Strip Miners",
        3: "At least I have chicken",
        4: "Granite Mountain Drakes",
        5: "Martian Targaryen",
        6: "The Frozen Tundraners",
        7: "San Carlos FC",
        8: "Madtown Coyotes",
        9: "Scenic City Beavers",
        10: "The #1 Loser",
        11: "Happy Hippies",
        12: "Blue Moose",
        13: "Mormonts of Bear Island",
        14: "The Cheek Seekers",
        15: "The Night Sky Hellhawks",
        16: "The Mad Hatters FC",
    }
    divisions = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3, 8: 4,
                 9: 1, 10: 2, 11: 3, 12: 4, 13: 1, 14: 2, 15: 4, 16: 3}
    score_rows = {
        1: [
            (1, 1, 86.61), (2, 5, 115.21), (3, 1, 109.60), (4, 6, 90.32),
            (5, 2, 130.31), (6, 6, 145.45), (7, 4, 167.15), (8, 8, 137.20),
            (9, 3, 88.85), (10, 7, 123.16), (11, 3, 132.66), (12, 7, 111.37),
            (13, 4, 76.26), (14, 8, 96.98), (15, 5, 133.01), (16, 2, 83.45),
        ],
        2: [
            (1, 7, 108.58), (2, 5, 103.40), (3, 4, 124.91), (4, 2, 90.87),
            (5, 8, 147.08), (6, 6, 90.95), (7, 3, 56.71), (8, 1, 118.38),
            (9, 8, 120.03), (10, 6, 106.47), (11, 4, 78.92), (12, 2, 108.01),
            (13, 7, 80.09), (14, 5, 56.95), (15, 1, 110.68), (16, 3, 77.68),
        ],
        3: [
            (1, 1, 124.94), (2, 4, 112.94), (3, 5, 99.64), (4, 8, 104.46),
            (5, 1, 112.14), (6, 3, 114.21), (7, 6, 72.38), (8, 5, 122.03),
            (9, 2, 125.51), (10, 4, 84.56), (11, 7, 86.84), (12, 6, 119.27),
            (13, 3, 85.24), (14, 2, 71.08), (15, 8, 102.73), (16, 7, 94.60),
        ],
    }
    gibbs = {1: 38.75, 2: 23.40, 3: 41.90}
    geno = {1: 10.80, 2: 20.03, 3: 36.59}

    def rows_for(week):
        rows = []
        for roster_id, matchup_id, points in score_rows[week]:
            player_points = {}
            players = []
            starters = []
            if roster_id == 8:
                players.append("9221")
                starters.append("9221")
                player_points["9221"] = gibbs[week]
            if roster_id == 14:
                players.append("1373")
                player_points["1373"] = geno[week]
            rows.append({
                "matchup_id": matchup_id,
                "roster_id": roster_id,
                "points": points,
                "players": players,
                "starters": starters,
                "players_points": player_points,
            })
        return rows

    snapshot = {
        "week": 3,
        "league": {"season": "2026"},
        "editorial": {"league_key": "ironbound_sixteen"},
        "users": [
            {"user_id": f"u{rid}", "display_name": team, "metadata": {"team_name": team}}
            for rid, team in names.items()
        ],
        "rosters": [
            {"roster_id": rid, "owner_id": f"u{rid}", "settings": {"division": divisions[rid]}}
            for rid in names
        ],
        "players": {
            "9221": {"full_name": "Jahmyr Gibbs"},
            "1373": {"full_name": "Geno Smith"},
        },
        "matchups": rows_for(3),
        "publication_sleeper": {
            "schedule": {
                "status": "available",
                "weeks": {"1": rows_for(1), "2": rows_for(2), "3": rows_for(3)},
            }
        },
    }

    result = build_canonical_league_evidence(snapshot, None)

    assert result["coverage"]["status"] == "READY"
    assert result["entering_records"]["3"]["5"] == {"wins": 2, "losses": 0, "ties": 0}
    assert result["entering_records"]["3"]["4"] == {"wins": 0, "losses": 2, "ties": 0}
    top_three = sorted(
        result["team_season_totals"].values(),
        key=lambda row: row["points"],
        reverse=True,
    )[:3]
    assert [(row["team"], row["points"]) for row in top_three] == [
        ("Martian Targaryen", 389.53),
        ("Madtown Coyotes", 377.61),
        ("The Frozen Tundraners", 350.61),
    ]
    assert result["player_season_totals"]["9221"]["points"] == 104.05
    assert result["player_season_totals"]["1373"]["points"] == 67.42
