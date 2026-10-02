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
