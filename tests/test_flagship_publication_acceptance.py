import json
from pathlib import Path

from editorial_desk.external_inputs import ExternalEditorialInputs
from editorial_desk.publication_complete import build_publication_complete_packet


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _build_packet(input_name):
    data = _load(input_name)
    teams = data["teams"]
    team_to_roster = {team: idx + 1 for idx, team in enumerate(teams)}
    snapshot = {
        "week": data["week"],
        "league": {"season": data["season"]},
        "editorial": {
            "league_key": data["league_key"],
            "publication_profile": {"key": data["publication_key"]},
        },
    }
    canonical = {
        "coverage": {"status": "READY", "weeks": list(range(1, data["week"] + 1))},
        "historical_matchups": [],
        "entering_records": {str(data["week"]): {str(i): {"wins": 1, "losses": 1, "ties": 0} for i in range(1, 17)}},
        "team_season_totals": {
            str(i): {"roster_id": i, "team": teams[i - 1], "points": 300 - i, "through_week": data["week"]}
            for i in range(1, 17)
        },
        "player_season_totals": {"overall": {"player_id": "overall", "points": 60.0, "through_week": data["week"]}},
        "player_season_totals_status": "READY",
        "division_summary": {
            "status": "READY",
            "divisions": {
                name: {"division": name, "scoring_average": avg}
                for name, avg in data.get("division_averages", {"1": 100.0}).items()
            },
        },
        "evidence_index": {"fixture:1": {"evidence_id": "fixture:1"}},
        "conflicts": [],
    }
    games = [
        {
            "matchup_id": row["matchup_id"],
            "matchup": f"{teams[row['left_roster_id'] - 1]} vs {teams[row['right_roster_id'] - 1]}",
            "scoreline": "100-90",
        }
        for row in data["games"]
    ]
    forecast = [
        {"matchup_id": row["matchup_id"], "roster_one": row["left_roster_id"], "roster_two": row["right_roster_id"], "projected_margin": 5}
        for row in data["games"]
    ]
    rankings = [
        {"roster_id": i, "team": team, "rank": i, "previous_rank": i}
        for i, team in enumerate(teams, 1)
    ]
    manager = data["manager_honors"]
    no_fear = []
    if manager.get("no_fear"):
        no_fear = [{
            "candidate_type": "NO_FEAR",
            "team": manager["no_fear"],
            "roster_id": team_to_roster[manager["no_fear"]],
            "evidence": {"projected_deficit": manager["no_fear_projected_deficit"]},
        }]
    rookie_names = data.get("rookie_watch_top_five") or [f"Rookie {i}" for i in range(1, 6)]
    research = {
        "publication_key": data["publication_key"],
        "season": data["season"],
        "week": data["week"],
        "game_coverage": {"games": games, "cover_candidates": [{"matchup_id": 1}]},
        "usage_desk": {"status": "READY", "leaders": {}},
        "weekly_honors": {
            "manager_of_the_week": {"team": manager["manager_of_the_week"], "roster_id": team_to_roster[manager["manager_of_the_week"]]},
            "most_efficient_manager": {"team": manager["manager_of_the_week"], "roster_id": team_to_roster[manager["manager_of_the_week"]]},
            "bad_beat": {"team": manager["bad_beat"], "roster_id": team_to_roster[manager["bad_beat"]]},
            "escape_artist": {"team": manager["escape_artist"], "roster_id": team_to_roster[manager["escape_artist"]]},
            "overall_player_of_the_week": {"player_id": "overall", "player": data["player_honors"]["overall"]},
            "started_position_leaders": {
                "QB": {"player_id": "q"},
                "RB": {"player_id": "r"},
                "WR": {"player_id": "w"},
                "TE": {"player_id": "t"},
            },
            "benchwarmer_of_the_week": {"player_id": "bench", "player": data["player_honors"]["benchwarmer"]},
            "rookie_watch_top_five": [{"player_id": f"rookie{i}", "player": name} for i, name in enumerate(rookie_names, 1)],
            "rookie_of_the_week": {"player_id": "rookie1"},
            "season_efficiency_top_three": [{"roster_id": 1, "weeks": data["week"]}],
            "season_team_score_top_three": [
                {"roster_id": team_to_roster[name], "team": name, "weeks": data["week"], "score": 300 - idx}
                for idx, name in enumerate(data.get("season_team_points_top_three") or teams[:3])
            ],
            "player_season_top_three": {"status": "READY", "by_position": {"QB": [{"player_id": "q"}]}},
            "rookie_season_leaders": {"status": "READY", "by_position": {"WR": [{"player_id": "rookie1"}]}},
            "rotating_award_candidates": no_fear,
            "rotating_award_manual_review": [],
            "award_audit": {},
        },
        "story_desk": {"status": "available", "candidates": [{"candidate_id": "story1"}]},
        "power_board": {"writeup_inputs": rankings},
        "power_rankings_chart": {"status": "READY", "rows": rankings},
        "playoff_odds_chart": {"status": "READY", "rows": [{"roster_id": i, "playoff": 50} for i in range(1, 17)]},
        "remaining_schedule_strength": {"status": "READY", "rows": [{"roster_id": i, "average": 50} for i in range(1, 17)]},
        "weekly_matchup_forecast": {"status": "READY", "rows": forecast},
        "division_outlook": {"division_status": "READY", "division_summaries": [{"division": "fixture"}]},
        "ranking_publication_assets": {
            "required": True,
            "assets": {
                "power_rankings": {"status": "READY", "package_path": "publication-assets/ranks.png"},
                "playoff_forecast": {"status": "READY", "package_path": "publication-assets/playoffs.png"},
            },
        },
        "roster_market": {"status": "READY", "sleeper_platform_rates": {"status": "UNAVAILABLE", "required": False}},
    }
    transactions = {
        "coverage": {"status": "READY", "transaction_count": 0},
        "pick_provenance_status": "READY",
        "unresolved_pick_provenance": [],
        "transactions": [],
    }
    source_manifest = {
        "information_cutoff": "2026-09-30T18:00:00+00:00",
        "sleeper": {
            "matchups": {"status": "AVAILABLE", "weeks": list(range(1, data["week"] + 1))},
            "transactions": {"status": "AVAILABLE", "weeks": list(range(1, data["week"] + 1))},
            "projections": {"status": "AVAILABLE", "season": data["season"], "week": data["week"]},
        },
        "rankings": {"status": "READY", "results_through_week": data["week"], "ranking_week": data["week"] + 1},
        "publication_assets": {"status": "READY"},
        "beat_news": {"status": "READY", "blocking": False},
    }
    health = {"status": "READY_NO_ITEMS", "players": [], "news_events": []}
    return build_publication_complete_packet(
        snapshot,
        {},
        research,
        ExternalEditorialInputs(data["publication_key"], schema_version=3),
        canonical_evidence=canonical,
        transaction_evidence=transactions,
        source_manifest=source_manifest,
        health=health,
        publication_assets=research["ranking_publication_assets"]["assets"],
    )


