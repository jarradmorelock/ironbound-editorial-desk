from editorial_desk.nfl_enrichment import build_nfl_game_intelligence


def flagship_snapshot():
    plays = [
        {
            "game_id": "2026_01_NO_ATL",
            "quarter": 1,
            "posteam": "NO",
            "yardline_100": 60.0,
            "pass_attempt": True,
            "complete_pass": True,
            "pass_touchdown": True,
            "rush_attempt": False,
            "rush_touchdown": False,
            "passer_player_id": "sho",
            "receiver_player_id": "rec1",
            "rusher_player_id": None,
            "td_player_id": "rec1",
            "yards_gained": 100.0,
            "first_down": True,
            "first_down_pass": True,
            "first_down_rush": False,
            "qb_kneel": False,
            "qb_spike": False,
            "score_differential": 0.0,
        },
        {
            "game_id": "2026_01_NO_ATL",
            "quarter": 4,
            "posteam": "NO",
            "yardline_100": 80.0,
            "pass_attempt": True,
            "complete_pass": True,
            "pass_touchdown": True,
            "rush_attempt": False,
            "rush_touchdown": False,
            "passer_player_id": "sho",
            "receiver_player_id": "rec1",
            "rusher_player_id": None,
            "td_player_id": "rec1",
            "yards_gained": 100.0,
            "first_down": True,
            "first_down_pass": True,
            "first_down_rush": False,
            "qb_kneel": False,
            "qb_spike": False,
            "score_differential": -14.0,
        },
        {
            "game_id": "2026_01_NO_ATL",
            "quarter": 4,
            "posteam": "NO",
            "yardline_100": 70.0,
            "pass_attempt": True,
            "complete_pass": True,
            "pass_touchdown": True,
            "rush_attempt": False,
            "rush_touchdown": False,
            "passer_player_id": "sho",
            "receiver_player_id": "rec2",
            "rusher_player_id": None,
            "td_player_id": "rec2",
            "yards_gained": 100.0,
            "first_down": True,
            "first_down_pass": True,
            "first_down_rush": False,
            "qb_kneel": False,
            "qb_spike": False,
            "score_differential": -7.0,
        },
    ]
    for index in range(8):
        plays.append(
            {
                "game_id": "2026_01_NO_ATL",
                "quarter": 1 if index < 4 else 3,
                "posteam": "NO",
                "yardline_100": 35.0,
                "pass_attempt": False,
                "complete_pass": False,
                "pass_touchdown": False,
                "rush_attempt": True,
                "rush_touchdown": False,
                "passer_player_id": None,
                "receiver_player_id": None,
                "rusher_player_id": "etn",
                "td_player_id": None,
                "yards_gained": 5.0,
                "first_down": False,
                "first_down_pass": False,
                "first_down_rush": False,
                "qb_kneel": False,
                "qb_spike": False,
                "score_differential": 0.0,
            }
        )
    for yardline in (8.0, 3.0):
        plays.append(
            {
                "game_id": "2026_01_NO_ATL",
                "quarter": 2,
                "posteam": "NO",
                "yardline_100": yardline,
                "pass_attempt": False,
                "complete_pass": False,
                "pass_touchdown": False,
                "rush_attempt": True,
                "rush_touchdown": True,
                "passer_player_id": None,
                "receiver_player_id": None,
                "rusher_player_id": "mil",
                "td_player_id": "mil",
                "yards_gained": yardline,
                "first_down": True,
                "first_down_pass": False,
                "first_down_rush": True,
                "qb_kneel": False,
                "qb_spike": False,
                "score_differential": 0.0,
            }
        )
    plays.extend(
        [
            {
                "game_id": "2026_01_NO_ATL",
                "quarter": 2,
                "posteam": "NO",
                "yardline_100": 40.0,
                "pass_attempt": False,
                "complete_pass": False,
                "pass_touchdown": False,
                "rush_attempt": True,
                "rush_touchdown": False,
                "passer_player_id": None,
                "receiver_player_id": None,
                "rusher_player_id": "mil",
                "td_player_id": None,
                "yards_gained": 4.0,
                "first_down": False,
                "first_down_pass": False,
                "first_down_rush": False,
                "qb_kneel": False,
                "qb_spike": False,
                "score_differential": 0.0,
            },
            {
                "game_id": "2026_01_NO_ATL",
                "quarter": 3,
                "posteam": "NO",
                "yardline_100": 40.0,
                "pass_attempt": False,
                "complete_pass": False,
                "pass_touchdown": False,
                "rush_attempt": True,
                "rush_touchdown": False,
                "passer_player_id": None,
                "receiver_player_id": None,
                "rusher_player_id": "mil",
                "td_player_id": None,
                "yards_gained": 4.0,
                "first_down": False,
                "first_down_pass": False,
                "first_down_rush": False,
                "qb_kneel": False,
                "qb_spike": False,
                "score_differential": 0.0,
            },
        ]
    )
    return {
        "week": 1,
        "editorial": {"tier": "flagship"},
        "league": {
            "season": "2026",
            "scoring_settings": {
                "pass_yd": 0.04,
                "pass_td": 6,
                "pass_cmp": 0.1,
                "rush_yd": 0.1,
                "rush_td": 6,
                "rush_att": 0.1,
                "rush_fd": 0.25,
                "rec": 0.5,
                "rec_yd": 0.1,
                "rec_td": 6,
                "rec_fd": 0.25,
            },
        },
        "players": {
            "s-shough": {
                "full_name": "Tyler Shough",
                "position": "QB",
                "team": "NO",
                "gsis_id": "sho",
            },
            "s-etn": {
                "full_name": "Travis Etienne Jr.",
                "position": "RB",
                "team": "NO",
                "gsis_id": "etn",
            },
            "s-cmc": {
                "full_name": "Christian McCaffrey",
                "position": "RB",
                "team": "SF",
                "gsis_id": "cmc",
            },
        },
        "rosters": [
            {"roster_id": 1, "players": ["s-shough", "s-etn", "s-cmc"]}
        ],
        "nfl_context": {
            "schedule": {
                "status": "available",
                "records": [
                    {
                        "game_id": "2026_01_NO_ATL",
                        "away_team": "ATL",
                        "away_score": 28,
                        "home_team": "NO",
                        "home_score": 31,
                    }
                ],
            },
            "player_stats": {
                "status": "available",
                "records": [
                    {"player_id": "sho", "player_display_name": "Tyler Shough", "position": "QB", "team": "NO"},
                    {"player_id": "etn", "player_display_name": "Travis Etienne Jr.", "position": "RB", "team": "NO"},
                    {"player_id": "mil", "player_display_name": "Kendre Miller", "position": "RB", "team": "NO"},
                    {"player_id": "cmc", "player_display_name": "Christian McCaffrey", "position": "RB", "team": "SF"},
                    {"player_id": "blk", "player_display_name": "Kaelon Black", "position": "RB", "team": "SF"},
                ],
            },
            "snap_counts": {
                "status": "available",
                "records": [
                    {"game_id": "2026_01_SF_LAR", "player": "Christian McCaffrey", "position": "RB", "team": "SF", "offense_snaps": 32.0, "offense_pct": 0.50},
                    {"game_id": "2026_01_SF_LAR", "player": "Kaelon Black", "position": "RB", "team": "SF", "offense_snaps": 32.0, "offense_pct": 0.50},
                    {"game_id": "2026_01_NO_ATL", "player": "Travis Etienne Jr.", "position": "RB", "team": "NO", "offense_snaps": 35.0, "offense_pct": 0.55},
                    {"game_id": "2026_01_NO_ATL", "player": "Kendre Miller", "position": "RB", "team": "NO", "offense_snaps": 28.0, "offense_pct": 0.44},
                ],
            },
            "play_by_play": {"status": "available", "records": plays},
        },
    }


