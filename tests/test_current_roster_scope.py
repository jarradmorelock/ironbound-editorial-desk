from editorial_desk.nfl_enrichment import build_nfl_game_intelligence
from editorial_desk.weekly_features import _free_agent_of_week


def test_free_agent_exclusion_uses_current_roster_not_historical_player_directory():
    snapshot = {
        "league": {"scoring_settings": {"rush_yd": 0.1, "rush_td": 6}},
        "players": {
            "current": {"full_name": "Current Back", "gsis_id": "g-current"},
            # Kept in the trimmed directory because he appeared in prior league
            # history, but no longer belongs to any current roster.
            "former": {"full_name": "Former Back", "gsis_id": "g-former"},
        },
        "rosters": [{"roster_id": 1, "players": ["current"], "taxi": [], "reserve": []}],
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {"player_id": "g-current", "player_display_name": "Current Back", "position": "RB", "team": "TEN", "rushing_yards": 120, "rushing_tds": 1},
                    {"player_id": "g-former", "player_display_name": "Former Back", "position": "RB", "team": "NO", "rushing_yards": 150, "rushing_tds": 2},
                ],
            }
        },
    }

    result = _free_agent_of_week(snapshot)

    assert result["player"] == "Former Back"


def test_game_intelligence_relevant_teams_are_current_roster_teams_only():
    snapshot = {
        "editorial": {"tier": "flagship"},
        "league": {"scoring_settings": {}},
        "players": {
            "current": {"full_name": "Current Back", "position": "RB", "team": "TEN", "gsis_id": "g-current"},
            "former": {"full_name": "Former Back", "position": "RB", "team": "NO", "gsis_id": "g-former"},
        },
        "rosters": [{"roster_id": 1, "players": ["current"], "taxi": [], "reserve": []}],
        "nfl_context": {
            "player_stats": {"status": "available", "records": []},
            "schedule": {"status": "available", "records": []},
            "snap_counts": {
                "status": "available",
                "records": [
                    {"player": "Current Back", "position": "RB", "team": "TEN", "offense_snaps": 40, "offense_pct": 0.7},
                    {"player": "Former Back", "position": "RB", "team": "NO", "offense_snaps": 40, "offense_pct": 0.7},
                ],
            },
            "play_by_play": {"status": "available", "records": []},
        },
    }

    result = build_nfl_game_intelligence(snapshot)

    assert "g-current" in result["players"]
    assert "g-former" not in result["players"]
