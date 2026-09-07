import requests

from editorial_desk.collector import (
    _collect_ranking_sources,
    _trim_ranking_sources,
)


class FailingRankingsClient:
    def dynasty_daddy_player_values(self):
        raise requests.ConnectionError("ranking source offline")


class FailingSleeperClient:
    def projections(self, season, week):
        raise requests.ConnectionError("projection source offline")


def test_optional_ranking_source_failure_does_not_abort_collection():
    sources = _collect_ranking_sources(
        FailingRankingsClient(),
        FailingSleeperClient(),
        "2026",
        4,
    )
    assert sources["dynasty_daddy"]["status"] == "unavailable"
    assert sources["sleeper_projections"]["status"] == "unavailable"


def test_ranking_inputs_are_trimmed_to_players_in_the_league():
    sources = {
        "dynasty_daddy": {
            "status": "available",
            "players": {
                "p1": {
                    "sleeper_id": "p1",
                    "full_name": "Player One",
                    "trade_value": 100,
                    "unneeded": "discard",
                },
                "p2": {"sleeper_id": "p2", "full_name": "Player Two"},
            },
        },
        "sleeper_projections": {
            "status": "available",
            "players": {"p1": {"rush_yd": 80}, "p2": {"rush_yd": 40}},
        },
    }
    trimmed = _trim_ranking_sources(sources, {"p1"})
    assert set(trimmed["dynasty_daddy"]["players"]) == {"p1"}
    assert "unneeded" not in trimmed["dynasty_daddy"]["players"]["p1"]
    assert set(trimmed["sleeper_projections"]["players"]) == {"p1"}