def test_ironbound_week3_gold_standard_is_publication_ready_without_external_research():
    packet = _build_packet("ironbound_week3_publication_input.json")
    expected = _load("ironbound_week3_publication_acceptance.json")

    assert packet["readiness"]["publication_ready"] is True
    assert len(packet["game_dossiers"]) == expected["required_matchups"]
    assert packet["manager_honors"]["bad_beat"]["team"] == expected["manager_honors"]["bad_beat_team"]
    assert packet["manager_honors"]["escape_artist"]["team"] == expected["manager_honors"]["escape_artist_team"]
    no_fear = next(row for row in packet["manager_honors"]["rotating_award_candidates"] if row["candidate_type"] == "NO_FEAR")
    assert no_fear["team"] == expected["manager_honors"]["no_fear_team"]
    assert no_fear["evidence"]["projected_deficit"] >= expected["manager_honors"]["no_fear_min_projected_deficit"]
    assert packet["player_honors"]["overall_player_of_the_week"]["player"] == expected["player_honors"]["overall"]
    assert packet["player_honors"]["benchwarmer_of_the_week"]["player"] == expected["player_honors"]["benchwarmer"]
    assert [row["team"] for row in packet["manager_honors"]["season_team_score_top_three"]] == expected["season_team_points_top_three"]
    assert {
        key: row["scoring_average"]
        for key, row in packet["division_report"]["canonical"]["divisions"].items()
    } == expected["division_averages"]
    assert len(packet["week_ahead"]["rows"]) == expected["week_ahead_matchups"]


def test_unbound_regular_season_gold_standard_is_publication_ready_without_external_research():
    packet = _build_packet("unbound_regular_season_publication_input.json")
    expected = _load("unbound_regular_season_publication_acceptance.json")

    assert packet["readiness"]["publication_ready"] is True
    assert len(packet["game_dossiers"]) == expected["required_matchups"]
    assert packet["manager_honors"]["manager_of_the_week"]["team"] == expected["manager_honors"]["manager_of_the_week"]
    assert packet["manager_honors"]["bad_beat"]["team"] == expected["manager_honors"]["bad_beat_team"]
    assert packet["manager_honors"]["escape_artist"]["team"] == expected["manager_honors"]["escape_artist_team"]
    assert packet["player_honors"]["overall_player_of_the_week"]["player"] == expected["player_honors"]["overall"]
    assert packet["player_honors"]["benchwarmer_of_the_week"]["player"] == expected["player_honors"]["benchwarmer"]
    assert [row["player"] for row in packet["rookie_watch"]["rookie_watch_top_five"]] == expected["rookie_watch_top_five"]
    assert len(packet["week_ahead"]["rows"]) == expected["week_ahead_matchups"]