def test_non_flagship_skips_deep_nfl_enrichment():
    data = flagship_snapshot()
    data["editorial"]["tier"] = "newspaper"
    assert build_nfl_game_intelligence(data) is None


def test_backfield_split_surfaces_near_even_snap_share():
    intelligence = build_nfl_game_intelligence(flagship_snapshot())
    signal = next(
        row
        for row in intelligence["story_signals"]
        if row["type"] == "BACKFIELD_SPLIT" and row["team"] == "SF"
    )
    assert [row["snap_share"] for row in signal["players"]] == [0.5, 0.5]


def test_late_surge_and_comeback_engine_reconstruct_quarter_scoring():
    intelligence = build_nfl_game_intelligence(flagship_snapshot())
    shough = intelligence["players"]["sho"]
    assert shough["fantasy_points_by_quarter"]["1"] == 10.1
    assert shough["fantasy_points_by_quarter"]["4"] == 20.2
    types = {row["type"] for row in intelligence["story_signals"] if row.get("player_id") == "sho"}
    assert "LATE_SURGE" in types
    assert "COMEBACK_ENGINE" in types


def test_high_value_touch_shift_and_missed_windfall_surface_etienne_context():
    intelligence = build_nfl_game_intelligence(flagship_snapshot())
    etienne = intelligence["players"]["etn"]
    miller = intelligence["players"]["mil"]
    assert etienne["opportunities"] == 8
    assert etienne["inside_10_opportunities"] == 0
    assert miller["inside_10_opportunities"] == 2
    signals = intelligence["story_signals"]
    assert any(row["type"] == "HIGH_VALUE_TOUCH_SHIFT" and row.get("player_id") == "etn" for row in signals)
    assert any(row["type"] == "MISSED_WINDFALL" and row.get("player_id") == "etn" for row in signals)
