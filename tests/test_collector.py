import requests

from editorial_desk.collector import (
    _collect_ranking_sources,
    _trim_ranking_sources,
    collect_all,
)
from editorial_desk.config import LeagueConfig


class FailingRankingsClient:
    def dynasty_daddy_player_values(self):
        raise requests.ConnectionError("ranking source offline")


class FailingSleeperClient:
    def projections(self, season, week):
        raise requests.ConnectionError("projection source offline")


class EmptyRankingsClient:
    def dynasty_daddy_player_values(self):
        return []


class EmptySleeperClient:
    def nfl_state(self):
        return {"season": "2026"}

    def players(self):
        return {}

    def projections(self, season, week):
        return {}

    def league(self, league_id):
        return {
            "league_id": league_id,
            "name": "Private League",
            "season": "2026",
            "settings": {},
            "roster_positions": [],
        }

    def users(self, league_id):
        return []

    def rosters(self, league_id):
        return []

    def matchups(self, league_id, week):
        return []

    def transactions(self, league_id, week):
        return []

    def traded_picks(self, league_id):
        return []


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


def test_data_only_league_generates_analysis_but_no_publication_dossier(tmp_path):
    league = LeagueConfig(
        key="private_league",
        name="Private League",
        sleeper_league_id="789",
        publication=None,
        publication_profile=None,
        tier="data_only",
        league_format="dynasty",
        ranking_model="ironbound_dynasty",
        publication_enabled=False,
    )

    generated = collect_all(
        [league],
        1,
        tmp_path,
        client=EmptySleeperClient(),
        rankings_client=EmptyRankingsClient(),
    )

    assert {path.name for path in generated} == {"snapshot.json", "analysis.json"}
    assert not list(tmp_path.rglob("dossier.*"))
