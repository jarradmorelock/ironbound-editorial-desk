from pathlib import Path

from editorial_desk.config import load_publications
from editorial_desk.publication_packets import build_publication_packet
from editorial_desk.publication_render import render_publication_packet


PUBLICATIONS = load_publications(Path("config/publications.json"))
NEWSPAPERS = (
    "ballad_crier",
    "the_stampede",
    "volunteer_voice",
    "saturday_standard",
    "hollywood_beat",
)


def _snapshot():
    return {
        "week": 0,
        "editorial": {"league_format": "dynasty"},
        "league": {
            "season": "2026",
            "roster_positions": ["QB", "RB", "IDP_FLEX", "DEF", "BN"],
            "metadata": {"division_1": "East", "division_2": "West"},
        },
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
        ],
        "rosters": [
            {
                "roster_id": 1,
                "owner_id": "u1",
                "players": ["q1", "rb1", "lb1", "dst1", "rook1"],
                "settings": {"division": 1, "wins": 0, "losses": 0},
            },
            {
                "roster_id": 2,
                "owner_id": "u2",
                "players": ["q2", "rb2", "lb2", "dst2", "rook2"],
                "settings": {"division": 2, "wins": 0, "losses": 0},
            },
        ],
        "players": {
            "q1": {"full_name": "QB One", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5, "status": "Active"},
            "rb1": {"full_name": "RB One", "position": "RB", "fantasy_positions": ["RB"], "years_exp": 3, "status": "Active"},
            "lb1": {"full_name": "LB One", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 2, "status": "Active"},
            "dst1": {"full_name": "Defense One", "position": "DEF", "fantasy_positions": ["DEF"], "years_exp": 0, "status": "Active"},
            "rook1": {"full_name": "Rookie One", "position": "WR", "fantasy_positions": ["WR"], "years_exp": 0, "status": "Active"},
            "q2": {"full_name": "QB Two", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 8, "status": "Active"},
            "rb2": {"full_name": "RB Two", "position": "RB", "fantasy_positions": ["RB"], "years_exp": 4, "status": "Active"},
            "lb2": {"full_name": "LB Two", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 1, "status": "Active"},
            "dst2": {"full_name": "Defense Two", "position": "DEF", "fantasy_positions": ["DEF"], "years_exp": 0, "status": "Active"},
            "rook2": {"full_name": "Rookie Two", "position": "DB", "fantasy_positions": ["DB"], "years_exp": 0, "status": "Active"},
        },
        "matchups": [],
        "transactions": [
            {"transaction_id": "t1", "status": "complete", "type": "trade", "adds": {"rb1": 2}, "drops": {"rb2": 2}}
        ],
        "traded_picks": [
            {"season": "2027", "round": 1, "roster_id": 2, "owner_id": 1, "previous_owner_id": 2},
            {"season": "2028", "round": 2, "roster_id": 1, "owner_id": 2, "previous_owner_id": 1},
        ],
        "keeper_costs": [
            {"roster_id": 1, "player_id": "rb1", "cost_round": 5},
            {"roster_id": 2, "player_id": "rb2", "cost_round": 7},
        ],
        "draft_context": {
            "status": "available",
            "records": [
                {
                    "draft": {"draft_id": "d1", "season": "2026", "type": "rookie", "metadata": {"name": "2026 Rookie Draft"}},
                    "picks": [
                        {"pick_no": 1, "round": 1, "roster_id": 1, "player_id": "rook1", "metadata": {"position": "WR", "adp": 3.0}},
                        {"pick_no": 2, "round": 1, "roster_id": 2, "player_id": "rook2", "metadata": {"position": "DB", "adp": 8.0}},
                    ],
                    "traded_picks": [],
                }
            ],
        },
        "ranking_inputs": {
            "draft_adp": {
                "status": "available",
                "players": {"rook1": {"adp": 3.0}, "rook2": {"adp": 8.0}},
            },
            "dynasty_daddy": {
                "status": "available",
                "players": {
                    "q1": {"trade_value": 8000, "overall_rank": 12},
                    "q2": {"trade_value": 7600, "overall_rank": 18},
                    "rb1": {"trade_value": 6400, "overall_rank": 42},
                },
            },
        },
        "next_matchups": {
            "status": "available",
            "week": 1,
            "records": [
                {"matchup_id": 1, "roster_id": 1},
                {"matchup_id": 1, "roster_id": 2},
            ],
        },
        "nfl_context": {},
    }


def _dossier():
    return {
        "scoreboard": [],
        "lineup_efficiency": [],
        "rankings": {
            "official_standings": [
                {"rank": 1, "roster_id": 1, "team": "One"},
                {"rank": 2, "roster_id": 2, "team": "Two"},
            ],
            "data_power_ranking": [
                {"rank": 1, "roster_id": 1, "team": "One", "score": 0.61},
                {"rank": 2, "roster_id": 2, "team": "Two", "score": 0.57},
            ],
        },
        "divisions": {
            "1": {"name": "East", "teams": [1]},
            "2": {"name": "West", "teams": [2]},
        },
        "awards": {},
        "weekly_features": {},
        "weekly_records": [],
        "roster_health": {"status": "available", "players": []},
        "game_timing": {"starter_game_days": []},
    }


def test_all_five_preseason_packets_render_locked_departments_without_blocking_when_sources_exist():
    snapshot = _snapshot()
    dossier = _dossier()
    rendered = {}

    for key in NEWSPAPERS:
        publication = PUBLICATIONS[key]
        packet = build_publication_packet(snapshot, dossier, publication, "preseason")
        expected = [contract.display_name for contract in publication.contracts_for("preseason")]
        actual = [row["display_name"] for row in packet["departments"]]
        assert actual == expected
        unavailable = [
            (row["feature"], row["display_name"], row["reason"])
            for row in packet["departments"]
            if row["status"] == "unavailable"
        ]
        assert packet["status"] in {"ready", "degraded"}, (key, unavailable)
        assert not unavailable, (key, unavailable)
        text = render_publication_packet(packet)
        for label in expected:
            assert f"## {label}" in text
        rendered[key] = text

    assert "Division" not in rendered["volunteer_voice"]
    assert "East/West Division Order" in rendered["saturday_standard"]
    assert "ADP Draft Profile" in rendered["ballad_crier"]
    assert "Development Rights" in rendered["hollywood_beat"]


def test_preseason_external_adp_absence_degrades_ballad_instead_of_blocking_issue():
    snapshot = _snapshot()
    snapshot["ranking_inputs"].pop("draft_adp")
    for pick in snapshot["draft_context"]["records"][0]["picks"]:
        pick["metadata"].pop("adp", None)

    packet = build_publication_packet(snapshot, _dossier(), PUBLICATIONS["ballad_crier"], "preseason")
    adp = next(row for row in packet["departments"] if row["feature"] == "draft_adp_value")
    assert adp["status"] == "unavailable"
    assert adp["degraded"] is True
    assert packet["status"] == "degraded"


def test_preseason_support_sections_do_not_make_subjective_editorial_selections():
    snapshot = _snapshot()
    packet = build_publication_packet(snapshot, _dossier(), PUBLICATIONS["the_stampede"], "preseason")
    departments = {row["feature"]: row for row in packet["departments"]}

    for feature in ("paper_favorite_inputs", "season_prediction_inputs", "preseason_truth_inputs"):
        assert departments[feature]["status"] in {"ready", "ready_no_items"}
        data = departments[feature]["data"] or {}
        assert "winner" not in data
        assert "favorite" not in data
        assert "prediction" not in data
