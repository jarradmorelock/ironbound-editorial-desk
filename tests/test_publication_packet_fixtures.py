from pathlib import Path

from editorial_desk.config import load_publications
from editorial_desk.publication_packets import build_publication_packet
from editorial_desk.publication_render import render_publication_packet
from editorial_desk.review import build_editorial_review


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
        "collected_at": "2026-09-16T12:00:00+00:00",
        "week": 1,
        "editorial": {
            "league_key": "fixture",
            "configured_name": "Fixture League",
            "publication": "Fixture",
            "tier": "newspaper",
            "league_format": "dynasty",
            "ranking_model": "ironbound_dynasty",
        },
        "league": {
            "name": "Fixture League",
            "season": "2026",
            "roster_positions": ["QB", "IDP_FLEX", "BN"],
            "settings": {"league_average_match": 1},
            "metadata": {"division_1": "East", "division_2": "West"},
            "scoring_settings": {"pass_yd": 0.04},
        },
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
            {"user_id": "u3", "display_name": "Three", "metadata": {"team_name": "Three"}},
            {"user_id": "u4", "display_name": "Four", "metadata": {"team_name": "Four"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["q1", "lb1", "b1", "r1"], "settings": {"division": 1, "wins": 1, "losses": 0, "fpts": 30}},
            {"roster_id": 2, "owner_id": "u2", "players": ["q2", "lb2", "b2"], "settings": {"division": 1, "wins": 0, "losses": 1, "fpts": 27}},
            {"roster_id": 3, "owner_id": "u3", "players": ["q3", "lb3", "b3"], "settings": {"division": 2, "wins": 1, "losses": 0, "fpts": 29}},
            {"roster_id": 4, "owner_id": "u4", "players": ["q4", "lb4", "b4"], "settings": {"division": 2, "wins": 0, "losses": 1, "fpts": 26}},
        ],
        "players": {
            "q1": {"full_name": "QB One", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 4, "status": "Active"},
            "lb1": {"full_name": "LB One", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 2, "status": "Active"},
            "b1": {"full_name": "Bench One", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3, "status": "Active"},
            "r1": {"full_name": "Rookie One", "position": "WR", "fantasy_positions": ["WR"], "years_exp": 0, "status": "Active"},
            "q2": {"full_name": "QB Two", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 5, "status": "Active"},
            "lb2": {"full_name": "LB Two", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 3, "status": "Active"},
            "b2": {"full_name": "Bench Two", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 2, "status": "Active"},
            "q3": {"full_name": "QB Three", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 3, "status": "Active"},
            "lb3": {"full_name": "LB Three", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 0, "status": "Active"},
            "b3": {"full_name": "Bench Three", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 1, "status": "Active"},
            "q4": {"full_name": "QB Four", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 6, "status": "Active"},
            "lb4": {"full_name": "LB Four", "position": "LB", "fantasy_positions": ["LB"], "years_exp": 4, "status": "Active"},
            "b4": {"full_name": "Bench Four", "position": "QB", "fantasy_positions": ["QB"], "years_exp": 2, "status": "Active"},
        },
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 30, "starters": ["q1", "lb1"], "players": ["q1", "lb1", "b1"], "players_points": {"q1": 20, "lb1": 10, "b1": 5}},
            {"matchup_id": 1, "roster_id": 2, "points": 27, "starters": ["q2", "lb2"], "players": ["q2", "lb2", "b2"], "players_points": {"q2": 17, "lb2": 10, "b2": 22}},
            {"matchup_id": 2, "roster_id": 3, "points": 29, "starters": ["q3", "lb3"], "players": ["q3", "lb3", "b3"], "players_points": {"q3": 18, "lb3": 11, "b3": 8}},
            {"matchup_id": 2, "roster_id": 4, "points": 26, "starters": ["q4", "lb4"], "players": ["q4", "lb4", "b4"], "players_points": {"q4": 16, "lb4": 10, "b4": 6}},
        ],
        "transactions": [
            {"transaction_id": "w1", "status": "complete", "type": "waiver", "adds": {"q3": 3}, "drops": {}, "settings": {"waiver_bid": 7}}
        ],
        "traded_picks": [
            {"season": "2027", "round": 1, "roster_id": 2, "owner_id": 1, "previous_owner_id": 2}
        ],
        "ranking_inputs": {
            "sleeper_projections": {"status": "available", "players": {}},
            "dynasty_daddy": {"status": "available", "players": {"q1": {"trade_value": 9000, "overall_rank": 4}}},
            "redraft_daddy": {"status": "unavailable", "players": {}, "error": "not used by fixture"},
        },
        "nfl_context": {
            "player_stats": {
                "status": "available",
                "records": [
                    {"player_id": "q1", "player_name": "QB One", "position": "QB", "attempts": 34, "passing_yards": 305, "passing_tds": 3},
                    {"player_id": "q2", "player_name": "QB Two", "position": "QB", "attempts": 41, "passing_yards": 280, "passing_tds": 2},
                    {"player_id": "r1", "player_name": "Rookie One", "position": "WR", "receptions": 9, "receiving_yards": 120, "receiving_tds": 1},
                ],
            },
            "game_windows": [{"name": "monday", "player_ids": ["q1"]}],
        },
        "draft_context": {
            "status": "available",
            "records": [
                {
                    "draft": {"draft_id": "d1", "season": "2026", "type": "rookie", "metadata": {"name": "2026 Rookie Draft"}},
                    "picks": [{"pick_no": 1, "round": 1, "roster_id": 1, "player_id": "r1", "metadata": {"position": "WR"}}],
                    "traded_picks": [],
                }
            ],
        },
        "next_matchups": {
            "status": "available",
            "week": 2,
            "records": [
                {"matchup_id": 3, "roster_id": 1},
                {"matchup_id": 3, "roster_id": 4},
                {"matchup_id": 4, "roster_id": 2},
                {"matchup_id": 4, "roster_id": 3},
            ],
        },
    }


def test_all_five_weekly_newspaper_packets_render_locked_departments_without_label_leakage():
    snapshot = _snapshot()
    dossier = build_editorial_review(snapshot)
    rendered = {}

    for key in NEWSPAPERS:
        publication = PUBLICATIONS[key]
        packet = build_publication_packet(snapshot, dossier, publication, "weekly")
        expected = [contract.display_name for contract in publication.contracts_for("weekly")]
        actual = [department["display_name"] for department in packet["departments"]]
        assert actual == expected
        assert packet["status"] == "ready", (key, [
            (row["display_name"], row["status"], row["reason"])
            for row in packet["departments"]
            if row["status"] == "unavailable"
        ])
        text = render_publication_packet(packet)
        for label in expected:
            assert f"## {label}" in text
        rendered[key] = text

    assert "Weekly Rounds" in rendered["ballad_crier"]
    assert "Weekly Rounds" not in rendered["saturday_standard"]
    assert "Portal Film Room" in rendered["saturday_standard"]
    assert "Portal Film Room" not in rendered["hollywood_beat"]
    assert "Cutting Room Floor" in rendered["hollywood_beat"]
    assert "What a Way to Make a Living" in rendered["the_stampede"]
    assert "Heavy Lifting" not in rendered["the_stampede"]
    assert "Division Pulse" not in rendered["volunteer_voice"]
    assert "divisional" not in rendered["volunteer_voice"].casefold()
