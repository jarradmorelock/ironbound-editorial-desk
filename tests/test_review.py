from editorial_desk.review import render_editorial_review


def test_review_renders_magazine_features_and_flagship_game_intelligence():
    dossier = {
        "week": 1,
        "information_current_through": "2026-09-15T20:00:00Z",
        "league": {
            "publication": "Ironbound Weekly",
            "configured_name": "Ironbound Sixteen",
            "tier": "flagship",
        },
        "scoreboard": [],
        "lineup_efficiency": [],
        "rankings": {},
        "awards": {},
        "weekly_records": {},
        "weekly_features": {
            "divisional_mvp_nominees": [
                {
                    "division_name": "Hammer",
                    "player": "Started Star",
                    "team": "Team A",
                    "position": "RB",
                    "points": 35.4,
                    "status": "STARTED",
                    "gold_foil": True,
                }
            ],
            "top_scorers_by_position": {
                "QB": {"player": "Quarterback", "team": "Team B", "points": 31.2, "status": "STARTED"}
            },
            "benchwarmer_of_the_week": {"player": "Bench Star", "team": "Team C", "points": 24.1, "status": "BENCH"},
            "rookie_of_the_week": {"player": "Rookie Star", "team": "Team D", "points": 22.0, "status": "TAXI"},
            "free_agent_of_the_week": {"player": "Free Agent Star", "team": "NO", "position": "WR", "points": 20.5, "status": "FREE_AGENT"},
        },
        "nfl_game_intelligence": {
            "source_status": {"play_by_play": "available", "snap_counts": "available"},
            "story_signals": [
                {
                    "type": "BACKFIELD_SPLIT",
                    "team": "SF",
                    "explanation": "Christian McCaffrey and Kaelon Black played nearly even offensive snap shares.",
                }
            ],
        },
    }

    text = render_editorial_review(dossier)

    assert "## Weekly Magazine Features" in text
    assert "Hammer: Started Star" in text
    assert "GOLD FOIL" in text
    assert "Rookie of the Week: Rookie Star" in text
    assert "TAXI" in text
    assert "Free Agent of the Week: Free Agent Star" in text
    assert "## Ironbound NFL Game Intelligence" in text
    assert "BACKFIELD_SPLIT" in text
    assert "Christian McCaffrey and Kaelon Black" in text
