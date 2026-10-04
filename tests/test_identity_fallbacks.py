from editorial_desk.nfl_enrichment import build_nfl_game_intelligence
from editorial_desk.weekly_features import _free_agent_of_week, _rookie_of_week


def test_free_agent_feature_excludes_rostered_player_when_sleeper_gsis_is_missing():
    snapshot = {
        "league": {"scoring_settings": {"pass_yd": 0.04, "pass_td": 6}},
        "players": {
            "11560": {
                "full_name": "Caleb Williams",
                "position": "QB",
                "team": "CHI",
                "gsis_id": None,
                "years_exp": 2,
            }
        },
        "rosters": [{"roster_id": 1, "players": ["11560"]}],
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {
                        "player_id": "00-0039918",
                        "player_display_name": "Caleb Williams",
                        "position": "QB",
                        "team": "CHI",
                        "passing_yards": 300,
                        "passing_tds": 4,
                    },
                    {
                        "player_id": "fa-1",
                        "player_display_name": "Actual Free Agent",
                        "position": "QB",
                        "team": "NYJ",
                        "passing_yards": 250,
                        "passing_tds": 3,
                    },
                ],
            }
        },
    }

    winner = _free_agent_of_week(snapshot)

    assert winner["player"] == "Actual Free Agent"


def test_rookie_feature_does_not_treat_missing_years_exp_as_zero():
    snapshot = {
        "players": {
            "SEA": {"first_name": "Seattle", "last_name": "Seahawks", "position": "DEF", "years_exp": None},
            "rookie": {"full_name": "Real Rookie", "position": "WR", "years_exp": 0},
        },
        "users": [{"user_id": "u1", "display_name": "Owner", "metadata": {"team_name": "Team"}}],
        "rosters": [{"roster_id": 1, "owner_id": "u1", "players": ["SEA", "rookie"]}],
        "matchups": [
            {
                "roster_id": 1,
                "starters": ["SEA", "rookie"],
                "players": ["SEA", "rookie"],
                "players_points": {"SEA": 22.0, "rookie": 18.0},
            }
        ],
    }

    winner = _rookie_of_week(snapshot)

    assert winner["player"] == "Real Rookie"


def test_flagship_identity_fallback_marks_rostered_players_without_gsis():
    snapshot = {
        "editorial": {"tier": "flagship"},
        "league": {
            "scoring_settings": {"pass_yd": 0.04, "pass_td": 6, "pass_cmp": 0.1}
        },
        "players": {
            "12545": {
                "full_name": "Tyler Shough",
                "position": "QB",
                "team": "NO",
                "gsis_id": None,
            }
        },
        "rosters": [{"roster_id": 1, "players": ["12545"]}],
        "nfl_context": {
            "schedule": {
                "status": "available",
                "records": [{"home_team": "NO", "home_score": 31, "away_team": "ATL", "away_score": 28}],
            },
            "player_stats": {
                "status": "available",
                "records": [
                    {
                        "player_id": "00-0040743",
                        "player_display_name": "Tyler Shough",
                        "position": "QB",
                        "team": "NO",
                    }
                ],
            },
            "snap_counts": {"status": "available", "records": []},
            "play_by_play": {
                "status": "available",
                "records": [
                    {
                        "quarter": 1,
                        "posteam": "NO",
                        "pass_attempt": True,
                        "complete_pass": True,
                        "pass_touchdown": True,
                        "passer_player_id": "00-0040743",
                        "receiver_player_id": "r1",
                        "yards_gained": 100,
                        "first_down_pass": True,
                        "score_differential": 0,
                    },
                    {
                        "quarter": 4,
                        "posteam": "NO",
                        "pass_attempt": True,
                        "complete_pass": True,
                        "pass_touchdown": True,
                        "passer_player_id": "00-0040743",
                        "receiver_player_id": "r2",
                        "yards_gained": 100,
                        "first_down_pass": True,
                        "score_differential": -14,
                    },
                    {
                        "quarter": 4,
                        "posteam": "NO",
                        "pass_attempt": True,
                        "complete_pass": True,
                        "pass_touchdown": True,
                        "passer_player_id": "00-0040743",
                        "receiver_player_id": "r3",
                        "yards_gained": 100,
                        "first_down_pass": True,
                        "score_differential": -7,
                    },
                ],
            },
        },
    }

    intelligence = build_nfl_game_intelligence(snapshot)

    shough = intelligence["players"]["00-0040743"]
    assert shough["rostered"] is True
    assert any(
        signal["type"] == "LATE_SURGE" and signal.get("player_id") == "00-0040743"
        for signal in intelligence["story_signals"]
    )


def test_efficiency_spike_is_not_emitted_for_quarterbacks():
    snapshot = {
        "editorial": {"tier": "flagship"},
        "league": {"scoring_settings": {"pass_yd": 0.04, "pass_td": 6, "rush_yd": 0.1}},
        "players": {
            "qb": {"full_name": "Quarterback", "position": "QB", "team": "DAL", "gsis_id": "qb-gsis"}
        },
        "rosters": [{"roster_id": 1, "players": ["qb"]}],
        "nfl_context": {
            "schedule": {"status": "available", "records": []},
            "player_stats": {
                "status": "available",
                "records": [{"player_id": "qb-gsis", "player_display_name": "Quarterback", "position": "QB", "team": "DAL"}],
            },
            "snap_counts": {"status": "available", "records": []},
            "play_by_play": {
                "status": "available",
                "records": [
                    {
                        "quarter": 1,
                        "posteam": "DAL",
                        "pass_attempt": True,
                        "complete_pass": True,
                        "pass_touchdown": True,
                        "passer_player_id": "qb-gsis",
                        "receiver_player_id": "r1",
                        "yards_gained": 400,
                        "score_differential": 0,
                    },
                    {
                        "quarter": 2,
                        "posteam": "DAL",
                        "rush_attempt": True,
                        "rusher_player_id": "qb-gsis",
                        "yards_gained": 1,
                        "score_differential": 0,
                    },
                ],
            },
        },
    }

    intelligence = build_nfl_game_intelligence(snapshot)

    assert not any(
        signal["type"] == "EFFICIENCY_SPIKE" and signal.get("player_id") == "qb-gsis"
        for signal in intelligence["story_signals"]
    )
