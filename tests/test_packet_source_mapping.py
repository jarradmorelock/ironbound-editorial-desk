from editorial_desk.config import FeatureContractConfig, PublicationConfig
from editorial_desk.enriched_collector import _collect_next_matchups, _ensure_next_matchups
from editorial_desk.publication_packets import build_publication_packet


def _publication(features):
    return PublicationConfig(
        key="saturday",
        name="Saturday",
        tier="newspaper",
        source_files=(),
        recurring_sections=(),
        brand_departments=(),
        editorial_priorities=(),
        feature_contracts={
            "weekly": tuple(
                FeatureContractConfig(feature, feature, True) for feature in features
            )
        },
    )


def _snapshot():
    return {
        "week": 1,
        "league": {"roster_positions": ["QB", "IDP_FLEX", "BN"]},
        "users": [
            {"user_id": "u1", "display_name": "One", "metadata": {"team_name": "One"}},
            {"user_id": "u2", "display_name": "Two", "metadata": {"team_name": "Two"}},
        ],
        "rosters": [
            {"roster_id": 1, "owner_id": "u1", "players": ["q1", "lb1"], "settings": {"division": 1}},
            {"roster_id": 2, "owner_id": "u2", "players": ["q2", "lb2"], "settings": {"division": 2}},
        ],
        "players": {
            "q1": {"full_name": "QB One", "position": "QB", "fantasy_positions": ["QB"]},
            "lb1": {"full_name": "LB One", "position": "LB", "fantasy_positions": ["LB"]},
            "q2": {"full_name": "QB Two", "position": "QB", "fantasy_positions": ["QB"]},
            "lb2": {"full_name": "LB Two", "position": "LB", "fantasy_positions": ["LB"]},
        },
        "matchups": [
            {"matchup_id": 1, "roster_id": 1, "points": 30, "starters": ["q1", "lb1"], "players": ["q1", "lb1"], "players_points": {"q1": 20, "lb1": 10}},
            {"matchup_id": 1, "roster_id": 2, "points": 25, "starters": ["q2", "lb2"], "players": ["q2", "lb2"], "players_points": {"q2": 18, "lb2": 7}},
        ],
        "ranking_inputs": {
            "dynasty_daddy": {
                "status": "available",
                "players": {"q1": {"trade_value": 9000, "overall_rank": 4}},
            }
        },
        "next_matchups": {
            "status": "available",
            "week": 2,
            "records": [
                {"matchup_id": 2, "roster_id": 1},
                {"matchup_id": 2, "roster_id": 2},
            ],
        },
    }


def _dossier():
    return {
        "scoreboard": [
            {"winner": {"roster_id": 1, "team": "One", "points": 30}, "loser": {"roster_id": 2, "team": "Two", "points": 25}, "margin": 5}
        ],
        "rankings": {
            "official_standings": [{"rank": 1, "roster_id": 1, "team": "One"}],
            "data_power_ranking": [{"rank": 1, "roster_id": 1, "team": "One"}],
        },
        "divisions": {"1": {"name": "East", "average_points": 30}, "2": {"name": "West", "average_points": 25}},
        "weekly_records": [{"record_type": "high_score", "team": "One", "value": 30}],
        "weekly_features": {
            "benchwarmer_of_the_week": {"player": "Bench Guy", "points": 22},
            "rookie_of_the_week": {"player": "Rookie", "points": 18},
            "free_agent_of_the_week": {"player": "Free Agent", "points": 16},
        },
        "awards": {
            "bad_beat": {"team": "Two", "points": 25},
            "escape_artist": {"team": "One", "points": 30},
            "manager_of_the_week": {"team": "One"},
        },
    }


def test_packet_resolver_uses_established_weekly_dossier_paths():
    features = [
        "standings",
        "ranking_movement",
        "division_metrics",
        "record_watch",
        "idp_position_metrics",
        "weekly_desk_honors",
        "dynasty_market_values",
        "next_matchups",
    ]
    packet = build_publication_packet(
        _snapshot(),
        _dossier(),
        _publication(features),
        "weekly",
        chronicle_history={"coverage": {"complete": True, "warnings": []}},
    )
    rows = {row["feature"]: row for row in packet["departments"]}

    assert all(rows[feature]["status"] == "ready" for feature in features)
    assert rows["standings"]["data"] == _dossier()["rankings"]["official_standings"]
    assert rows["ranking_movement"]["data"][0]["team"] == "One"
    assert rows["ranking_movement"]["data"][0]["rank"] == 1
    assert rows["ranking_movement"]["data"][0]["movement"] is None
    assert rows["division_metrics"]["data"] == _dossier()["divisions"]
    assert rows["record_watch"]["data"]["records"] == _dossier()["weekly_records"]
    assert set(rows["idp_position_metrics"]["data"]) == {"QB", "LB"}
    honors = rows["weekly_desk_honors"]["data"]
    assert honors["benchwarmer"] == _dossier()["weekly_features"]["benchwarmer_of_the_week"]
    assert honors["rookie"] == _dossier()["weekly_features"]["rookie_of_the_week"]
    assert honors["free_agent"] == _dossier()["weekly_features"]["free_agent_of_the_week"]
    assert honors["bad_beat"] == _dossier()["awards"]["bad_beat"]
    assert rows["dynasty_market_values"]["data"]["q1"]["trade_value"] == 9000
    assert rows["next_matchups"]["data"] == _snapshot()["next_matchups"]["records"]


class FakeSleeper:
    def matchups(self, league_id, week):
        assert league_id == "123"
        assert week == 2
        return [{"matchup_id": 4, "roster_id": 1}, {"matchup_id": 4, "roster_id": 2}]


def test_next_matchups_collection_is_normalized_and_one_week_ahead():
    result = _collect_next_matchups(FakeSleeper(), "123", 1)
    assert result["status"] == "available"
    assert result["week"] == 2
    assert len(result["records"]) == 2

    snapshot = {}
    _ensure_next_matchups(snapshot, FakeSleeper(), "123", 1)
    assert snapshot["next_matchups"] == result


def test_next_matchups_failure_is_explicitly_unavailable():
    class BrokenSleeper:
        def matchups(self, league_id, week):
            raise ValueError("next week unavailable")

    result = _collect_next_matchups(BrokenSleeper(), "123", 1)
    assert result["status"] == "unavailable"
    assert result["week"] == 2
    assert result["records"] == []
    assert "next week unavailable" in result["error"]
