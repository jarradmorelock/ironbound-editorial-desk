import importlib
import importlib.util


def _module():
    spec = importlib.util.find_spec("editorial_desk.canonical_evidence")
    assert spec is not None, "canonical_evidence module is required"
    return importlib.import_module("editorial_desk.canonical_evidence")


def _snapshot():
    week1 = [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": 100.0,
            "players": ["p1"],
            "starters": ["p1"],
            "players_points": {"p1": 10.0},
        },
        {
            "roster_id": 2,
            "matchup_id": 1,
            "points": 90.0,
            "players": ["p2"],
            "starters": ["p2"],
            "players_points": {"p2": 9.0},
        },
    ]
    week2 = [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": 110.0,
            "players": ["p1"],
            "starters": ["p1"],
            "players_points": {"p1": 20.0},
        },
        {
            "roster_id": 2,
            "matchup_id": 1,
            "points": 95.0,
            "players": ["p2"],
            "starters": ["p2"],
            "players_points": {"p2": 11.0},
        },
    ]
    week3 = [
        {
            "roster_id": 1,
            "matchup_id": 1,
            "points": 120.0,
            "players": ["p1"],
            "starters": ["p1"],
            "players_points": {"p1": 30.0},
        },
        {
            "roster_id": 2,
            "matchup_id": 1,
            "points": 100.0,
            "players": ["p2"],
            "starters": ["p2"],
            "players_points": {"p2": 20.0},
        },
    ]
    history = {
        "schedule": {
            "status": "available",
            "weeks": {"1": week1, "2": week2, "3": week3},
            "errors": {},
        },
        "transactions": {"status": "available", "weeks": {}, "errors": {}},
    }
    return {
        "week": 3,
        "league": {"season": "2026"},
        "editorial": {"league_key": "test", "publication_enabled": True},
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "Team One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Team Two"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "settings": {"division": 1}},
            {"roster_id": 2, "owner_id": "u2", "settings": {"division": 1}},
        ],
        "players": {
            "p1": {"full_name": "Player One", "position": "QB"},
            "p2": {"full_name": "Player Two", "position": "QB"},
        },
        "matchups": week3,
        "flagship_sleeper": history,
    }


def test_sleeper_schedule_history_builds_entering_records_and_player_totals():
    result = _module().build_canonical_league_evidence(_snapshot(), None)

    assert result["coverage"]["weeks"] == [1, 2, 3]
    assert result["coverage"]["status"] == "READY"
    assert result["entering_records"]["3"]["1"] == {
        "wins": 2,
        "losses": 0,
        "ties": 0,
    }
    assert result["player_season_totals"]["p1"]["points"] == 60.0
    assert result["player_season_totals"]["p1"]["through_week"] == 3
    assert result["team_season_totals"]["1"]["points"] == 330.0
    assert result["division_summary"]["1"]["points"] == 615.0


def test_missing_historical_roster_blocks_full_season_totals():
    snapshot = _snapshot()
    snapshot["flagship_sleeper"]["schedule"]["weeks"]["2"] = [
        snapshot["flagship_sleeper"]["schedule"]["weeks"]["2"][0]
    ]

    result = _module().build_canonical_league_evidence(snapshot, None)

    assert result["coverage"]["status"] == "PARTIAL"
    assert 2 in result["coverage"]["incomplete_weeks"]
    assert result["player_season_totals_status"] == "UNAVAILABLE"
    assert result["team_season_totals_status"] == "UNAVAILABLE"


def test_sleeper_chronicle_conflict_is_manual_verify():
    class Chronicle:
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

    result = _module().build_canonical_league_evidence(_snapshot(), Chronicle())

    assert result["coverage"]["status"] == "MANUAL_VERIFY"
    assert result["conflicts"]
    conflict = result["conflicts"][0]
    assert conflict["status"] == "MANUAL_VERIFY"
    assert conflict["kind"] == "MATCHUP_FINAL"
    assert conflict["sleeper_value"] == 100.0
    assert conflict["chronicle_value"] == 99.0
