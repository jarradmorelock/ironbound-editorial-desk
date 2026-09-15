from editorial_desk.metrics import build_weekly_dossier
from editorial_desk.weekly_features import apply_weekly_features


def snapshot():
    players = {
        "qb1": {
            "full_name": "Quarterback One",
            "position": "QB",
            "fantasy_positions": ["QB"],
            "years_exp": 5,
            "gsis_id": "g-qb1",
        },
        "qb2": {
            "full_name": "Quarterback Two",
            "position": "QB",
            "fantasy_positions": ["QB"],
            "years_exp": 4,
            "gsis_id": "g-qb2",
        },
        "rb1": {
            "full_name": "Runner One",
            "position": "RB",
            "fantasy_positions": ["RB"],
            "years_exp": 2,
            "gsis_id": "g-rb1",
        },
        "rb2": {
            "full_name": "Rookie Runner",
            "position": "RB",
            "fantasy_positions": ["RB"],
            "years_exp": 0,
            "gsis_id": "g-rb2",
        },
        "wr1": {
            "full_name": "Receiver One",
            "position": "WR",
            "fantasy_positions": ["WR"],
            "years_exp": 3,
            "gsis_id": "g-wr1",
        },
        "wr2": {
            "full_name": "Receiver Two",
            "position": "WR",
            "fantasy_positions": ["WR"],
            "years_exp": 1,
            "gsis_id": "g-wr2",
        },
        "wr3": {
            "full_name": "Receiver Three",
            "position": "WR",
            "fantasy_positions": ["WR"],
            "years_exp": 2,
            "gsis_id": "g-wr3",
        },
        "wr4": {
            "full_name": "Receiver Four",
            "position": "WR",
            "fantasy_positions": ["WR"],
            "years_exp": 2,
            "gsis_id": "g-wr4",
        },
    }
    return {
        "collected_at": "2026-09-15T22:00:00+00:00",
        "week": 1,
        "editorial": {
            "league_key": "test",
            "configured_name": "Test League",
            "publication": "Test Paper",
            "tier": "flagship",
            "league_format": "dynasty",
            "ranking_model": "ironbound_dynasty",
        },
        "league": {
            "name": "Test League",
            "season": "2026",
            "roster_positions": ["QB", "RB", "WR", "FLEX", "BN"],
            "settings": {"league_average_match": 1, "divisions": 2},
            "metadata": {"division_1": "Forge", "division_2": "Anvil"},
            "scoring_settings": {
                "pass_yd": 0.04,
                "pass_td": 6,
                "pass_int": -2,
                "rush_yd": 0.1,
                "rush_td": 6,
                "rush_fd": 0.25,
                "rec": 0.5,
                "rec_yd": 0.1,
                "rec_td": 6,
                "rec_fd": 0.25,
            },
        },
        "users": [
            {"user_id": "u1", "display_name": "Owner One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Owner Two", "metadata": {"team_name": "Two"}},
            {"user_id": "u3", "display_name": "Owner Three", "metadata": {"team_name": "Three"}},
            {"user_id": "u4", "display_name": "Owner Four", "metadata": {"team_name": "Four"}},
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["qb1", "rb1", "rb2", "wr1", "wr2"],
                "taxi": ["rb2"],
                "settings": {"division": 1, "wins": 0, "losses": 1, "fpts": 101},
            },
            {
                "roster_id": 2,
                "owner_id": "u2",
                "players": ["qb2", "rb1", "wr3", "wr4"],
                "settings": {"division": 1, "wins": 1, "losses": 0, "fpts": 110},
            },
            {
                "roster_id": 3,
                "owner_id": "u3",
                "players": ["qb1", "rb1", "wr1", "wr2"],
                "settings": {"division": 2, "wins": 1, "losses": 0, "fpts": 70},
            },
            {
                "roster_id": 4,
                "owner_id": "u4",
                "players": ["qb2", "rb1", "wr3", "wr4"],
                "settings": {"division": 2, "wins": 0, "losses": 1, "fpts": 65},
            },
        ],
        "players": players,
        "matchups": [
            {
                "matchup_id": 1,
                "roster_id": 1,
                "points": 101,
                "starters": ["qb1", "rb1", "wr1", "wr2"],
                "players": ["qb1", "rb1", "rb2", "wr1", "wr2"],
                "players_points": {"qb1": 20, "rb1": 20, "rb2": 35, "wr1": 31, "wr2": 30},
            },
            {
                "matchup_id": 1,
                "roster_id": 2,
                "points": 110,
                "starters": ["qb2", "rb1", "wr3", "wr4"],
                "players": ["qb2", "rb1", "wr3", "wr4"],
                "players_points": {"qb2": 25, "rb1": 25, "wr3": 30, "wr4": 30},
            },
            {
                "matchup_id": 2,
                "roster_id": 3,
                "points": 70,
                "starters": ["qb1", "rb1", "wr1", "wr2"],
                "players": ["qb1", "rb1", "wr1", "wr2"],
                "players_points": {"qb1": 10, "rb1": 20, "wr1": 20, "wr2": 20},
            },
            {
                "matchup_id": 2,
                "roster_id": 4,
                "points": 65,
                "starters": ["qb2", "rb1", "wr3", "wr4"],
                "players": ["qb2", "rb1", "wr3", "wr4"],
                "players_points": {"qb2": 15, "rb1": 15, "wr3": 20, "wr4": 15},
            },
        ],
        "transactions": [],
        "traded_picks": [],
        "ranking_inputs": {
            "sleeper_projections": {"status": "available", "players": {}},
            "dynasty_daddy": {"status": "available", "players": {}},
        },
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {
                        "player_id": "fa1",
                        "player_display_name": "Free Agent Star",
                        "position": "RB",
                        "carries": 18,
                        "rushing_yards": 110,
                        "rushing_tds": 2,
                        "rushing_first_downs": 5,
                        "targets": 3,
                        "receptions": 2,
                        "receiving_yards": 20,
                        "receiving_tds": 0,
                        "receiving_first_downs": 1,
                        "fantasy_points_ppr": 29,
                    },
                    {
                        "player_id": "g-wr1",
                        "player_display_name": "Receiver One",
                        "position": "WR",
                        "targets": 12,
                        "receptions": 10,
                        "receiving_yards": 160,
                        "receiving_tds": 2,
                        "receiving_first_downs": 7,
                        "fantasy_points_ppr": 38,
                    },
                ],
            }
        },
    }


def enriched():
    data = snapshot()
    dossier = build_weekly_dossier(data)
    return data, apply_weekly_features(data, dossier)


def test_lineup_efficiency_includes_taxi_in_sleeper_max_points():
    _, dossier = enriched()
    row = next(r for r in dossier["lineup_efficiency"] if r["roster_id"] == 1)
    assert row["optimal_points"] == 116
    assert row["efficiency"] == round(101 / 116, 4)


def test_divisional_mvp_nominees_are_starters_and_gold_marks_top_nominee():
    _, dossier = enriched()
    nominees = dossier["weekly_features"]["divisional_mvp_nominees"]
    assert {row["division_name"] for row in nominees} == {"Forge", "Anvil"}
    assert all(row["status"] == "STARTED" for row in nominees)
    assert all(row["player"] != "Rookie Runner" for row in nominees)
    assert sum(bool(row["gold_foil"]) for row in nominees) == 1
    assert next(row for row in nominees if row["gold_foil"])["points"] == 31


def test_rookie_of_week_reports_taxi_status():
    _, dossier = enriched()
    rookie = dossier["weekly_features"]["rookie_of_the_week"]
    assert rookie["player"] == "Rookie Runner"
    assert rookie["status"] == "TAXI"
    assert rookie["points"] == 35


def test_benchwarmer_excludes_taxi_players():
    _, dossier = enriched()
    benchwarmer = dossier["weekly_features"]["benchwarmer_of_the_week"]
    assert benchwarmer is None


def test_top_scorers_by_position_include_roster_status():
    _, dossier = enriched()
    leaders = dossier["weekly_features"]["top_scorers_by_position"]
    assert leaders["QB"]["player"] == "Quarterback Two"
    assert leaders["QB"]["status"] == "STARTED"
    assert leaders["RB"]["player"] == "Rookie Runner"
    assert leaders["RB"]["status"] == "TAXI"


def test_free_agent_of_week_uses_league_scoring_and_excludes_rostered_players():
    _, dossier = enriched()
    free_agent = dossier["weekly_features"]["free_agent_of_the_week"]
    assert free_agent["player"] == "Free Agent Star"
    assert free_agent["position"] == "RB"
    assert free_agent["points"] == 27.5
